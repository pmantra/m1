from __future__ import annotations

from typing import Tuple

from .base import AdminCategory, AdminViewT, AuthenticatedMenuLink
from .models.direct_payment_invoice import DirectPaymentInvoiceView
from .models.direct_payment_invoice_report import DirectPaymentInvoiceReportView
from .models.payer_accumulator import (
    AccumulationTreatmentMappingView,
    PayerAccumulationReportsView,
)
from .models.wallet import (
    IngestionMetaView,
    WalletClientReportReimbursementsView,
    WalletClientReportView,
)


def get_views() -> Tuple[AdminViewT, ...]:
    return (
        DirectPaymentInvoiceView.factory(
            category=AdminCategory.WALLET_REPORTING.value,  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
            name="Direct Payment Invoices",
        ),
        DirectPaymentInvoiceReportView.factory(
            category=AdminCategory.WALLET_REPORTING.value,  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
            name="Direct Payment Organization Invoice Report",
        ),
        # Reporting
        WalletClientReportView.factory(category=AdminCategory.WALLET_REPORTING.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        WalletClientReportReimbursementsView.factory(
            category=AdminCategory.WALLET_REPORTING.value  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        ),
        PayerAccumulationReportsView.factory(category=AdminCategory.WALLET_REPORTING.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        AccumulationTreatmentMappingView.factory(category=AdminCategory.WALLET_REPORTING.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        IngestionMetaView.factory(
            category=AdminCategory.WALLET_REPORTING.value,  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
            name="ESI Ingestion Meta Management",
        ),
    )


def get_links() -> Tuple[AuthenticatedMenuLink, ...]:
    return ()
