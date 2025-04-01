from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from flask import jsonify, request
from flask_restful import abort
from marshmallow import ValidationError
from sqlalchemy import String, case, cast
from sqlalchemy.orm.query import Query

from authn.models.user import User
from authz.models.roles import ROLES
from direct_payment.clinic.models.clinic import FertilityClinic, FertilityClinicLocation
from direct_payment.clinic.resources.clinic_auth import ClinicAuthorizedResource
from direct_payment.clinic.schemas.aggregate_procedures import (
    AggregateProceduresSortByEnum,
    FertilityClinicAggregateProcedureSchema,
    FertilityClinicAggregateProceduresGetSchema,
    OrderDirectionsEnum,
)
from direct_payment.clinic.schemas.procedures import FertilityClinicProceduresSchema
from direct_payment.clinic.utils.aggregate_procedures_utils import (
    get_benefit_e9y_start_and_expiration_date,
)
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedure,
    TreatmentProcedureStatus,
)
from direct_payment.treatment_procedure.schemas.treatment_procedure import (
    TreatmentProcedureSchema,
)
from direct_payment.treatment_procedure.utils.procedure_helpers import (
    get_mapped_global_procedures,
)
from storage.connection import db
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.repository.member_benefit import MemberBenefitRepository


def get_wallet_state_and_benefit_type_and_e9y_dates(
    wallet_id: int, user_id: int
) -> Dict[str, Optional[str]]:
    wallet = db.session.query(ReimbursementWallet).get(wallet_id)

    if wallet is None:
        return {
            "wallet_state": None,
            "benefit_type": None,
            "benefit_start_date": None,
            "benefit_expires_date": None,
        }

    reimbursement_category = wallet.get_direct_payment_category

    if reimbursement_category:
        benefit_type = wallet.category_benefit_type(
            request_category_id=reimbursement_category.id
        )
    else:
        benefit_type = None

    wallet_state_value = wallet.state.value if wallet.state else None
    benefit_type_value = benefit_type.value if benefit_type else None

    (
        member_eligibility_start_date,
        benefit_expires_date,
    ) = get_benefit_e9y_start_and_expiration_date(wallet, user_id)
    formatted_benefit_start_date = (
        member_eligibility_start_date.isoformat()
        if member_eligibility_start_date
        else None
    )
    formatted_benefit_expires_date = (
        benefit_expires_date.isoformat() if benefit_expires_date else None
    )

    return {
        "wallet_state": wallet_state_value,
        "benefit_type": benefit_type_value,
        "benefit_start_date": formatted_benefit_start_date,
        "benefit_expires_date": formatted_benefit_expires_date,
    }


def _get_order_direction_and_sort_by_from_args(
    args: dict,
) -> Tuple[Optional[AggregateProceduresSortByEnum], Optional[OrderDirectionsEnum]]:
    sort_by = args.get("sort_by")
    if sort_by is not None:
        sort_by = AggregateProceduresSortByEnum[sort_by.upper()]

    order_direction = args.get("order_direction")
    if order_direction is not None:
        order_direction = OrderDirectionsEnum[order_direction.upper()]
    return sort_by, order_direction


def _get_filters_from_args(args: dict) -> dict[str, List]:
    return {
        key: args[key]
        for key in ["status", "clinic_id", "clinic_location_id"]
        if key in args
    }


def _apply_sort(
    base_query: Query,
    sort_by: Optional[AggregateProceduresSortByEnum],
    order_direction: Optional[OrderDirectionsEnum],
) -> Query:
    if sort_by is None:
        return base_query.order_by(TreatmentProcedure.created_at.desc())

    # Clinic portal displays the end date when procedure status is cancelled
    date_sort = case(
        [
            (
                TreatmentProcedure.status == TreatmentProcedureStatus.CANCELLED,
                TreatmentProcedure.end_date,
            )
        ],
        else_=TreatmentProcedure.start_date,
    )
    sort_options = {
        AggregateProceduresSortByEnum.MEMBER_LAST_NAME: [User.last_name],
        AggregateProceduresSortByEnum.PROCEDURE_NAME: [
            TreatmentProcedure.procedure_name
        ],
        AggregateProceduresSortByEnum.CLINIC_NAME: [
            FertilityClinic.name,
            FertilityClinicLocation.name,
        ],
        AggregateProceduresSortByEnum.DATE: [date_sort],
        AggregateProceduresSortByEnum.COST: [TreatmentProcedure.cost],
        # mysql will order enum columns by their index rather than the string value, so we cast to a string here
        AggregateProceduresSortByEnum.STATUS: [cast(TreatmentProcedure.status, String)],
    }

    sort_columns = []
    if order_direction == OrderDirectionsEnum.DESC:
        sort_columns = [c.desc() for c in sort_options[sort_by]]  # type: ignore[attr-defined] # "object" has no attribute "__iter__"; maybe "__dir__" or "__str__"? (not iterable)
    else:
        sort_columns = [c.asc() for c in sort_options[sort_by]]  # type: ignore[attr-defined] # "object" has no attribute "__iter__"; maybe "__dir__" or "__str__"? (not iterable)
    return base_query.order_by(*sort_columns)


def _apply_filter(base_query: Query, filters: dict[str, List]) -> Query:
    if filters.get("status"):
        base_query = base_query.filter(
            TreatmentProcedure.status.in_(filters["status"]),
        )
    if filters.get("clinic_id"):
        base_query = base_query.filter(
            TreatmentProcedure.fertility_clinic_id.in_(filters["clinic_id"]),
        )
    if filters.get("clinic_location_id"):
        base_query = base_query.filter(
            TreatmentProcedure.fertility_clinic_location_id.in_(
                filters["clinic_location_id"]
            ),
        )
    return base_query


