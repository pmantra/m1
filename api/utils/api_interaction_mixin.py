import json
import logging
import random
import string
from typing import Optional

from flask import Response

from authn.models.user import User
from l10n.config import CUSTOM_LOCALE_HEADER
from utils.log import logger

log = logger(__name__)

# hide fixture logging :)
logging.getLogger("factory").setLevel(logging.INFO)
logging.getLogger("schemas.io").setLevel(logging.INFO)
logging.getLogger("faker").setLevel(logging.WARNING)


class APIInteractionMixin:
    def standard_headers(self, user: Optional[User]) -> dict:
        if user:
            return {"x-maven-user-id": str(user.id)}
        return {}

    def json_headers(self, user: Optional[User] = None) -> dict:
        headers = self.standard_headers(user)
        headers.update({"Content-Type": "application/json"})
        return headers

    def with_locale_header(self, headers: dict, locale: str) -> dict:
        headers.update({CUSTOM_LOCALE_HEADER: locale})
        return headers

    def json_data(self, data_dict: dict) -> str:
        return json.dumps(data_dict)

    def load_json(self, response: Response) -> dict:
        string = response.data.decode("utf-8")
        return json.loads(string)

    def _get_random_string(
        self,
        char_choices: Optional[str] = None,
        char_class: str = "ascii_letters",
        max_chars: int = 20,
        min_chars: int = 1,
    ) -> str:
        """
        Generate a random string based on character choices and size.
        :param char_choices: if provided and is a string, use it as the character choices;
            otherwise use string classes defined by char_class.
        :param char_class: the importable character class name from string;
            if not existing, default to ascii_letters.
        :param max_chars: maximum character size of the random string
        :param min_chars: minimum character size of the random string
        :return: a random string
        """
        if char_choices and isinstance(char_choices, str):
            characters = char_choices
        else:
            try:
                characters = getattr(string, char_class)
            except AttributeError:
                characters = string.ascii_letters

        return "".join(
            random.choices(characters, k=random.choice(range(min_chars, max_chars)))
        )
