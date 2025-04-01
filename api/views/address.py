import pycountry
from flask import request
from flask_restful import abort
from marshmallow import Schema, ValidationError, fields, validates_schema

from common.services.api import PermissionedUserResource
from models.profiles import Address
from storage.connection import db
from views.schemas.common_v3 import V3AddressSchema


class AddressSchemaV2(Schema):
    address_1 = fields.String(required=True)
    address_2 = fields.String()
    city = fields.String(required=True)
    state = fields.String(required=True)
    country = fields.String(required=True)
    zip_code = fields.String(required=True)

    @validates_schema
    def validate_country_state(self, data, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        state = data.get("state")
        country = data.get("country")

        if not country:
            return True

        if not pycountry.countries.get(alpha_2=country):
            raise ValidationError(f"{country} is not a valid country code!")

        if country == "US" and not pycountry.subdivisions.get(
            code=f"{country}-{state}"
        ):
            raise ValidationError(f"{state} is not a valid US state!")
        return True


class AddressResource(PermissionedUserResource):
    def post(self, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self._user_or_404(user_id)
        schema = AddressSchemaV2()

        try:
            data = schema.load(request.json if request.is_json else {})
        except ValidationError as e:
            abort(400, message=e.messages)

        if data.get("address_2"):
            street_address = f'{data["address_1"]} {data["address_2"]}'
        else:
            street_address = data["address_1"]

        data_obj = {
            "user_id": user_id,
            "street_address": street_address,
            "city": data["city"],
            "state": data["state"],
            "country": data["country"],
            "zip_code": data["zip_code"],
        }

        newAddress = Address(**data_obj)

        db.session.add(newAddress)
        db.session.commit()

        return None, 201

    def get(self, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        schema = V3AddressSchema()
        addresses = schema.dump(
            db.session.query(Address).filter(Address.user_id == user_id).all(),
            many=True,
        )
        return addresses
