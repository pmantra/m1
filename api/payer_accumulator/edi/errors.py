from payer_accumulator.errors import PayerAccumulationException


class X12FileWriterException(Exception):
    pass


class EDI837AccumulationFileGeneratorException(PayerAccumulationException):
    pass


class EDI276ClaimStatusRequestGeneratorException(PayerAccumulationException):
    pass


class NoValidRowIncludedException(EDI837AccumulationFileGeneratorException):
    pass
