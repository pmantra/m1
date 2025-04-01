from flask import flash

from authn.models.user import User
from cost_breakdown.models.cost_breakdown import CostBreakdown
from data_admin.maker_base import _MakerBase
from data_admin.makers.mmb import TreatmentProcedureMaker
from data_admin.makers.organization import OrganizationMaker
from data_admin.makers.wallet import (
    ReimbursementOrganizationSettingsMaker,
    ReimbursementRequestMaker,
)
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedure,
)
from storage.connection import db
from wallet.models.reimbursement_wallet import ReimbursementWallet


class CostBreakdownMaker(_MakerBase):
    def create_object(self, spec):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        required_params = [
            "user_email",
        ]

        missing_params = []
        for param in required_params:
            val = spec.get(param)
            if val is None:
                missing_params.append(param)

        if missing_params:
            raise ValueError(f"Missing param(s): {missing_params}")

        user_email = spec.get("user_email")
        user = User.query.filter_by(email=user_email).one_or_none()

        if user is None:
            raise ValueError(f"No user found for email: {user_email}.")

        wallet = ReimbursementWallet.query.filter_by(user_id=user.id).one_or_none()
        if wallet is None:
            org_name = "Wayne Enterprises LLC"
            # create organization
            org_maker = OrganizationMaker()
            org_maker.create_object_and_flush({"name": org_name})
            org_settings_spec = {
                "organization": org_name,
                "started_at": "90 days ago",
                "wallets": [{"organization": org_name, "member": user.email}],
                "categories": [
                    {
                        "organization": org_name,
                        "label": "Fertility",
                        "reimbursement_request_category_maximum": 10_000_00,
                    }
                ],
            }
            ReimbursementOrganizationSettingsMaker().create_object_and_flush(
                spec=org_settings_spec
            )
            wallet = ReimbursementWallet.query.filter_by(user_id=user.id).one_or_none()
            flash(f"Wallet {wallet.id} created for user `{user_email}`")  # noqa W604

        procedure_id = spec.get("treatment_procedure_id")
        procedure = TreatmentProcedure.query.filter_by(id=procedure_id).one_or_none()
        reimbursement_request = None
        if procedure is None:
            if spec.get("reimbursement_requests"):
                for rr_spec in spec.get("reimbursement_requests"):
                    reimbursement_request = (
                        ReimbursementRequestMaker().create_object_and_flush(
                            spec=rr_spec, wallet=wallet
                        )
                    )
                    flash(
                        f"Reimbursement Request {reimbursement_request.id} created for user {user_email}"
                    )
            if spec.get("treatment_procedures"):
                for tp in spec.get("treatment_procedures"):
                    procedure = TreatmentProcedureMaker().create_object_and_flush(tp)
                    flash(
                        f"Treatment Procedure {procedure.id} created for user {user_email}"
                    )

        db.session.flush()
        cost_breakdown = CostBreakdown(
            treatment_procedure_uuid=procedure.uuid if procedure else None,
            reimbursement_request_id=reimbursement_request.id
            if reimbursement_request
            else None,
            wallet_id=wallet.id,
            total_member_responsibility=spec.get("total_member_responsibility", 100),
            total_employer_responsibility=spec.get("total_employer_responsibility", 0),
            beginning_wallet_balance=spec.get("beginning_wallet_balance", 0),
            ending_wallet_balance=spec.get("ending_wallet_balance", 0),
            deductible=spec.get("deductible", 100),
            copay=spec.get("copay", 0),
            oop_applied=spec.get("oop_applied", 100),
            deductible_remaining=spec.get("deductible_remaining", 0),
            oop_remaining=spec.get("oop_remaining", 2000),
            hra_applied=spec.get("hra_applied", None),
        )
        db.session.add(cost_breakdown)
        db.session.flush()

        if procedure:
            procedure.cost_breakdown_id = cost_breakdown.id
            db.session.add(procedure)
            db.session.flush()

        return cost_breakdown
