from wallet.models.constants import WalletState, WalletUserStatus
from wallet.pytests.factories import (
    ReimbursementOrganizationSettingsFactory,
    ReimbursementWalletDashboardCardFactory,
)
from wallet.services.reimbusement_wallet_dashboard import (
    DASHBOARD_CARD_LINK_URL_TEXT,
    get_cards_for_user,
    get_dashboard_cards,
    get_reimbursement_organization_settings,
    update_wallet_program_overview_url,
)


def test_get_cards_for_user__no_org(default_user, wallet_dashboard):
    reimbursement_settings = get_reimbursement_organization_settings(default_user)
    cards = get_cards_for_user(default_user, reimbursement_settings)
    assert cards == []


def test_get_cards_for_user__no_org_reimbursements(enterprise_user, wallet_dashboard):
    reimbursement_settings = get_reimbursement_organization_settings(enterprise_user)
    cards = get_cards_for_user(enterprise_user, reimbursement_settings)
    assert cards == []


def test_get_cards_for_user__no_wallet(enterprise_user, wallet_dashboard):
    ReimbursementOrganizationSettingsFactory.create(
        organization_id=enterprise_user.organization.id
    )
    reimbursement_settings = get_reimbursement_organization_settings(enterprise_user)
    cards = get_cards_for_user(enterprise_user, reimbursement_settings)
    assert len(cards) == 1
    assert cards[0].title == "Generic Card"


def test_get_cards_for_user__no_wallet_debit_enabled_not_eligible(
    enterprise_user, wallet_dashboard
):
    ReimbursementOrganizationSettingsFactory.create(
        organization_id=enterprise_user.organization.id, debit_card_enabled=False
    )
    reimbursement_settings = get_reimbursement_organization_settings(enterprise_user)
    cards = get_cards_for_user(enterprise_user, reimbursement_settings)
    assert len(cards) == 1
    assert cards[0].title == "Generic Card"


def test_get_cards_for_user__no_wallet_debit_enabled_and_eligible(
    enterprise_user, wallet_dashboard
):
    enterprise_user.profile.country_code = "US"
    ReimbursementOrganizationSettingsFactory.create(
        organization_id=enterprise_user.organization.id, debit_card_enabled=True
    )
    reimbursement_settings = get_reimbursement_organization_settings(enterprise_user)
    cards = get_cards_for_user(enterprise_user, reimbursement_settings)
    assert len(cards) == 2
    assert cards[0].title == "Generic Card"
    assert cards[1].title == "Debit Card"


def test_get_cards_for_user__wallet_pending(
    pending_alegeus_wallet_hra, wallet_dashboard
):
    enterprise_user = pending_alegeus_wallet_hra.employee_member
    reimbursement_settings = get_reimbursement_organization_settings(enterprise_user)
    cards = get_cards_for_user(enterprise_user, reimbursement_settings)
    assert len(cards) == 2
    assert cards[0].title == "Pending Card"


def test_get_cards_for_user__wallet_disqualified(
    pending_alegeus_wallet_hra, wallet_dashboard
):
    enterprise_user = pending_alegeus_wallet_hra.employee_member
    pending_alegeus_wallet_hra.state = WalletState.DISQUALIFIED
    reimbursement_settings = get_reimbursement_organization_settings(enterprise_user)
    cards = get_cards_for_user(enterprise_user, reimbursement_settings)
    assert len(cards) == 2
    assert cards[0].title == "Disqualified Card"


def test_get_cards_for_user__wallet_qualified(
    qualified_alegeus_wallet_hra, wallet_dashboard
):
    enterprise_user = qualified_alegeus_wallet_hra.employee_member
    reimbursement_settings = get_reimbursement_organization_settings(enterprise_user)
    cards = get_cards_for_user(enterprise_user, reimbursement_settings)
    assert len(cards) == 0


def test_get_cards_for_user__wallet_qualified_but_rwu_pending(
    qualified_alegeus_wallet_hra, wallet_dashboard
):
    enterprise_user = qualified_alegeus_wallet_hra.employee_member
    qualified_alegeus_wallet_hra.reimbursement_wallet_users[
        0
    ].status = WalletUserStatus.PENDING
    reimbursement_settings = get_reimbursement_organization_settings(enterprise_user)
    cards = get_cards_for_user(enterprise_user, reimbursement_settings)
    assert len(cards) == 2
    assert cards[0].title == "Pending Card"


def test_update_wallet_program_overview_url__no_cards(default_user):
    reimbursement_settings = get_reimbursement_organization_settings(default_user)
    updated_cards = update_wallet_program_overview_url([], reimbursement_settings)
    assert updated_cards == []


def test_update_wallet_program_overview_url__with_cards(
    enterprise_user, pending_alegeus_wallet_hra
):
    org_settings = pending_alegeus_wallet_hra.reimbursement_organization_settings
    cards = [
        ReimbursementWalletDashboardCardFactory.create(
            title="Generic Card", link_url=DASHBOARD_CARD_LINK_URL_TEXT
        ),
        ReimbursementWalletDashboardCardFactory.create(
            title="Debit Card", require_debit_eligible=True
        ),
    ]
    reimbursement_settings = get_reimbursement_organization_settings(enterprise_user)
    updated_cards = update_wallet_program_overview_url(cards, reimbursement_settings)
    assert (
        updated_cards[0].link_url == org_settings.benefit_overview_resource.custom_url
    )
    assert updated_cards[1].link_url is None


def test_update_wallet_program_overview_url_no_benefit_overview_resource(
    enterprise_user, pending_alegeus_wallet_hra
):
    org_settings = pending_alegeus_wallet_hra.reimbursement_organization_settings
    org_settings.benefit_overview_resource = None
    cards = [
        ReimbursementWalletDashboardCardFactory.create(
            title="Generic Card", link_url=DASHBOARD_CARD_LINK_URL_TEXT
        ),
        ReimbursementWalletDashboardCardFactory.create(
            title="Debit Card", require_debit_eligible=True
        ),
    ]
    reimbursement_settings = get_reimbursement_organization_settings(enterprise_user)
    updated_cards = update_wallet_program_overview_url(cards, reimbursement_settings)
    assert updated_cards[0].link_url is None
    assert updated_cards[1].link_url is None


def test_get_dashboard_cards__returns_updated_cards(
    pending_alegeus_wallet_hra, wallet_dashboard
):
    wallet = pending_alegeus_wallet_hra
    org_settings = wallet.reimbursement_organization_settings
    org_settings.debit_card_enabled = True
    cards = get_dashboard_cards(wallet.employee_member)
    assert len(cards) == 3

    assert cards[0].title == "Pending Card"
    assert cards[0].link_url is None

    assert cards[1].title == "Generic Card"
    assert cards[1].link_url == org_settings.benefit_overview_resource.custom_url
    assert cards[2].title == "Debit Card"
    assert cards[2].link_url is None


def test_get_reimbursement_organization_settings_non_enterprise_user(default_user):
    result = get_reimbursement_organization_settings(default_user)
    assert result is None


def test_get_reimbursement_organization_settings_without_setting(enterprise_user):
    result = get_reimbursement_organization_settings(enterprise_user)
    assert result is None


def test_get_reimbursement_organization_settings_with_setting_exists(enterprise_user):
    settings = ReimbursementOrganizationSettingsFactory.create(
        organization_id=enterprise_user.organization.id
    )
    result = get_reimbursement_organization_settings(enterprise_user)
    assert result == settings
