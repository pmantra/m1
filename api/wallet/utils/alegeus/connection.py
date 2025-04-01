from utils.log import logger
from wallet.alegeus_api import ALEGEUS_TPAID, AlegeusApi, is_request_successful

log = logger(__name__)


def test_wcp_connection() -> bool:
    """
    Test WealthCare Participant (WCP) API by requesting auth'ed userinfo and verifying TPAID
    """
    api = AlegeusApi()

    try:
        response = api.get_user_info()
        if not is_request_successful(response):  # type: ignore[arg-type] # Argument 1 to "is_request_successful" has incompatible type "Optional[Response]"; expected "Response"
            log.error("WCP connection test error.")
            return False

        userinfo = response.json()  # type: ignore[union-attr] # Item "None" of "Optional[Response]" has no attribute "json"
        if userinfo["TpaId"] != ALEGEUS_TPAID:
            log.error("WCP connection test TPAID mismatch.")
            return False
    except Exception as e:
        log.exception("WCP connection test exception.", error=e)
        return False

    return True


def test_wca_connection() -> bool:
    """
    Test WealthCare Admin (WCA) API by requesting employers list and expecting > 0 records
    """
    api = AlegeusApi()

    try:
        response = api.get_employer_list()
        if not is_request_successful(response):  # type: ignore[arg-type] # Argument 1 to "is_request_successful" has incompatible type "Optional[Response]"; expected "Response"
            log.error("WCA connection test error.")
            return False

        employers = response.json()  # type: ignore[union-attr] # Item "None" of "Optional[Response]" has no attribute "json"
        if len(employers) == 0:
            log.error("WCA connection test employers empty.")
            return False
    except Exception as e:
        log.exception("WCA connection test exception.", error=e)
        return False

    return True
