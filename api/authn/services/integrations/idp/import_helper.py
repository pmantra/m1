from __future__ import annotations

import codecs


def build_payload(user) -> dict | None:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    value = _build_custom_password_hash(user.password)
    if value is None:
        return
    return {
        "email": user.email,
        "name": user.email,
        "email_verified": True,
        "custom_password_hash": {
            "algorithm": ALGORITHM,
            "hash": {
                "value": value,
                "encoding": "utf8",
            },
        },
        "app_metadata": {"maven_user_id": user.id},
    }


ALGORITHM = "pbkdf2"


def _build_custom_password_hash(password: str) -> str:
    """Given a hashed password, build a PHC string format for upload

    See: https://github.com/P-H-C/phc-string-format/blob/master/phc-sf-spec.md

    Example:
        "pbkdf2:sha256:10000$qeqixO61snFa$17355c7c3bb99947a1122dedfaa86c5467cb6e95da344d0661dba5e62ac902c7"

        <algorithm>:<digest>:<iterations>$<salt>$<hash>
        The salt is not hex, but needs to be converted to base 64 with padding ("=") removed
        The hash is hex format, which needs to be converted to base 64 with padding ("=") removed
    """
    if password is None or len(password) == 0:
        return  # type: ignore[return-value] # Return value expected
    if password.count("$") < 2:
        return  # type: ignore[return-value] # Return value expected
    _, salt, hashed = password.split("$")
    if salt is None or hashed is None:
        return
    try:
        b64_salt = (
            codecs.encode(bytes(salt, "utf-8"), "base64")
            .decode()
            .replace("=", "")
            .rstrip()
        )
        b64_hash = (
            codecs.encode(codecs.decode(hashed, "hex"), "base64")
            .decode()
            .replace("=", "")
            .rstrip()
        )
    except Exception:
        return  # type: ignore[return-value] # Return value expected
    return f"${ALGORITHM}-{DIGEST}$i={ITERATIONS},l={KEYLEN}${b64_salt}${b64_hash}"


DIGEST = "sha256"
ITERATIONS = 10_000
KEYLEN = 32
