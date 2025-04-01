from utils.rotatable_token import SECURITY_SIGNING_TOKEN

DEFAULT_EMAIL_SIGNING_TIMEOUT = 60 * 30  # 30 minutes in seconds


def _encode_email_token(email, scope, timeout=DEFAULT_EMAIL_SIGNING_TIMEOUT):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    return SECURITY_SIGNING_TOKEN.encode(
        {"email": email.casefold(), "scope": scope}, exp=timeout
    )


def _check_email_token(email, token, scope):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    return SECURITY_SIGNING_TOKEN.decode(token) == {
        "email": email.casefold(),
        "scope": scope,
    }


def new_password_reset_token(email, exp=DEFAULT_EMAIL_SIGNING_TIMEOUT):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    return _encode_email_token(email, "password_reset", exp)


def check_password_reset_token(email, token):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    return _check_email_token(email, token, "password_reset")


def new_confirm_email_token(email):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    return _encode_email_token(email, "confirm_email")


def check_confirm_email_token(email, token):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    return _check_email_token(email, token, "confirm_email")


def new_payer_email_token(email):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    return _encode_email_token(email, "new_payer", timeout=86400)


def check_payer_email_token(email, token):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    return _check_email_token(email, token, "new_payer")


def _encode_integer_token(intval, scope, timeout):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    return SECURITY_SIGNING_TOKEN.encode(
        {"intval": intval, "scope": scope}, exp=timeout
    )


def _check_integer_token(token, scope):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    result = SECURITY_SIGNING_TOKEN.decode(token)
    if result is None or result["scope"] != scope:
        return
    return result["intval"]


def new_overflowing_appointment_token(appointment_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    return _encode_integer_token(appointment_id, "overflowing_appointment", 86400)


def check_overflowing_appointment_token(token):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    return _check_integer_token(token, "overflowing_appointment")


def new_user_id_encoded_token(user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    return _encode_integer_token(user_id, "user_id", 172800)


def check_user_id_encoded_token(token):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    return _check_integer_token(token, "user_id")
