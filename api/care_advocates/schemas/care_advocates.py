import datetime
from typing import Dict, List

from marshmallow import Schema, ValidationError, fields

from authn.models.user import User
from care_advocates.services.care_advocate import CareAdvocateService
from models.products import Product
from models.verticals_and_specialties import CX_VERTICAL_NAME, Vertical
from storage.connection import db
from views.schemas.common_v3 import CSVIntegerField, MavenDateTime


class PooledAvailabilityInvalidCAsException(ValidationError):
    def __init__(self) -> None:
        super().__init__(message="ca_ids do not correspond to existing Care Advocates")


def validate_ca_ids(ca_ids):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if not CareAdvocateService().is_valid_list_cas_ids(ca_ids):
        raise PooledAvailabilityInvalidCAsException()


class PooledAvailabilityArgsSchema(Schema):
    start_at = MavenDateTime(required=True)
    end_at = MavenDateTime(required=True)
    ca_ids = CSVIntegerField(required=True, validate=validate_ca_ids)


class PooledAvailabilityResponseSchema(Schema):
    care_advocates_pooled_availability = fields.Method(
        "get_care_advocates_pooled_availability"
    )

    def get_care_advocates_pooled_availability(
        self, pooled_availability_dict: Dict[datetime.datetime, List[int]]
    ) -> List[Dict]:
        # Returns: [{start_time: < date_time >, ca_ids: [ < id >]}]}
        pooled_availability_list = [
            {
                "start_time": timeslot_start.strftime("%Y-%m-%d %H:%M"),
                "ca_ids": ca_ids,
            }
            for timeslot_start, ca_ids in pooled_availability_dict.items()
        ]
        return pooled_availability_list


class CareAdvocateAssignmentInvalidMemberException(ValidationError):
    def __init__(self) -> None:
        super().__init__(message="member_id does not correspond to existing member")


def validate_member_id(member_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if not CareAdvocateService().is_valid_user_id(member_id):
        raise CareAdvocateAssignmentInvalidMemberException()


class CareAdvocateAssignmentArgsSchema(Schema):
    member_id = fields.Integer(required=True, validate=validate_member_id)
    ca_ids = fields.List(fields.Int(), required=True, validate=validate_ca_ids)


class CareAdvocateAssignmentResponseSchema(Schema):
    """
    Returns:
    assigned_care_advocate = {
        "assigned_care_advocate": {
            "id": <ca_id>,
            "first_name": <first_name>,
            "image_url": <image_url>,
            "products": [
                {"product_id": <product_id>, "is_intro_appointment_product": <bool>}
            ],
        }
    }
    """

    assigned_care_advocate = fields.Method("get_assigned_care_advocate")

    def get_assigned_care_advocate(self, care_advocate_id: int) -> Dict:
        prac = User.query.get(care_advocate_id)
        product = (
            db.session.query(Product)
            .join(Vertical, Product.vertical_id == Vertical.id)
            .filter(
                Product.user_id == care_advocate_id, Vertical.name == CX_VERTICAL_NAME
            )
            .first()
        )

        product_data = {"product_id": product.id, "is_intro_appointment_product": True}
        prac_data = {
            "id": prac.id,
            "first_name": prac.first_name,
            "image_url": prac.avatar_url,
            "products": [product_data],
        }

        return prac_data


class SearchArgsSchema(Schema):
    member_id = fields.Integer(required=True)
    use_preferred_language = fields.Boolean(required=False)
    availability_before = fields.AwareDateTime(required=False)


class SearchResponseSchema(Schema):
    care_advocate_ids = fields.List(fields.Integer())
    soonest_next_availability = fields.AwareDateTime()
