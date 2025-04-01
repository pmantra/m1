def get_member_availability_from_message(message_body: str) -> str:
    """
    Pulls out the availability section of a message body. Returns empty string on error
    """
    start = message_body.find("(in order of preference):\n\n") + 26
    end = message_body.find("\n\nIf any of these dates/times")

    if start == -1 or end == -1:
        return ""

    return message_body[start:end]
