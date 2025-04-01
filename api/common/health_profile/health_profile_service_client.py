from __future__ import annotations

import datetime
import traceback
from os import environ
from typing import Optional

import ddtrace
import flask

from authn.models.user import User
from authz.models.roles import ROLES
from common.base_triforce_client import BaseTriforceClient
from common.health_profile.health_profile_service_models import (
    ClinicalStatus,
    ConditionType,
    GestationalDiabetesStatus,
    GetFertilityStatusHistoryResponse,
    MemberCondition,
    PregnancyAndRelatedConditions,
)
from utils.log import logger

log = logger(__name__)


# Proxy to new Health Profile Service
class HealthProfileServiceClient:
    def __init__(
        self,
        user: User,
        accessing_user: Optional[User] = None,
        base_url: Optional[str] = None,
        release_pregnancy_updates: bool | None = False,
    ) -> None:
        self.user = user
        self.accessing_user = self._get_accessing_user(user, accessing_user)

        if not base_url:
            internal_gateway_url = environ.get("INTERNAL_GATEWAY_URL", None)
            if internal_gateway_url:
                prefix = internal_gateway_url
            else:
                prefix = "http://health-profile-api-service.hpp.svc.cluster.local"
            base_url = f"{prefix}/api/v1/health-profile"
        if not base_url:
            raise Exception(
                "Unable to configure HealthProfileServiceClient because Internal Gateway environment variable not set"
            )

        self.client = BaseTriforceClient(
            base_url=base_url,
            service_name="HealthProfileService",
            headers=self._headers(),
        )

        self.release_pregnancy_updates = release_pregnancy_updates

    def _headers(self) -> dict[str, str]:
        # If currrent request has User Headers, BaseTriforceClient will forward them
        # As fallback, inject them using the requested user.
        # This assumes correct permissions checks, if necessary, have already been applied upstream
        try:
            if flask.request.headers.get("X-Maven-User-ID"):
                return {}
        except Exception:
            pass
        headers = {
            "X-Maven-User-Id": str(self.user.id),
            "X-Maven-User-Identities": '["member"]',
        }
        log.info("Adding missing user headers", context=headers)
        return headers

    @staticmethod
    def _get_accessing_user(user: User, accessing_user: Optional[User]) -> User:
        from common.services.api import _get_user, _get_user_from_token

        if accessing_user:
            return accessing_user
        try:
            accessing_user = _get_user() or _get_user_from_token()
            if accessing_user:
                return accessing_user
        except Exception:
            pass
        return user

    def get_fertility_status_history(
        self,
    ) -> GetFertilityStatusHistoryResponse:
        route = f"/users/{self.user.id}/data?include=fertility_status_history"
        try:
            response = self.client.make_service_request(
                route,
                method="GET",
            )
            log.info(
                "Mono to HPS GET",
                context={
                    "user": self.user.id,
                    "base_url": self.client.base_url,
                    "route": route,
                    "status_code": response.status_code,
                },
            )
            response.raise_for_status()
            return GetFertilityStatusHistoryResponse.from_dict(response.json())
        except Exception as e:
            log.error(
                "Exception occurred in Health Profile Service API call",
                error=str(e),
                exc=traceback.format_exc(),
                context={
                    "user": self.user.id,
                    "base_url": self.client.base_url,
                    "route": route,
                },
            )
            raise e

    def set_fertility_status(self, status: str) -> None:
        route = f"/users/{self.user.id}/data-point-types/fertility_status_history"
        try:
            data = {
                "status_code": status,
                "modifier_role": ",".join(self.accessing_user.user_types) or "unknown",
                "modifier_name": self.accessing_user.full_name or "unknown",
                "modifier_verticals": [],  # todo
            }
            log.info(
                "Mono to HPS Post",
                context={
                    "user": self.user.id,
                    "base_url": self.client.base_url,
                    "route": route,
                    "status_code": status,
                },
            )
            response = self.client.make_service_request(
                route,
                data=data,
                method="POST",
            )
            response.raise_for_status()
        except Exception as e:
            log.error(
                "Exception occurred in Health Profile Service API call",
                error=str(e),
                exc=traceback.format_exc(),
            )
            raise e

    @ddtrace.tracer.wrap()
    def put_member_conditions(self, member_conditions: list) -> None:
        route = f"/member_conditions/{self.user.id}"
        try:
            log.info(
                "Mono to HPS Put",
                context={
                    "user": self.user.id,
                    "base_url": self.client.base_url,
                    "route": route,
                },
            )
            response = self.client.make_service_request(
                route,
                data=member_conditions,
                method="PUT",
            )
            response.raise_for_status()
        except Exception as e:
            log.error(
                "Exception occurred in Health Profile Service API call",
                error=str(e),
                exc=traceback.format_exc(),
            )
            raise e

    @ddtrace.tracer.wrap()
    def put_current_pregnancy_and_gdm_status(
        self,
        pregnancy_due_date: datetime.date,
        gdm_status: GestationalDiabetesStatus,
        gdm_onset_date: datetime.date | None,
    ) -> None:
        existing_pregnancies = self.get_pregnancy(
            self.user.id, ClinicalStatus.ACTIVE.value
        )
        related_conditions = {
            ConditionType.GESTATIONAL_DIABETES.value: {
                "status": gdm_status.value,
                "onset_date": gdm_onset_date.isoformat() if gdm_onset_date else None,
                "modifier": {
                    "id": self.user.id,
                    "name": self.user.full_name,
                    "role": ROLES.member,
                    "verticals": [],
                },
            }
        }
        if len(existing_pregnancies) == 1:
            current_pregnancy = existing_pregnancies[0]
            data = {
                ConditionType.PREGNANCY.value: {
                    "id": current_pregnancy.id,
                    "user_id": self.user.id,
                },
                "related_conditions": related_conditions,
            }
            self.patch_pregnancy_and_related_conditions(current_pregnancy.id, data)
        else:
            route = f"/pregnancy_and_related_conditions/{self.user.id}"
            try:
                data = {
                    ConditionType.PREGNANCY.value: {
                        "estimated_date": pregnancy_due_date.isoformat()
                        if pregnancy_due_date
                        else None,
                        "status": "active",
                        "modifier": None,
                    },
                    "related_conditions": related_conditions,
                }
                log.info(
                    "Mono to HPS Put",
                    context={
                        "user": self.user.id,
                        "base_url": self.client.base_url,
                        "route": route,
                    },
                )
                response = self.client.make_service_request(
                    route,
                    params={
                        "release_pregnancy_updates": self.release_pregnancy_updates,
                    },
                    data=data,
                    method="PUT",
                )
                response.raise_for_status()
            except Exception as e:
                log.error(
                    "Exception occurred in Health Profile Service API call",
                    error=str(e),
                    exc=traceback.format_exc(),
                )
                raise e

    @ddtrace.tracer.wrap()
    def put_pregnancy_and_related_conditions(
        self, pregnancy_and_related_conditions: dict
    ) -> PregnancyAndRelatedConditions:
        route = f"/pregnancy_and_related_conditions/{self.user.id}"
        try:
            log.info(
                "Mono to HPS Put",
                context={
                    "user": self.user.id,
                    "base_url": self.client.base_url,
                    "route": route,
                },
            )
            response = self.client.make_service_request(
                route,
                params={
                    "release_pregnancy_updates": self.release_pregnancy_updates,
                },
                data=pregnancy_and_related_conditions,
                method="PUT",
            )
            response.raise_for_status()
            return PregnancyAndRelatedConditions.from_dict(response.json())
        except Exception as e:
            log.error(
                "Exception occurred in Health Profile Service API call",
                error=str(e),
                exc=traceback.format_exc(),
            )
            raise e

    @ddtrace.tracer.wrap()
    def patch_pregnancy_and_related_conditions(
        self, pregnancy_id: str, pregnancy_and_related_conditions: dict
    ) -> PregnancyAndRelatedConditions:
        route = f"/pregnancy_and_related_conditions/{pregnancy_id}"
        try:
            log.info(
                "Mono to HPS Patch",
                context={
                    "user": self.user.id,
                    "base_url": self.client.base_url,
                    "route": route,
                },
            )
            response = self.client.make_service_request(
                route,
                data=pregnancy_and_related_conditions,
                method="PATCH",
            )
            response.raise_for_status()
            return PregnancyAndRelatedConditions.from_dict(response.json())
        except Exception as e:
            log.error(
                "Exception occurred in Health Profile Service API call",
                error=str(e),
                exc=traceback.format_exc(),
            )
            raise e

    @ddtrace.tracer.wrap()
    def get_pregnancy_and_related_conditions(
        self,
    ) -> list[PregnancyAndRelatedConditions]:
        route = f"/pregnancy_and_related_conditions/{self.user.id}"
        try:
            log.info(
                "Mono to HPS Get",
                context={
                    "user": self.user.id,
                    "base_url": self.client.base_url,
                    "route": route,
                },
            )
            response = self.client.make_service_request(
                route,
                method="GET",
                params={
                    "release_pregnancy_updates": self.release_pregnancy_updates,
                },
            )
            response.raise_for_status()
            result = [
                PregnancyAndRelatedConditions.from_dict(item)
                for item in response.json()
            ]
            return result
        except Exception as e:
            log.error(
                "Exception occurred in Health Profile Service API call",
                error=str(e),
                exc=traceback.format_exc(),
            )
            raise e

    def post_fertility_status_history(self, fertility_status_code: str) -> None:
        route = f"/users/{self.user.id}/data-point-types/fertility_status_history"
        try:
            data = {
                "status_code": fertility_status_code,
                "modifier_role": "member",
                "modifier_name": self.user.full_name or "unknown",
                "modifier_id": self.user.id,
                "modifier_verticals": [],
            }
            log.info(
                "Updating fertility status to successful_pregnancy to HPS",
                context={
                    "user": self.user.id,
                },
            )
            response = self.client.make_service_request(
                route,
                data=data,
                method="POST",
            )
            response.raise_for_status()
        except Exception as e:
            log.error(
                "Exception occurred while updating fertility status to HPS",
                error=str(e),
                exc=traceback.format_exc(),
                context={
                    "user": self.user.id,
                },
            )
            raise e

    @ddtrace.tracer.wrap()
    def get_pregnancy(self, user_id: int, status: str) -> list[MemberCondition]:
        route = f"/users/{self.user.id}/pregnancies"
        params = {"status": status, "user_id": user_id}

        try:
            log.info(
                "Mono to HPS Get Pregnancies",
                context={
                    "user": self.user.id,
                    "base_url": self.client.base_url,
                    "route": route,
                },
            )
            response = self.client.make_service_request(
                route,
                method="GET",
                params=params,
            )
            response.raise_for_status()
            result = [MemberCondition.from_dict(item) for item in response.json()]
            return result
        except Exception as e:
            log.error(
                "Exception occurred in Health Profile Service API call get_pregnancy",
                error=str(e),
                exc=traceback.format_exc(),
            )
            raise e

    @ddtrace.tracer.wrap()
    def put_pregnancy(self, pregnancy: MemberCondition) -> None:
        route = f"/users/{self.user.id}/pregnancies"

        try:
            log.info(
                "Mono to HPS Put Pregnancy",
                context={
                    "user": self.user.id,
                    "base_url": self.client.base_url,
                    "route": route,
                },
            )
            response = self.client.make_service_request(
                route,
                method="PUT",
                data=pregnancy.to_dict(),
            )
            response.raise_for_status()
        except Exception as e:
            log.error(
                "Exception occurred in Health Profile Service API call put_pregnancy",
                error=str(e),
                exc=traceback.format_exc(),
            )
            raise e
