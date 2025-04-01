import datetime

import dateparser
from flask import flash

from authn.models.user import User
from data_admin.maker_base import _MakerBase
from data_admin.makers.wallet import ReimbursementOrganizationSettingsMaker
from models.enterprise import Organization
from payer_accumulator.helper_functions import get_payer_id
from storage.connection import db
from wallet.models.constants import (
    FamilyPlanType,
    MemberHealthPlanPatientRelationship,
    MemberHealthPlanPatientSex,
    WalletState,
)
from wallet.models.reimbursement_organization_settings import (
    EmployerHealthPlan,
    ReimbursementOrganizationSettings,
)
from wallet.models.reimbursement_wallet import MemberHealthPlan, ReimbursementWallet


class EmployerHealthPlanMaker(_MakerBase):
    def create_object(self, spec):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        required_params = [
            "start_date",
            "end_date",
            "payer",
            "ind_deductible_limit",
            "ind_oop_max_limit",
            "fam_deductible_limit",
            "fam_oop_max_limit",
        ]

        missing_params = []
        for param in required_params:
            val = spec.get(param)
            if val is None:
                missing_params.append(param)

        if missing_params:
            raise ValueError(f"Missing param(s): {missing_params}")

        if user_email := spec.get("user_email"):
            org_setting = self.org_settings_from_user(user_email)
        elif organization_name := spec.get("organization"):
            org_setting = (
                ReimbursementOrganizationSettings.query.join(
                    ReimbursementOrganizationSettings.organization
                )
                .filter(Organization.name == organization_name)
                .one()
            )
        else:
            raise ValueError("Please provide a user_email or organization.")

        formatted_start_date = datetime.datetime.fromisoformat(spec.get("start_date"))
        formatted_end_date = datetime.datetime.fromisoformat(spec.get("end_date"))

        payer = spec.get("payer")
        payer_id = get_payer_id(payer_name=payer)

        name = spec.get("name", "")

        existing_health_plan = EmployerHealthPlan.query.filter(
            EmployerHealthPlan.reimbursement_org_settings_id == org_setting.id,
            EmployerHealthPlan.benefits_payer_id == payer_id,
            EmployerHealthPlan.name == name,
        ).one_or_none()
        if existing_health_plan:
            flash(
                f"Employer Health Plan '{name}' for Org <{org_setting.id}> and Payer <{payer_id}> already exists.",
                "info",
            )
            return existing_health_plan

        employer_health_plan = EmployerHealthPlan(
            name=name,
            reimbursement_org_settings_id=org_setting.id,
            start_date=formatted_start_date,
            end_date=formatted_end_date,
            ind_deductible_limit=spec.get("ind_deductible_limit"),
            ind_oop_max_limit=spec.get("ind_oop_max_limit"),
            fam_deductible_limit=spec.get("fam_deductible_limit"),
            fam_oop_max_limit=spec.get("fam_oop_max_limit"),
            carrier_number=spec.get("carrier_number", "98765"),
            benefits_payer_id=payer_id,
            is_deductible_embedded=spec.get("is_deductible_embedded", True),
            is_oop_embedded=spec.get("is_oop_embedded", False),
            rx_integrated=spec.get("rx_integrated", True),
            group_id=spec.get("group_id", None),
        )
        db.session.add(employer_health_plan)
        db.session.flush()
        return employer_health_plan

    @staticmethod
    def org_settings_from_user(user_email: str) -> ReimbursementOrganizationSettings:
        user = User.query.filter_by(email=user_email).one_or_none()
        if user is None:
            raise ValueError(f"No user found for email: {user_email}.")
        wallet = ReimbursementWallet.query.filter_by(user_id=user.id).one_or_none()

        user_needs_wallet = wallet is None and user
        if user_needs_wallet:
            org_name = "Wayne Enterprises LLC"
            org_settings_spec = {
                "organization": org_name,
                "started_at": "90 days ago",
                "wallets": [{"organization": org_name, "member": user.email}],
            }
            ReimbursementOrganizationSettingsMaker().create_object_and_flush(
                spec=org_settings_spec
            )
            wallet = ReimbursementWallet.query.filter_by(user_id=user.id).one_or_none()
            flash(f"Wallet {wallet.id} created for user `{user_email}`")  # noqa W604

        return wallet.reimbursement_organization_settings


