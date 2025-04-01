import datetime
from collections import namedtuple
from datetime import date

import pytest

from wallet.models.constants import AlegeusCoverageTier, WalletState
from wallet.models.models import AnnualInsuranceQuestionnaireHDHPData
from wallet.models.reimbursement import ReimbursementWalletPlanHDHP
from wallet.pytests.factories import (
    ReimbursementAccountTypeFactory,
    ReimbursementOrgSettingCategoryAssociationFactory,
    ReimbursementPlanFactory,
    ReimbursementRequestCategoryFactory,
    ReimbursementWalletFactory,
)
from wallet.utils.insurance.process_questionnaire import (
    create_wallet_hdhp_plan,
    get_hdhp_questionnaire_response,
)

PlanTuple = namedtuple(
    "PlanTuple",
    [
        "alegeus_plan_id",
        "alegeus_account_type",
        "is_hdhp",
        "start_date",
        "end_date",
        "organization_id",
    ],
)


@pytest.mark.parametrize(
    argnames="response_user_hdhp,response_partner_hdhp,expected_coverage_tier",
    argvalues=(
        (True, True, AlegeusCoverageTier.FAMILY),
        (True, False, AlegeusCoverageTier.SINGLE),
        (False, True, AlegeusCoverageTier.SINGLE),
        (False, False, None),
    ),
)
def test_get_hdhp_questionnaire_response(
    response_user_hdhp, response_partner_hdhp, expected_coverage_tier
):
    # Given
    questionnaire_data = AnnualInsuranceQuestionnaireHDHPData(
        response_user_hdhp,
        response_partner_hdhp,
    )
    # When
    coverage_tier = get_hdhp_questionnaire_response(questionnaire_data)
    # Then
    assert coverage_tier == expected_coverage_tier


@pytest.mark.parametrize(
    argnames="org_id_offset, mapped_hdhp_plan_id, hdhp_plan_id, expect_a_plan",
    argvalues=(
        (0, "TESTORGHDHP2024", "TESTORGHDHP2024", True),
        (0, "TESTORGHDHP24", "TESTORGHDHP24", True),
        (1, "TESTORGHDHP2024", "TESTORGHDHP2024", False),
        (1, "TESTORGHDHP24", "TESTORGHDHP24", False),
        (0, "TESTORGHDHP2025", "TESTORGHDHP2025", False),
        (0, "TESTORGHDHP23", "TESTORGHDHP23", False),
        (0, "TESTORGHDHP24", "TESTORGHDHP2024", False),
        (0, "TESTORGHDHP2024", "TESTORGHDHP24", False),
    ),
)
def test_create_wallet_hdhp_plan_legacy(
    enterprise_user,
    monkeypatch,
    org_id_offset,
    mapped_hdhp_plan_id,
    hdhp_plan_id,
    expect_a_plan,
):
    # year = datetime.datetime.utcnow().year
    year_ = 2024
    created_hdhp_plan = ReimbursementPlanFactory.create(
        reimbursement_account_type=ReimbursementAccountTypeFactory.create(
            alegeus_account_type="DTR"
        ),
        alegeus_plan_id=hdhp_plan_id,
        start_date=datetime.date(year=year_, month=1, day=1),
        end_date=datetime.date(year=year_, month=12, day=31),
        is_hdhp=True,
    )

    wallet = ReimbursementWalletFactory.create(state=WalletState.PENDING)
    org_settiings = wallet.reimbursement_organization_settings
    category = ReimbursementRequestCategoryFactory.create(
        label="fertility", reimbursement_plan=created_hdhp_plan
    )
    ReimbursementOrgSettingCategoryAssociationFactory.create(
        reimbursement_organization_settings=org_settiings,
        reimbursement_request_category=category,
        reimbursement_request_category_maximum=5000,
    )
    monkeypatch.setattr(
        "wallet.utils.insurance.process_questionnaire.ORGID_TO_HDHP_PLAN_NAME_MAP",
        {org_settiings.organization_id + org_id_offset: mapped_hdhp_plan_id},
    )
    # When
    plan_created = create_wallet_hdhp_plan(
        wallet, AlegeusCoverageTier.SINGLE, year_, True
    )
    hdhp_wallet = ReimbursementWalletPlanHDHP.query.one_or_none()

    assert plan_created == (created_hdhp_plan if expect_a_plan else None)
    assert hdhp_wallet if expect_a_plan else hdhp_wallet is None
    if expect_a_plan:
        assert hdhp_wallet.reimbursement_wallet_id == wallet.id


