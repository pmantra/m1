from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class InterchangeControlHeader:
    __slots__ = (
        "authorization_information_qualifier",
        "authorization_information",
        "security_information_qualifier",
        "security_information",
        "interchange_sender_id_qualifier",
        "interchange_sender_id",
        "interchange_receiver_id_qualifier",
        "interchange_receiver_id",
        "interchange_date",
        "interchange_time",
        "repetition_separator",
        "interchange_control_version_number",
        "interchange_control_number",
        "acknowledgment_requested",
        "interchange_usage_indicator",
        "component_element_separator",
    )
    authorization_information_qualifier: str
    authorization_information: str
    security_information_qualifier: str
    security_information: str
    interchange_sender_id_qualifier: str
    interchange_sender_id: str
    interchange_receiver_id_qualifier: str
    interchange_receiver_id: str
    interchange_date: str
    interchange_time: str
    repetition_separator: str
    interchange_control_version_number: str
    interchange_control_number: str
    acknowledgment_requested: str
    interchange_usage_indicator: str
    component_element_separator: str


@dataclass
class TransactionSetHeader:
    __slots__ = (
        "transaction_set_identifier_code",
        "transaction_set_control_number",
        "version_release_industry_identifier_code",
    )
    transaction_set_identifier_code: str
    transaction_set_control_number: str
    version_release_industry_identifier_code: str


@dataclass
class ClaimStatusTrackingInformation:
    __slots__ = (
        "trace_type_code",
        "referenced_transaction_trace_number",
    )
    trace_type_code: str
    referenced_transaction_trace_number: str


@dataclass
class ClaimLevelStatusInformation:
    __slots__ = (
        "health_care_claim_status_category_code",
        "claim_status_code",
    )
    health_care_claim_status_category_code: str
    claim_status_code: str


@dataclass
class ClaimData:
    claim_status_tracking: Optional[ClaimStatusTrackingInformation]
    claim_level_status: Optional[ClaimLevelStatusInformation]


@dataclass
class X12Data277:
    interchange_control_header: Optional[InterchangeControlHeader]
    transaction_set_header: Optional[TransactionSetHeader]
    claims: List[ClaimData] = field(default_factory=list)
