from wallet.resources.annual_questionnaire import (
    AnnualQuestionnaireNeededInClinicPortalResource,
    AnnualQuestionnaireNeededResource,
    AnnualQuestionnaireResource,
)
from wallet.resources.reimbursement_org_name_retrieval import (
    ReimbursementOrgSettingNameResource,
)
from wallet.resources.reimbursement_org_settings import ReimbursementOrgSettingsResource
from wallet.resources.reimbursement_request import (
    ReimbursementRequestDetailsResource,
    ReimbursementRequestResource,
    ReimbursementRequestSourceRequestsResource,
    ReimbursementRequestStateResource,
)
from wallet.resources.reimbursement_wallet import (
    ReimbursementWalletResource,
    ReimbursementWalletsResource,
)
from wallet.resources.reimbursement_wallet_bank_account import (
    UserReimbursementWalletBankAccountResource,
)
from wallet.resources.reimbursement_wallet_currency import (
    ReimbursementWalletAvailableCurrenciesResource,
)
from wallet.resources.reimbursement_wallet_dashboard import (
    ReimbursementWalletDashboardResource,
)
from wallet.resources.reimbursement_wallet_debit_card import (
    UserReimbursementWalletDebitCardLostStolenResource,
    UserReimbursementWalletDebitCardResource,
)
from wallet.resources.reimbursement_wallet_state import ReimbursementWalletStateResource
from wallet.resources.reimbursement_wallet_upcoming_transactions import (
    UserReimbursementWalletUpcomingTransactionsResource,
)
from wallet.resources.stripe_webhook import StripeReimbursementWebHookResource
from wallet.resources.surveymonkey_webhook import SurveyMonkeyWebHookResource
from wallet.resources.wallet_add_user import WalletAddUserResource
from wallet.resources.wallet_historical_spend import WalletHistoricalSpendResource
from wallet.resources.wallet_invitation import WalletInvitationResource
from wallet.resources.wallet_user_info import WalletUserInfoResource
from wallet.resources.wallet_users import WalletUsersResource
from wallet.resources.wqs_wallet import WQSWalletPutResource, WQSWalletResource


def add_routes(api):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    api.add_resource(ReimbursementWalletResource, "/v1/reimbursement_wallet")

    api.add_resource(
        ReimbursementWalletAvailableCurrenciesResource,
        "/v1/reimbursement_wallet/available_currencies",
    )

    api.add_resource(ReimbursementWalletStateResource, "/v1/reimbursement_wallet/state")

    api.add_resource(
        ReimbursementWalletsResource, "/v1/reimbursement_wallet/<int:wallet_id>"
    )
    api.add_resource(
        UserReimbursementWalletBankAccountResource,
        "/v1/reimbursement_wallets/<int:wallet_id>/bank_account",
    )
    api.add_resource(
        UserReimbursementWalletDebitCardResource,
        "/v1/reimbursement_wallets/<int:wallet_id>/debit_card",
    )
    api.add_resource(
        UserReimbursementWalletDebitCardLostStolenResource,
        "/v1/reimbursement_wallets/<int:wallet_id>/debit_card/lost_stolen",
    )
    api.add_resource(ReimbursementRequestResource, "/v1/reimbursement_request")

    api.add_resource(
        ReimbursementRequestDetailsResource,
        "/v1/reimbursement_request/<int:reimbursement_request_id>",
    )

    api.add_resource(
        ReimbursementRequestStateResource, "/v1/reimbursement_request/state"
    )

    api.add_resource(
        ReimbursementRequestSourceRequestsResource,
        "/v1/reimbursement_request/<int:reimbursement_request_id>/sources",
    )

    api.add_resource(
        WalletUsersResource, "/v1/reimbursement_wallet/<int:wallet_id>/users"
    )

    api.add_resource(
        WalletAddUserResource, "/v1/reimbursement_wallet/<int:wallet_id>/add_user"
    )

    api.add_resource(
        WalletInvitationResource,
        "/v1/reimbursement_wallet/invitation/<string:invitation_id>",
    )

    api.add_resource(
        WalletUserInfoResource,
        # Internal routes contain a dash prefix
        "/v1/-/reimbursement_wallet/application/user_info",
    )

    api.add_resource(
        WQSWalletResource,
        # Internal routes contain a dash prefix
        "/v1/-/wqs/wallet",
    )

    api.add_resource(
        WQSWalletPutResource,
        # Internal routes contain a dash prefix
        "/v1/-/wqs/wallet/<int:wallet_id>",
    )

    api.add_resource(
        ReimbursementWalletDashboardResource, "/v1/reimbursement_wallet/dashboard"
    )

    api.add_resource(
        StripeReimbursementWebHookResource, "/v1/vendor/stripe/reimbursements-webhook"
    )
    api.add_resource(
        SurveyMonkeyWebHookResource, "/v1/vendor/surveymonkey/survey-completed-webhook"
    )

    api.add_resource(
        AnnualQuestionnaireResource,
        "/v1/reimbursement_wallets/<int:wallet_id>/insurance/annual_questionnaire",
    )

    api.add_resource(
        AnnualQuestionnaireNeededResource,
        "/v1/reimbursement_wallets/<int:wallet_id>/insurance/annual_questionnaire/needs_survey",
    )

    api.add_resource(
        AnnualQuestionnaireNeededInClinicPortalResource,
        "/v1/reimbursement_wallets/<int:wallet_id>/insurance/annual_questionnaire/clinic_portal/needs_survey",
    )

    api.add_resource(
        UserReimbursementWalletUpcomingTransactionsResource,
        "/v1/reimbursement_wallets/<int:id>/upcoming_transactions",
    )

    api.add_resource(
        ReimbursementOrgSettingsResource,
        # Internal routes contain a dash prefix
        "/v1/-/wqs/reimbursement_org",
    )

    api.add_resource(
        ReimbursementOrgSettingNameResource,
        # Internal routes contain a dash prefix
        "/v1/-/wqs/reimbursement_org_setting_name/<int:ros_id>",
    )

    api.add_resource(
        WalletHistoricalSpendResource,
        # Internal routes contain a dash prefix
        "/v1/-/wallet_historical_spend/process_file",
    )

    return api