class MemberHealthPlanMaker(_MakerBase):
    def create_object(self, spec):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        required_params = [
            "user_email",
            "subscriber_insurance_id",
            "subscriber_first_name",
            "subscriber_last_name",
            "subscriber_date_of_birth",
            "patient_first_name",
            "patient_last_name",
            "patient_date_of_birth",
            "patient_sex",
            "patient_relationship",
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

        wallet = ReimbursementWallet.query.filter(
            ReimbursementWallet.user_id == user.id,
            ReimbursementWallet.state == WalletState.QUALIFIED,
        ).one_or_none()

        if employer_health_plan_id := spec.get("employer_health_plan_id"):
            employer_plan = EmployerHealthPlan.query.filter_by(
                id=employer_health_plan_id
            ).one_or_none()
            if employer_plan is None:
                raise ValueError(
                    f"No employer health plan found for id: {employer_health_plan_id}."
                )
        elif employer_health_plan_name := spec.get("employer_health_plan_name"):
            employer_plan = EmployerHealthPlan.query.filter(
                EmployerHealthPlan.name == employer_health_plan_name,
                EmployerHealthPlan.reimbursement_org_settings_id
                == wallet.reimbursement_organization_settings_id,
            ).one_or_none()
            if employer_plan is None:
                raise ValueError(
                    f"No employer health plan found for id: {employer_health_plan_id}."
                )
        else:
            employer_plan = EmployerHealthPlan.query.filter(
                EmployerHealthPlan.reimbursement_org_settings_id
                == wallet.reimbursement_organization_settings_id
            ).first()
        if employer_plan is None:
            raise ValueError(f"No employer health plan found for wallet: {wallet}.")

        existing_health_plan = MemberHealthPlan.query.filter(
            MemberHealthPlan.reimbursement_wallet_id == wallet.id,
            MemberHealthPlan.member_id == user.id,
        ).one_or_none()
        if existing_health_plan:
            flash(
                f"Member Health Plan for wallet <{wallet.id}> and user <{user.id}> already exists.",
                "info",
            )
            return existing_health_plan

        member_health_plan = MemberHealthPlan(
            employer_health_plan_id=employer_plan.id,
            reimbursement_wallet_id=wallet.id,
            member_id=user.id,
            subscriber_insurance_id=spec.get("subscriber_insurance_id"),
            subscriber_first_name=spec.get("subscriber_first_name"),
            subscriber_last_name=spec.get("subscriber_last_name"),
            subscriber_date_of_birth=dateparser.parse(
                spec.get("subscriber_date_of_birth")
            )
            if spec.get("subscriber_date_of_birth")
            else None,
            patient_first_name=spec.get("patient_first_name"),
            patient_last_name=spec.get("patient_last_name"),
            patient_date_of_birth=dateparser.parse(spec.get("patient_date_of_birth"))
            if spec.get("patient_date_of_birth")
            else None,
            patient_sex=MemberHealthPlanPatientSex(
                spec.get("patient_sex").upper()
            ).value,
            patient_relationship=MemberHealthPlanPatientRelationship(
                spec.get("patient_relationship").upper()
            ).value,
            plan_type=FamilyPlanType.INDIVIDUAL,
            plan_start_at=spec.get(
                "plan_start_at",
                datetime.datetime.combine(employer_plan.start_date, datetime.time()),
            ),
            plan_end_at=spec.get(
                "plan_end_at",
                datetime.datetime.combine(employer_plan.end_date, datetime.time()),
            ),
        )

        db.session.add(member_health_plan)
        return member_health_plan
