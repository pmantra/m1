from flask_babel import lazy_gettext

from l10n.lazy_string_encoder import JSONEncoderForHTMLAndLazyString


def test_it_encodes_a_lazy_string():
    encoder = JSONEncoderForHTMLAndLazyString()

    encoded = encoder.encode(lazy_gettext("foo"))

    assert encoded == '"foo"'
