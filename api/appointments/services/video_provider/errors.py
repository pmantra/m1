class RequiredParameterException(Exception):
    """
    Raised when we require a parameter that was not provided
    """

    pass


class VideoPlatformException(Exception):
    """
    Raised when the partner video platform raises an unexpected error
    """

    pass
