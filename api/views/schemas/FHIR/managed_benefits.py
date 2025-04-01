from marshmallow import Schema, fields

from wallet.models.models import MemberTypeDetails


class ManagedBenefitsInfoSchema(Schema):
    member_type = fields.Function(
        lambda obj: obj.member_type.name
        if obj and hasattr(obj, "member_type")
        else None
    )

    gold_eligible = fields.Method("get_gold_eligible")

    def get_gold_eligible(self, obj: MemberTypeDetails) -> bool:
        if obj and hasattr(obj, "flags"):
            flags_obj = obj.flags
            if (
                flags_obj
                and hasattr(flags_obj, "wallet_organization")
                and hasattr(flags_obj, "direct_payment")
            ):
                # This is the same logic used in api/admin/templates/member_profile_edit_template.html
                # to show "potentially gold eligible" in admin
                return flags_obj.wallet_organization and flags_obj.direct_payment
        return False
