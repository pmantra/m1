import enum
from typing import List, Optional, TypedDict


class PortalMessageLevel(str, enum.Enum):
    """The level of the message displayed to users in the clinic portal"""

    ATTENTION = "attention"
    WARNING = "warning"
    ERROR = "error"
    SUCCESS = "success"


class BodyVariant(str, enum.Enum):
    """
    The enum representing the variant of the body's copy-text
    displayed to users when a member is looked up in the clinic portal
    """

    PROGYNY_TOC = "PROGYNY_TOC"


class PortalMessage(TypedDict):
    """Wrapper class for a message displayed to users in the clinic portal"""

    text: str
    level: str


class ClinicPortalMember(TypedDict):
    user_id: int
    first_name: str
    last_name: str
    date_of_birth: str
    phone: str
    email: str
    benefit_id: str
    current_type: str
    eligible_type: str
    eligibility_start_date: Optional[str]
    eligibility_end_date: Optional[str]


class ClinicPortalProcedure(TypedDict):
    procedure_id: str
    procedure_name: str


class ClinicPortalFertilityProgram(TypedDict):
    program_type: str
    direct_payment_enabled: bool
    allows_taxable: bool
    dx_required_procedures: List[str]
    excluded_procedures: List[ClinicPortalProcedure]


class ClinicPortalOrganization(TypedDict):
    name: str
    fertility_program: Optional[ClinicPortalFertilityProgram]


class WalletBalance(TypedDict):
    total: Optional[int]
    available: Optional[int]
    is_unlimited: bool


class WalletOverview(TypedDict):
    wallet_id: int
    state: str
    balance: WalletBalance
    payment_method_on_file: bool
    allow_treatment_scheduling: bool
    benefit_type: Optional[str]


class MemberBenefit(TypedDict):
    organization: Optional[ClinicPortalOrganization]
    wallet: Optional[WalletOverview]


class PortalContent(TypedDict):
    messages: list[PortalMessage]
    body_variant: str


class MemberLookupResponse(TypedDict):
    member: ClinicPortalMember
    benefit: MemberBenefit
    content: Optional[PortalContent]
