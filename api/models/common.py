import enum


class PrivilegeType(str, enum.Enum):
    """
    The levels of permission are reflected in the ordering here, e.g.
    `anonymous` is most restrictive.
    """

    STANDARD = "standard"
    EDUCATION_ONLY = "education_only"
    INTERNATIONAL = "international"
    ANONYMOUS = "anonymous"
