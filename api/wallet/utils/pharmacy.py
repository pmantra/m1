from __future__ import annotations

import enum
from typing import Optional

from authn.models.user import User
from wallet.models.reimbursement_wallet import ReimbursementWallet


class Pharmacy(str, enum.Enum):
    ALTO = "ALTO"
    SMP = "SMP"


ALTO_PHARMACY_REGIONS = frozenset(("CA", "CO", "CT", "NV", "NJ", "NY", "TX", "WA"))
SMP_PHARMACY_REGIONS = frozenset(
    (
        "AL",
        "AK",
        "AZ",
        "AR",
        "DE",
        "DC",
        "FL",
        "GA",
        "HI",
        "ID",
        "IL",
        "IN",
        "IA",
        "KS",
        "KY",
        "LA",
        "ME",
        "MD",
        "MA",
        "MI",
        "MN",
        "MS",
        "MO",
        "MT",
        "NE",
        "NH",
        "NM",
        "NC",
        "ND",
        "OH",
        "OK",
        "OR",
        "PA",
        "RI",
        "SC",
        "SD",
        "TN",
        "UT",
        "VT",
        "VA",
        "WV",
        "WI",
        "WY",
    )
)

PHARMACY_INFO = {
    Pharmacy.ALTO: {
        "name": "Alto Pharmacy",
        "url": "https://www.mavenclinic.com/app/resources/content/r/mavenrx-alto-pharmacy",
    },
    Pharmacy.SMP: {
        "name": "SMP Pharmacy",
        "url": "https://www.mavenclinic.com/app/resources/content/r/mavenrx-smp-pharmacy",
    },
}


def get_pharmacy_details_for_wallet(
    member: User, wallet: ReimbursementWallet | None = None
) -> Optional[dict]:
    if (
        wallet
        and wallet.reimbursement_organization_settings.direct_payment_enabled
        and wallet.get_direct_payment_category
    ):
        return PHARMACY_INFO[Pharmacy.SMP]

    member_profile = member.member_profile
    if (
        member_profile
        and member_profile.country_code == "US"
        and member_profile.subdivision_code
    ):
        state = member_profile.subdivision_code[3:]
        pharmacy = get_pharmacy_by_state(state)
        return PHARMACY_INFO.get(pharmacy)  # type: ignore[arg-type] # Argument 1 to "get" of "dict" has incompatible type "Optional[Pharmacy]"; expected "Pharmacy"

    return None


def get_pharmacy_by_state(state: str) -> Optional[Pharmacy]:
    """
    State->Pharmacy mapping is determined by contracts with the pharmacies.
    The list is maintained by Program Operations
    https://docs.google.com/spreadsheets/d/1LWtPcGzSHPe6_7LICT-kIp3-x3d-zRwlvw8i_VZ41E8/edit#gid=1562931856
    """

    if state in ALTO_PHARMACY_REGIONS:
        return Pharmacy.ALTO
    elif state in SMP_PHARMACY_REGIONS:
        return Pharmacy.SMP

    return None
