import datetime

import dateparser
from flask import flash, request

from authn.models.user import User
from data_admin.maker_base import _MakerBase
from data_admin.makers.payer_accumulation import AccumulationMappingMaker
from data_admin.makers.user import _add_a_user
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureType,
)
from eligibility import service as e9y_service
from models.enterprise import Organization
from models.marketing import Resource, ResourceContentTypes, ResourceTypes
from payer_accumulator.accumulation_mapping_service import AccumulationMappingService
from storage.connection import db
from wallet.models.constants import (
    AlegeusCoverageTier,
    CostSharingCategory,
    PlanType,
    ReimbursementRequestExpenseTypes,
    WalletState,
    WalletUserStatus,
    WalletUserType,
)
from wallet.models.reimbursement import (
    ReimbursementAccountType,
    ReimbursementPlan,
    ReimbursementRequest,
    ReimbursementRequestCategory,
    ReimbursementWalletPlanHDHP,
)
from wallet.models.reimbursement_organization_settings import (
    ReimbursementOrganizationSettings,
    ReimbursementOrgSettingCategoryAssociation,
)
from wallet.models.reimbursement_request_source import ReimbursementRequestSource
from wallet.models.reimbursement_wallet import CountryCurrencyCode, ReimbursementWallet
from wallet.models.reimbursement_wallet_user import ReimbursementWalletUsers
from wallet.services.reimbursement_wallet_state_change import handle_wallet_state_change


class ReimbursementOrganizationSettingsMaker(_MakerBase):
    def create_object(self, spec):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        organization = Organization.query.filter_by(
            name=spec.get("organization")
        ).first()
        settings = (
            ReimbursementOrganizationSettings.query.join(Organization)
            .filter(Organization.name == spec.get("organization"))
            .first()
        )
        if settings:
            flash(
                f"Org setting already exists for org <{spec.get('organization')}>",
                "info",
            )
            return settings

        resource_overview = Resource.query.filter_by(
            title="Maven Wallet Details Resource"
        ).first()
        if resource_overview is None:
            resource_overview = Resource(
                resource_type=ResourceTypes.ENTERPRISE,
                content_type=ResourceContentTypes.article.name,
                published_at=datetime.datetime.utcnow(),
                body="Organization Benefit Details",
                title="Maven Wallet Details Resource",
                subhead="Resource Subheading",
            )
        resource_faq = Resource.query.filter_by(
            title="Maven Wallet FAQ Resource"
        ).first()
        if resource_faq is None:
            resource_faq = Resource(
                resource_type=ResourceTypes.ENTERPRISE,
                content_type=ResourceContentTypes.article.name,
                published_at=datetime.datetime.utcnow(),
                body="Organization Benefit FAQ",
                title="Maven Wallet FAQ Resource",
                subhead="Resource Subheading",
            )
        settings = ReimbursementOrganizationSettings(
            organization=organization,
            benefit_overview_resource=resource_overview,
            benefit_faq_resource=resource_faq,
            survey_url="https://fake.url",
            debit_card_enabled=spec.get("debit_card_enabled"),
            direct_payment_enabled=spec.get("direct_payment_enabled"),
            rx_direct_payment_enabled=spec.get("rx_direct_payment_enabled"),
            deductible_accumulation_enabled=spec.get("deductible_accumulation_enabled"),
            closed_network=spec.get("closed_network"),
            fertility_requires_diagnosis=spec.get("fertility_requires_diagnosis"),
            fertility_allows_taxable=spec.get("fertility_allows_taxable"),
            started_at=dateparser.parse(spec.get("started_at")),
            ended_at=(
                None
                if spec.get("ended_at") is None
                else dateparser.parse(spec.get("ended_at"))
            ),
        )
        db.session.add(settings)
        db.session.flush()
        if "categories" in spec and isinstance(spec["categories"], list):
            for category_spec in spec.get("categories"):
                ReimbursementCategoryMaker().create_object_and_flush(
                    category_spec, settings
                )
        if "wallets" in spec and isinstance(spec["wallets"], list):
            for wallet_spec in spec.get("wallets"):
                ReimbursementWalletMaker().create_object_and_flush(
                    wallet_spec, settings
                )
        return settings


