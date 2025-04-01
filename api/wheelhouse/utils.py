
class InvalidBooleanException(Exception):
    pass

def get_boolean_value(field: any) -> bool:
    if isinstance(field, str):
        normalized = field.strip().lower()
        if normalized == "true":
            return True
        elif normalized == "false":
            return False
        raise InvalidBooleanException(f"{field} cannot be resolved to a boolean.")
    elif isinstance(field, bool):
        return bool
    elif isinstance(field, int):
        return bool(field)