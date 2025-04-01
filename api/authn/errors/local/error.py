from typing import Any


class PasswordStrengthCheckError(Exception):
    def __init__(self, errors: Any):
        self.errors = errors

    def __str__(self) -> str:
        if isinstance(self.errors, list):
            return str(self.errors[0])
        else:
            return self.errors
