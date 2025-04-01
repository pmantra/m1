from os import environ
from unittest.mock import patch

from utils.rotatable_token import RotatableToken


def test_valid_rotatable_token():
    """
    When the jwt is decoded with a valid algorithm
    test that we can decode the token
    """
    with patch.dict(environ, {"NAME_PRIMARY": "TOKEN_PRIMARY"}):
        t = RotatableToken("NAME")
        data = {"things": "stuff"}
        encoded = t.encode(data)

    assert t.decode(encoded) == data


def test_invalid_rotatable_token():
    """
    When the jwt is encoded using "alg: none",
    test that we handle the specific error
    """
    with patch.dict(environ, {"NAME_PRIMARY": "TOKEN_PRIMARY"}):
        t = RotatableToken("NAME")
        # This is a token encoded with the algorithm set to "None", which is invalid per our jwt library
        bad_token = (
            "eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0."
            "eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ."
            "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        )

    assert t.decode(bad_token) is None
