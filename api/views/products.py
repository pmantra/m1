from flask import request
from httpproblem import Problem
from marshmallow_v1 import Schema, fields
from maven import feature_flags
from sqlalchemy.orm import load_only

from authn.models.user import User
from common.services.api import AuthenticatedResource
from models.products import Product
from models.verticals_and_specialties import Vertical
from storage.connection import db
from utils import launchdarkly
from utils.log import logger
from views.schemas.common import CSVIntegerField, PaginableOutputSchema
from views.schemas.products_v3 import ProductsGetArgsV3, ProductsSchemaV3

log = logger(__name__)


class ProductSimpleSchema(Schema):
    id = fields.Integer()
    minutes = fields.Integer()
    price = fields.Decimal(as_string=True)
    practitioner_id = fields.Integer(attribute="user_id")


class ProductsSchema(PaginableOutputSchema):
    data = fields.Nested(ProductSimpleSchema, many=True)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Nested", base class "PaginableOutputSchema" defined the type as "Raw")


class ProductsGetArgs(Schema):
    practitioner_ids = CSVIntegerField(required=True)
    vertical_name = fields.String()


class PractitionerProductsResource(AuthenticatedResource):
    @property
    def launchdarkly_context(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return launchdarkly.marshmallow_context(self.user.esp_id, self.user.email)

    def get(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation

        experiment_enabled = feature_flags.bool_variation(
            "experiment-marshmallow-practitioner-products-upgrade",
            self.launchdarkly_context,
            default=False,
        )
        schema = ProductsGetArgs() if not experiment_enabled else ProductsGetArgsV3()
        args = (
            schema.load(request.args).data  # type: ignore[attr-defined] # "object" has no attribute "load"
            if not experiment_enabled
            else schema.load(request.args)  # type: ignore[attr-defined] # "object" has no attribute "load"
        )

        if not args.get("practitioner_ids"):
            raise Problem(400, detail="Missing practitioners!")

        practitioner_ids = args["practitioner_ids"]

        practitioners = User.query.filter(User.id.in_(args["practitioner_ids"])).all()
        if any(p.is_care_coordinator for p in practitioners):
            if self.user.is_enterprise or self.user.is_care_coordinator:
                log.debug("Allowing %s to get care coordinator products", self.user)
            else:
                schema = ProductsSchema()
                return schema.dump({"data": []}).data

        base_products = db.s_replica1.query(Product).filter(
            Product.is_active == True, Product.user_id.in_(practitioner_ids)
        )

        vertical_name = args.get("vertical_name")
        if vertical_name:
            vertical = (
                Vertical.query.filter(Vertical.name == vertical_name).options(
                    load_only("id")
                )
            ).one_or_none()
            vertical_id = vertical and vertical.id
            base_products = base_products.filter(Product.vertical_id == vertical_id)

        products = base_products.all()
        Product.sort_products_by_price(products)

        schema = ProductsSchema() if not experiment_enabled else ProductsSchemaV3()
        return (
            schema.dump({"data": products}).data  # type: ignore[attr-defined] # "object" has no attribute "dump"
            if not experiment_enabled
            else schema.dump({"data": products})  # type: ignore[attr-defined] # "object" has no attribute "dump"
        )
