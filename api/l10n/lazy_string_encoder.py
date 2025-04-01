from typing import Any

from flask_babel import LazyString
from simplejson import JSONEncoderForHTML


class JSONEncoderForHTMLAndLazyString(JSONEncoderForHTML):
    """
    An encoder that supports LazyString from flask_babel.
    simplejson enforces a hard type check and will raise a TypeError instead
    of casting to a str
    """

    def default(self, o: Any) -> Any:
        if type(o) is LazyString:
            return str(o)
        return super().default(o)
