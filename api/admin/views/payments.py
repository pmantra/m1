from typing import Tuple

from .base import AdminCategory, AdminViewT, AuthenticatedMenuLink
from .models.advertising import AutomaticCodeApplicationView
from .models.messaging import MessageBillingView, MessageCreditView
from .models.payments import (
    AppointmentFeeCreatorView,
    CreditView,
    FeeAccountingEntryView,
    IncentivePaymentView,
    InvoiceView,
    MonthlyPaymentsView,
    PaymentAccountingEntryView,
    PractitionerContractView,
)
from .models.referrals import (
    ReferralCodeCategoryView,
    ReferralCodeSubCategoryView,
    ReferralCodeView,
)


def get_views() -> Tuple[AdminViewT, ...]:
    return (
        AppointmentFeeCreatorView.factory(category=AdminCategory.PAY.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        AutomaticCodeApplicationView.factory(category=AdminCategory.PAY.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        FeeAccountingEntryView.factory(category=AdminCategory.PAY.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        CreditView.factory(category=AdminCategory.PAY.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        IncentivePaymentView.factory(category=AdminCategory.PAY.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        InvoiceView.factory(category=AdminCategory.PAY.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        MonthlyPaymentsView(
            category=AdminCategory.PAY.value,
            endpoint="monthly_payments",
            name="Monthly Payments",
        ),
        MessageBillingView.factory(category=AdminCategory.PAY.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        MessageCreditView.factory(category=AdminCategory.PAY.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        PaymentAccountingEntryView.factory(category=AdminCategory.PAY.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        PractitionerContractView.factory(
            category=AdminCategory.PAY.value, name="Provider Contracts"  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        ),
        ReferralCodeCategoryView.factory(category=AdminCategory.PAY.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        ReferralCodeSubCategoryView.factory(category=AdminCategory.PAY.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        ReferralCodeView.factory(category=AdminCategory.PAY.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
    )


def get_links() -> Tuple[AuthenticatedMenuLink, ...]:
    return ()
