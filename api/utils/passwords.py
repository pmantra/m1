import random
import re
import secrets
import string

from flask_babel import lazy_gettext
from werkzeug import security

MAX_SCORE = 4.0
MIN_PASSWORD_LENGTH = 8
FEEDBACK_MISSING_ATTRIBUTE = lazy_gettext("utils_password_include_3_of_4")
FEEDBACK_PASSWORD_SHORT = lazy_gettext(
    "utils_password_minimum_character", min_length=MIN_PASSWORD_LENGTH
)

ATTRIBUTE_REGEX = {
    "lower_case": r"[a-z]",
    "upper_case": r"[A-Z]",
    "number": r"[0-9]",
    "special_character": r"[\!\@\#\$\%\^\&\*]",
}


def check_password_strength(password: str) -> dict:
    """
    Most of this logic related to the score and strength_score is legacy junk
    that we are maintaining for backwards compatibility with mobile clients

    When invalid we set these to 0, when valid, we set them to a "high" value
    The legacy structures come from https://github.com/dwolfhub/zxcvbn-python
    """
    pw_ok = True
    feedback = []
    strength_score = MAX_SCORE
    score = MAX_SCORE * 10

    attributes = []
    for attribute, regex in ATTRIBUTE_REGEX.items():
        if re.search(regex, password) is not None:
            attributes.append(attribute)

    # Require a minimum password length of MIN_PASSWORD_LENGTH
    if len(password) < MIN_PASSWORD_LENGTH:
        pw_ok = False
        score = 0.0
        strength_score = 0.0
        feedback.append(FEEDBACK_PASSWORD_SHORT)
    elif len(attributes) < 3:
        # Require at least 3 of the 4 attribute types
        pw_ok = False
        score = 0.0
        strength_score = 0.0
        feedback.append(FEEDBACK_MISSING_ATTRIBUTE)

    return {
        "score": score,
        "password_strength_score": strength_score,
        "password_strength_ok": pw_ok,
        "feedback": feedback,
        "password_length": len(password),
    }


def random_password() -> str:
    """
    Returns a randomized string to store as a password

    Conforms to the password strenght settings expected by Auth0
    """

    special = "".join(random.choices("!@#$%^&*", k=2))
    lower = "".join(random.choices(string.ascii_lowercase, k=2))
    upper = "".join(random.choices(string.ascii_uppercase, k=2))
    digits = "".join(random.choices(string.digits, k=2))
    return secrets.token_urlsafe(32) + special + lower + upper + digits


def encode_password(password: str) -> str:
    """Encrypt the supplied password."""
    return security.generate_password_hash(
        password=password, method="pbkdf2:sha256:10000", salt_length=12
    )
