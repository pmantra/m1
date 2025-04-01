from common.constants import Environment

USE_ALEGEUS_IN_ENV = {
    Environment.PRODUCTION: True,
    Environment.QA1: False,
    Environment.QA2: True,
    Environment.STAGING: True,
    Environment.LOCAL: False,
}


def use_alegeus_for_reimbursements():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    use_alegeus = USE_ALEGEUS_IN_ENV.get(Environment.current(), False)
    return use_alegeus
