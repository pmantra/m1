import pytest

from utils.exceptions import _obfuscate_parameters


@pytest.mark.parametrize(
    argnames="url,expected",
    argvalues=[
        (
            "url.com/?foo=bar&email=email%40foo.com&date_of_birth=10-01-88",
            "url.com/?foo=bar&email=***&date_of_birth=***",
        ),
        (
            "url.com/;foo=bar&email=email%40foo.com;date_of_birth=10-01-88",
            "url.com/;foo=bar&email=***;date_of_birth=***",
        ),
        (
            "url.com/;foo=bar;name=Princess%20Zelda;username=boss.lady1",
            "url.com/;foo=bar;name=***;username=***",
        ),
        (
            "url.com/;foo=bar;first_name=Zelda?username=boss.lady1",
            "url.com/;foo=bar;first_name=***?username=***",
        ),
    ],
)
def test_obfuscate_parameters(url: str, expected: str):
    # When
    obfuscated = _obfuscate_parameters(url)
    # Then
    assert obfuscated == expected
