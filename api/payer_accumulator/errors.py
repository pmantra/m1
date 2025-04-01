from typing import Optional


class PayerAccumulationException(Exception):
    pass


class AccumulationOpsActionableError(Exception):
    pass


class InvalidAccumulationMappingData(
    PayerAccumulationException, AccumulationOpsActionableError
):
    def __init__(self, message: str, expected_payer_id: Optional[int] = None):
        super().__init__(message)
        self.expected_payer_id = expected_payer_id


class RefundTreatmentAccumulationError(PayerAccumulationException):
    pass


class AccumulationAdjustmentNeeded(PayerAccumulationException):
    # TODO: remove this when auto-adjustment is in place
    pass


class InvalidPatientSexError(InvalidAccumulationMappingData):
    pass


class InvalidPayerError(InvalidAccumulationMappingData):
    pass


class InvalidTreatmentProcedureTypeError(InvalidAccumulationMappingData):
    pass


class InvalidSubscriberIdError(InvalidAccumulationMappingData):
    pass


class NoMemberHealthPlanError(InvalidAccumulationMappingData):
    pass


class NoCostBreakdownError(InvalidAccumulationMappingData):
    pass


class NoMappingDataProvidedError(InvalidAccumulationMappingData):
    pass


class NoMemberIdError(InvalidAccumulationMappingData):
    pass


class UnsupportedRelationshipCodeError(InvalidAccumulationMappingData):
    pass


class NoOrganizationFoundError(InvalidAccumulationMappingData):
    pass


class NoHealthPlanFoundError(InvalidAccumulationMappingData):
    pass


class InvalidGroupIdError(InvalidAccumulationMappingData):
    pass


class NoGlobalProcedureFoundError(InvalidAccumulationMappingData):
    pass


class NoHcpcsCodeForGlobalProcedureError(InvalidAccumulationMappingData):
    pass


class NoCriticalAccumulationInfoError(PayerAccumulationException):
    pass


class SkipAccumulationDueToMissingInfo(NoCriticalAccumulationInfoError):
    pass


class AccumulationRegenerationError(PayerAccumulationException):
    pass