def _get_paginated_treatment_procedures_with_count(
    clinic_ids: List[int],
    limit: Optional[int],
    offset: int,
    sort_by: Optional[AggregateProceduresSortByEnum],
    order_direction: Optional[OrderDirectionsEnum],
    filters: dict[str, List],
) -> Tuple[List[TreatmentProcedure], int]:
    base_query = (
        TreatmentProcedure.query.join(TreatmentProcedure.user)
        .join(TreatmentProcedure.fertility_clinic)
        .join(TreatmentProcedure.fertility_clinic_location)
        .filter(
            TreatmentProcedure.fertility_clinic_id.in_(clinic_ids),
            TreatmentProcedure.status != TreatmentProcedureStatus.PARTIALLY_COMPLETED,
            TreatmentProcedure.global_procedure_id != "",
        )
    )

    base_query = _apply_sort(base_query, sort_by, order_direction)
    base_query = _apply_filter(base_query, filters)

    total_count = base_query.count()

    paginated_treatment_procedures = (
        base_query.limit(limit).offset(offset).all()
        if limit is not None
        else base_query.all()
    )

    return paginated_treatment_procedures, total_count


class FertilityClinicAggregateProceduresResource(ClinicAuthorizedResource):
    def get(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        fc_user = self.current_user

        if fc_user.role != ROLES.fertility_clinic_billing_user:
            abort(401, message="Unauthorized")

        clinics_for_user = fc_user.clinics
        if len(clinics_for_user) == 0:
            return jsonify({"total_count": 0, "procedures": []})

        try:
            args = FertilityClinicAggregateProceduresGetSchema().load(request.args)
        except ValidationError as e:
            abort(400, message=str("; ".join(e.messages)))

        # todo: change default to 10 after the frontend API call has been updated to include pagination query params
        limit = args.get("limit", None)
        if limit is not None:
            limit = int(limit)
        offset = int(args.get("offset", 0))

        sort_by, order_direction = _get_order_direction_and_sort_by_from_args(args)

        filters = _get_filters_from_args(args)

        clinic_ids = [clinic.id for clinic in clinics_for_user]

        (
            paginated_treatment_procedures,
            total_count,
        ) = _get_paginated_treatment_procedures_with_count(
            clinic_ids, limit, offset, sort_by, order_direction, filters
        )

        all_members = [
            procedure.user
            for procedure in paginated_treatment_procedures
            if procedure.user is not None
        ]

        mapped_global_procedures = get_mapped_global_procedures(
            paginated_treatment_procedures
        )
        if mapped_global_procedures is None:
            return jsonify({"total_count": total_count, "procedures": []})

        treatment_procedures_schema = TreatmentProcedureSchema(
            exclude=("global_procedure", "partial_procedure")
        )
        global_procedures_schema = FertilityClinicProceduresSchema()
        aggregate_procedure_schema = FertilityClinicAggregateProcedureSchema()

        wallet_info_dict = {}
        response = []

        # transform procedure data
        for procedure in paginated_treatment_procedures:
            member: User | None = next(
                (m for m in all_members if m.id == procedure.member_id), None
            )

            if member is None:
                continue

            mb_repo = MemberBenefitRepository()
            member_benefit_id = mb_repo.get_member_benefit_id(user_id=member.id)

            # Check if wallet info is already fetched for this member
            if procedure.reimbursement_wallet_id not in wallet_info_dict:
                wallet_info_dict[
                    procedure.reimbursement_wallet_id
                ] = get_wallet_state_and_benefit_type_and_e9y_dates(
                    procedure.reimbursement_wallet_id, procedure.member_id
                )
            wallet_info = wallet_info_dict[procedure.reimbursement_wallet_id]

            benefit_type = wallet_info["benefit_type"]
            wallet_state = wallet_info["wallet_state"]
            benefit_start_date = wallet_info["benefit_start_date"]
            benefit_expires_date = wallet_info["benefit_expires_date"]

            formatted_member_birthday = (
                member.health_profile.birthday.isoformat()
                if member.health_profile.birthday
                else None
            )

            # transform data for partial procedure if treatment procedure has one
            returned_partial = None
            if procedure.partial_procedure:
                partial_procedure = procedure.partial_procedure
                partial_global_procedure = mapped_global_procedures.get(
                    partial_procedure.global_procedure_id
                )
                returned_partial = treatment_procedures_schema.dump(partial_procedure)
                returned_partial.update(
                    {
                        "global_procedure": global_procedures_schema.dump(
                            partial_global_procedure
                        )
                    }
                )

            aggregate_procedure = aggregate_procedure_schema.dump(procedure)

            # Update to include global procedure data
            global_procedure = mapped_global_procedures.get(
                procedure.global_procedure_id
            )
            aggregate_procedure.update(
                {"global_procedure": global_procedures_schema.dump(global_procedure)}
            )

            aggregate_procedure.update(
                {
                    "fertility_clinic_name": procedure.fertility_clinic.name,
                    "fertility_clinic_location_name": procedure.fertility_clinic_location.name,
                    "fertility_clinic_location_address": procedure.fertility_clinic_location.address_1,
                    "member_id": procedure.member_id,
                    "member_first_name": member.first_name,
                    "member_last_name": member.last_name,
                    "member_date_of_birth": formatted_member_birthday,
                    "benefit_id": member_benefit_id,
                    "benefit_type": benefit_type,
                    "wallet_state": wallet_state,
                    "benefit_start_date": benefit_start_date,
                    "benefit_expires_date": benefit_expires_date,
                }
            )

            response.append(aggregate_procedure)

        return jsonify({"total_count": total_count, "procedures": response})