@pytest.mark.parametrize(
    argnames="plans_info, wallet_org_id, inp_alegeus_tier, inp_year, expected_plan_index",
    argvalues=[
        pytest.param(
            [
                PlanTuple(
                    alegeus_plan_id="TESTORGHDHP2024",
                    alegeus_account_type="DTR",
                    is_hdhp=True,
                    start_date=date(2024, 1, 1),
                    end_date=date(2024, 12, 31),
                    organization_id=100,
                )
            ],
            100,
            AlegeusCoverageTier.SINGLE,
            2024,
            0,
            id="1. HDHP Reimbursement plan exists for the specified year. Wallet HDHP plan is created.",
        ),
        pytest.param(
            [
                PlanTuple(
                    alegeus_plan_id="TESTORGHDHP2024",
                    alegeus_account_type="DTR",
                    is_hdhp=True,
                    start_date=date(2024, 1, 1),
                    end_date=date(2024, 12, 31),
                    organization_id=100,
                )
            ],
            100,
            AlegeusCoverageTier.SINGLE,
            2025,
            None,
            id="2. HDHP Reimbursement plan does not exists for the specified year. Wallet HDHP plan is not created.",
        ),
        pytest.param(
            [
                PlanTuple(
                    alegeus_plan_id="TESTORG_NOT_HDHP_2024",
                    alegeus_account_type="FSA",
                    is_hdhp=False,
                    start_date=date(2024, 1, 1),
                    end_date=date(2024, 12, 31),
                    organization_id=100,
                ),
                PlanTuple(
                    alegeus_plan_id="TESTORGHDHP2024",
                    alegeus_account_type="DTR",
                    is_hdhp=True,
                    start_date=date(2024, 1, 1),
                    end_date=date(2024, 12, 31),
                    organization_id=100,
                ),
            ],
            100,
            AlegeusCoverageTier.FAMILY,
            2024,
            1,
            id="3. One of the plans is an HDHP Reimbursement plan for the specified year. Wallet HDHP plan is created.",
        ),
        pytest.param(
            [
                PlanTuple(
                    alegeus_plan_id="TESTORG_NOT_HDHP_2024",
                    alegeus_account_type="FSA",
                    is_hdhp=False,
                    start_date=date(2024, 1, 1),
                    end_date=date(2024, 12, 31),
                    organization_id=100,
                ),
                PlanTuple(
                    alegeus_plan_id="TESTORGHDHP2024",
                    alegeus_account_type="DTR",
                    is_hdhp=True,
                    start_date=date(2024, 1, 1),
                    end_date=date(2024, 12, 31),
                    organization_id=100,
                ),
                PlanTuple(
                    alegeus_plan_id="TESTORGHDHP2025",
                    alegeus_account_type="DTR",
                    is_hdhp=True,
                    start_date=date(2025, 1, 1),
                    end_date=date(2025, 12, 31),
                    organization_id=100,
                ),
            ],
            100,
            AlegeusCoverageTier.SINGLE,
            2025,
            2,
            id="4. One of the plans is an HDHP Reimbursement plan for the specified year. Wallet HDHP plan is created.",
        ),
        pytest.param(
            [
                PlanTuple(
                    alegeus_plan_id="TESTORG_HDHP_2024",
                    alegeus_account_type="DTR",
                    is_hdhp=True,
                    start_date=date(2024, 1, 1),
                    end_date=date(2024, 12, 31),
                    organization_id=100,
                ),
                PlanTuple(
                    alegeus_plan_id="TESTORG_ALSO_HDHP_2024",
                    alegeus_account_type="DTR",
                    is_hdhp=True,
                    start_date=date(2024, 1, 1),
                    end_date=date(2024, 12, 31),
                    organization_id=100,
                ),
            ],
            100,
            AlegeusCoverageTier.SINGLE,
            2024,
            None,
            id="5. Multiple HDHP Reimbursement plans for the specified year. Wallet HDHP plan is not created.",
        ),
        pytest.param(
            [
                PlanTuple(
                    alegeus_plan_id="TESTORG_NOT_HDHP_2024",
                    alegeus_account_type="FSA",
                    is_hdhp=False,
                    start_date=date(2024, 1, 1),
                    end_date=date(2024, 12, 31),
                    organization_id=101,
                ),
                PlanTuple(
                    alegeus_plan_id="TESTORGHDHP2024",
                    alegeus_account_type="DTR",
                    is_hdhp=True,
                    start_date=date(2024, 1, 1),
                    end_date=date(2024, 12, 31),
                    organization_id=100,
                ),
            ],
            101,
            AlegeusCoverageTier.SINGLE,
            2024,
            None,
            id="6. No HDHP plans for the wallet org. Wallet HDHP plan is notcreated.",
        ),
    ],
)
def test_create_wallet_hdhp_plan_new(
    enterprise_user,
    plans_info,
    wallet_org_id,
    inp_alegeus_tier,
    inp_year,
    expected_plan_index,
):
    wallet = ReimbursementWalletFactory.create(state=WalletState.QUALIFIED)
    wallet.reimbursement_organization_settings.organization_id = wallet_org_id

    plans = [
        ReimbursementPlanFactory.create(
            reimbursement_account_type=ReimbursementAccountTypeFactory.create(
                alegeus_account_type=plan_info.alegeus_account_type
            ),
            alegeus_plan_id=plan_info.alegeus_plan_id,
            start_date=plan_info.start_date,
            end_date=plan_info.end_date,
            is_hdhp=plan_info.is_hdhp,
            organization_id=plan_info.organization_id,
        )
        for plan_info in plans_info
    ]

    # When
    reimbursement_plan = create_wallet_hdhp_plan(
        wallet, inp_alegeus_tier, inp_year, False
    )
    hdhp_wallet_plan = ReimbursementWalletPlanHDHP.query.one_or_none()
    if expected_plan_index is None:
        assert hdhp_wallet_plan is None
        assert reimbursement_plan is None
    else:
        # Basic existence checks
        assert hdhp_wallet_plan
        assert reimbursement_plan

        # Wallet Plan validations
        assert hdhp_wallet_plan.reimbursement_wallet_id == wallet.id
        assert hdhp_wallet_plan.reimbursement_plan_id == reimbursement_plan.id
        assert hdhp_wallet_plan.alegeus_coverage_tier == inp_alegeus_tier

        # Reimbursement Plan validations
        assert reimbursement_plan.id == plans[expected_plan_index].id
        assert reimbursement_plan.organization_id == wallet_org_id
        assert reimbursement_plan.start_date.year == inp_year
        assert reimbursement_plan.is_hdhp
