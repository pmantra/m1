from functools import wraps

from flask import request
from flask_restful import abort

from common.services.api import (
    _USER_ID_HEADER,
    _VIEW_AS_HEADER,
    AuthenticatedResource,
    is_path_allowed_view_as,
)
from direct_payment.clinic.repository.user import FertilityClinicUserRepository
from utils.log import logger

log = logger(__name__)


class ClinicAuthorizedResource(AuthenticatedResource):
    """
    Clinic resources should inherit from this class to ensure that accessing users are FC users
    """

    def __init__(self) -> None:
        super().__init__()
        self.method_decorators = super().method_decorators + [self.clinic_authorized]
        self.repository = FertilityClinicUserRepository()

    def _get_fc_user_profile(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        user_id_str = request.headers.get(_USER_ID_HEADER)
        user_id = None
        if user_id_str and user_id_str.isdigit():
            user_id = int(user_id_str)
        view_as_str = request.headers.get(_VIEW_AS_HEADER)

        if view_as_str and view_as_str.isdigit():
            view_as_log = f"_get_fc_user_profile view as query: user_id {user_id_str} view_as {view_as_str} on {request.path}"
            if request.method == "GET" and is_path_allowed_view_as(request.path):
                log.warning(f"Accepted, {view_as_log}")
                user_id = int(view_as_str)
            else:
                log.warning(f"Rejected, {view_as_log}")

        if user_id:
            user = self.repository.get_by_user_id(user_id=user_id)
            self.current_user = user
            return user

    def clinic_authorized(self, func):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """
        Checks to see if the user is authorized to perform actions related to clinic functions
        """

        @wraps(func)
        def wrapper(*args, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
            fc_user = self._get_fc_user_profile()
            if fc_user and fc_user.active:
                log.info(
                    "clinic portal check authorization",
                    user_id=str(fc_user.id),
                    is_clinic_user=str(True),
                    is_active=str(True),
                    email_domain=str(fc_user.email_domain),
                )
                return func(*args, **kwargs)
            log.info(
                "clinic portal check authorization",
                user_id=str(fc_user.id if fc_user else None),
                is_clinic_user=(True if fc_user is not None else False),
                is_active=str(None),
                email_domain=str(fc_user.email_domain if fc_user else None),
            )
            abort(401, message="Unauthorized")

        return wrapper


class ClinicCheckAccessResource(ClinicAuthorizedResource):
    def get(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        """
        The decorator from the super class will determine whether or not the user has access.
        """
        return None, 204