class ReimbursementRequestMaker(_MakerBase):
    def create_object(self, spec, wallet=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if wallet is None and spec.get("member") and spec.get("organization"):
            wallet = (
                ReimbursementWallet.query.join(
                    User, ReimbursementOrganizationSettings, Organization
                )
                .filter(
                    User.email == spec.get("member"),
                    Organization.name == spec.get("organization"),
                )
                .first()
            )
        if wallet is None:
            label = spec.get("label")
            raise ValueError(
                f"Reimbursement Request {label} missing associated wallet information.",
                "error",
            )
        category_label = spec.get("category")
        category = (
            ReimbursementRequestCategory.query.join(
                ReimbursementOrgSettingCategoryAssociation,
                ReimbursementOrgSettingCategoryAssociation.reimbursement_request_category_id
                == ReimbursementRequestCategory.id,
            )
            .filter(
                ReimbursementRequestCategory.label == category_label,
                ReimbursementOrgSettingCategoryAssociation.reimbursement_organization_settings_id
                == wallet.reimbursement_organization_settings_id,
            )
            .first()
        )
        if category is None:
            raise ValueError(
                f"Reimbursement Request could not find category {category_label}.",
                "error",
            )
        r_request = ReimbursementRequest(
            label=spec.get("label"),
            description=spec.get("description"),
            service_provider=spec.get("service_provider"),
            person_receiving_service=spec.get("person_receiving_service"),
            person_receiving_service_id=wallet.member.id,
            amount=spec.get("amount"),
            state=spec.get("state"),
            category=category,
            sources=[ReimbursementRequestSource(reimbursement_wallet_id=wallet.id)],
            wallet=wallet,
            reimbursement_request_category_id=category.id,
            service_start_date=datetime.datetime.now()
            if dateparser.parse(spec.get("service_start_date")) is None
            else dateparser.parse(spec.get("service_start_date")),
            service_end_date=(
                None
                if spec.get("service_end_date") is None
                else dateparser.parse(spec.get("service_end_date"))
            ),
            reimbursement_transfer_date=(
                None
                if spec.get("reimbursement_transfer_date") is None
                else dateparser.parse(spec.get("reimbursement_transfer_date"))
            ),
            reimbursement_payout_date=(
                None
                if spec.get("reimbursement_payout_date") is None
                else dateparser.parse(spec.get("reimbursement_payout_date"))
            ),
            cost_sharing_category=CostSharingCategory(spec.get("cost_sharing_category"))
            if spec.get("cost_sharing_category")
            else None,
            procedure_type=spec.get("procedure_type"),
            cost_credit=spec.get("cost_credit"),
        )
        db.session.add(r_request)
        db.session.flush()
        if accumulation_mapping_spec := spec.get("accumulation_mapping"):
            payer = AccumulationMappingService(db.session).get_valid_payer(
                reimbursement_wallet_id=r_request.reimbursement_wallet_id,
                user_id=r_request.person_receiving_service_id,
                procedure_type=TreatmentProcedureType(r_request.procedure_type),
                effective_date=r_request.service_start_date,
            )
            AccumulationMappingMaker().create_object_and_flush(
                spec={
                    "reimbursement_request_id": r_request.id,
                    "treatment_accumulation_status": "PAID",
                    "completed_at": r_request.created_at,
                    "payer_id": payer.id,
                    "deductible": accumulation_mapping_spec.get("deductible"),
                    "oop_applied": accumulation_mapping_spec.get("oop_applied"),
                }
            )

        return r_request


class ReimbursementWalletMaker(_MakerBase):
    def create_object(  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self, spec, settings=None
    ):
        if settings is None and spec.get("organization"):
            settings = (
                ReimbursementOrganizationSettings.query.join(Organization)
                .filter(Organization.name == spec.get("organization"))
                .first()
            )
        if settings is None:
            member = spec.get("member")
            flash(
                f"Reimbursement wallet for {member} missing associated organization setting information.",
                "error",
            )
            return

        member = User.query.filter_by(email=spec.get("member")).one()
        if member is None:
            _add_a_user(
                {
                    "email": spec.get("member"),
                    "role": "member",
                    "organization_name": settings.organization.name,
                }
            )

        # avoid creating duplicate wallets here
        user_wallets = (
            ReimbursementWallet.query.join(
                ReimbursementWalletUsers,
                ReimbursementWalletUsers.reimbursement_wallet_id
                == ReimbursementWallet.id,
            )
            .filter(
                ReimbursementWalletUsers.user_id == member.id,
                ReimbursementWallet.state == WalletState(spec.get("state", "PENDING")),
                ReimbursementWallet.reimbursement_organization_settings_id
                == settings.id,
            )
            .all()
        )
        if user_wallets:
            flash(
                f"Reimbursement Wallet with state <{spec.get('state')}> for <{member.id}> and org <{spec.get('organization')}> already exists.",
                "info",
            )
            return user_wallets[0]

        # get verification from e9y service
        # _add_a_user will generate the verification, so we will always have verification in this context
        verification_service = e9y_service.get_verification_service()
        verifications = verification_service.get_all_verifications_for_user(
            user_id=member.id, organization_ids=[settings.organization_id]
        )
        verification = None if not verifications else verifications[0]
        eligibility_member_id = (
            None if not verification else verification.eligibility_member_id
        )
        eligibility_verification_id = (
            None if not verification else verification.verification_id
        )
        eligibility_member_2_id = (
            (None if not verification else verification.eligibility_member_2_id),
        )
        eligibility_member_2_version = (
            (None if not verification else verification.eligibility_member_2_version),
        )
        eligibility_verification_2_id = (
            (None if not verification else verification.verification_2_id),
        )

        primary_expense_type = spec.get("primary_expense_type", "FERTILITY")

        wallet = ReimbursementWallet(
            member=member,
            reimbursement_organization_settings=settings,
            state=WalletState.PENDING,
            initial_eligibility_member_id=eligibility_member_id,
            initial_eligibility_verification_id=(
                None if eligibility_member_id else eligibility_verification_id
            ),
            initial_eligibility_member_2_id=eligibility_member_2_id,
            initial_eligibility_member_2_version=eligibility_member_2_version,
            initial_eligibility_verification_2_id=eligibility_verification_2_id,
            primary_expense_type=ReimbursementRequestExpenseTypes(primary_expense_type),
        )
        wallet.note = spec.get("note") if spec.get("note") else ""
        db.session.add(wallet)
        db.session.flush()
        wallet_user = ReimbursementWalletUsers(
            reimbursement_wallet_id=wallet.id,
            user_id=member.id,
            type=WalletUserType.EMPLOYEE,
            status=WalletUserStatus.ACTIVE,
        )
        db.session.add(wallet_user)
        db.session.flush()
        if spec.get("reimbursement_wallet_hdhp_plan"):
            ReimbursementWalletPlanHDHPMaker().create_object_and_flush(
                spec.get("reimbursement_wallet_hdhp_plan"), wallet
            )

        # set the actual state after wallet creation to trigger any channel actions.
        if spec.get("state") in [
            name for name, member in WalletState.__members__.items()
        ]:
            wallet.state = WalletState[spec.get("state")]
        db.session.add(wallet)
        db.session.flush()
        handle_wallet_state_change(
            wallet, WalletState.PENDING, headers=request.headers  # type: ignore[arg-type] # Argument "headers" to "handle_wallet_state_change" has incompatible type "EnvironHeaders"; expected "Optional[Mapping[str, str]]"
        )
        if "reimbursement_requests" in spec and isinstance(
            spec["reimbursement_requests"], list
        ):
            for request_spec in spec["reimbursement_requests"]:
                ReimbursementRequestMaker().create_object_and_flush(
                    request_spec, wallet
                )
        return wallet


class ReimbursementCategoryMaker(_MakerBase):
    def create_object(  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self, spec, settings=None
    ):
        if settings is None and spec.get("organization"):
            settings = (
                ReimbursementOrganizationSettings.query.join(Organization)
                .filter(Organization.name == spec.get("organization"))
                .one_or_none()
            )
        if settings is None:
            label = spec.get("label")
            flash(
                f"Reimbursement category {label} missing associated organization setting information.",
                "error",
            )
            return
        category = ReimbursementRequestCategory.query.filter_by(
            label=spec.get("label")
        ).one_or_none()
        if category is None:
            category = ReimbursementRequestCategory(label=spec.get("label"))

            if "reimbursement_plan" in spec and isinstance(
                spec["reimbursement_plan"], dict
            ):
                reimbursement_plan_spec = spec.get("reimbursement_plan")
                plan = ReimbursementPlan.query.filter(
                    ReimbursementPlan.alegeus_plan_id
                    == reimbursement_plan_spec.get("alegeus_plan_id"),
                ).one_or_none()
                if plan is None:
                    alegeus_account_type = (
                        reimbursement_plan_spec.get("alegeus_account_type") or "HRA"
                    )
                    reimbursement_account_type = (
                        ReimbursementAccountType.query.filter_by(
                            alegeus_account_type=alegeus_account_type
                        ).one_or_none()
                    )

                    if not reimbursement_account_type:
                        reimbursement_account_type = ReimbursementAccountType(
                            alegeus_account_type=alegeus_account_type
                        )
                        db.session.add(reimbursement_account_type)

                    formatted_start_date = datetime.date.fromisoformat(
                        reimbursement_plan_spec.get("start_date") or "2020-01-01"
                    )
                    formatted_end_date = datetime.date.fromisoformat(
                        reimbursement_plan_spec.get("end_date") or "2099-12-31"
                    )
                    plan = ReimbursementPlan(
                        alegeus_plan_id=reimbursement_plan_spec.get("alegeus_plan_id"),
                        is_hdhp=reimbursement_plan_spec.get("is_hdhp") or False,
                        plan_type=reimbursement_plan_spec.get("plan_type")
                        or PlanType.LIFETIME,
                        start_date=formatted_start_date,
                        end_date=formatted_end_date,
                        reimbursement_account_type=reimbursement_account_type,
                    )
                    db.session.add(plan)
                category.reimbursement_plan = plan
            db.session.add(category)
            db.session.flush()
        association = ReimbursementOrgSettingCategoryAssociation.query.filter_by(
            reimbursement_request_category=category
        ).one_or_none()
        if association is None:
            assoc = ReimbursementOrgSettingCategoryAssociation(
                reimbursement_request_category=category,
                reimbursement_request_category_maximum=spec.get(
                    "reimbursement_request_category_maximum"
                ),
                reimbursement_organization_settings=settings,
            )
            db.session.add(assoc)
            db.session.flush()
        return category


class ReimbursementWalletPlanHDHPMaker(_MakerBase):
    def create_object(self, spec, wallet=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if wallet is None and spec.get("member") and spec.get("organization"):
            wallet = (
                ReimbursementWallet.query.join(
                    User, ReimbursementOrganizationSettings, Organization
                )
                .filter(
                    User.email == spec.get("member"),
                    Organization.name == spec.get("organization"),
                )
                .one_or_none()
            )
            if wallet is None:
                flash("Missing associated wallet information.", "error")
                return

        plan = ReimbursementPlan.query.filter_by(
            alegeus_plan_id=spec.get("alegeus_plan_id")
        ).one_or_none()

        if plan is None:
            reimbursement_account_type = ReimbursementAccountType.query.filter_by(
                alegeus_account_type="DTR"
            ).one_or_none()

            if not reimbursement_account_type:
                reimbursement_account_type = ReimbursementAccountType(
                    alegeus_account_type="DTR"
                )
                db.session.add(reimbursement_account_type)

            plan = ReimbursementPlan(
                reimbursement_account_type=reimbursement_account_type,
                is_hdhp=True,
                alegeus_plan_id=spec.get("alegeus_plan_id", "WYNLAPHDHP2022"),
                start_date=datetime.date.today().replace(month=1, day=1)
                - datetime.timedelta(weeks=42),
                end_date=datetime.date.today().replace(month=12, day=31)
                + datetime.timedelta(weeks=42),
            )
            db.session.add(plan)
            db.session.flush()
            flash(
                f"Created Reimbursement Plan {plan}",
                "success",
            )

        hdhp_plan = ReimbursementWalletPlanHDHP(
            reimbursement_plan=plan,
            wallet=wallet,
            alegeus_coverage_tier=AlegeusCoverageTier.SINGLE,
        )
        db.session.add(hdhp_plan)
        db.session.flush()
        flash(f"Created HDHP Wallet Plan {hdhp_plan}", "success")
        return hdhp_plan


class CountryCurrencyCodeMaker(_MakerBase):
    def create_object(self, spec):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        country_currency = CountryCurrencyCode.query.filter_by(
            country_alpha_2=spec.get("country_alpha_2"),
            currency_code=spec.get("currency_code"),
        ).first()
        if country_currency:
            flash(
                f"Country currency code already exists for {spec.get('country_alpha_2')} - {spec.get('currency_code')}",
                "info",
            )
            return country_currency

        country_currency = CountryCurrencyCode(
            country_alpha_2=spec.get("country_alpha_2"),
            currency_code=spec.get("currency_code"),
            minor_unit=spec.get("minor_unit"),
        )
        db.session.add(country_currency)
        return country_currency
