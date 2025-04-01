from marshmallow import Schema, fields


class WalletInfoSchema(Schema):
    offered_by_org = fields.Method("get_offered_by_org")

    member_status = fields.Function(
        lambda x: x.state.value if x and getattr(x, "state", None) else None
    )

    def get_offered_by_org(self, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if obj and obj.reimbursement_organization_settings:
            if hasattr(obj.reimbursement_organization_settings, "is_active"):
                return obj.reimbursement_organization_settings.is_active
            else:
                return any(
                    setting.is_active
                    for setting in obj.reimbursement_organization_settings
                )
        return False
