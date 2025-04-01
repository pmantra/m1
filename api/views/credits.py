from flask_restful import abort
from marshmallow_v1 import Schema, fields

from appointments.models.payments import Credit
from common.services.api import AuthenticatedResource
from views.schemas.common import MavenDateTime, PaginableOutputSchema


class CreditSchema(Schema):
    amount = fields.Decimal(as_string=True)
    expires_at = MavenDateTime()
    created_at = MavenDateTime()


class CreditMetaSchema(Schema):
    total_credit = fields.Decimal(as_string=True)


class CreditsSchema(PaginableOutputSchema):
    data = fields.Nested(CreditSchema, many=True)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Nested", base class "PaginableOutputSchema" defined the type as "Raw")
    meta = fields.Nested(CreditMetaSchema)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Nested", base class "PaginableOutputSchema" defined the type as "Raw")


class UserCreditsResource(AuthenticatedResource):
    def get(self, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if not user_id == self.user.id:
            abort(403, message="Only view your own credits!")

        credits = Credit.available_for_user(self.user)
        credits.order_by(Credit.expires_at.desc())
        credits = credits.all()

        schema = CreditsSchema()
        data = {
            "data": credits,
            "meta": {"total_credit": sum([c.amount for c in credits])},
            "pagination": {"total": len(credits)},
        }
        return schema.dump(data).data
