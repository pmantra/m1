import enum


class StateMatchType(enum.Enum):

    """
    Each booked appointment must have a state match type.

    in-state: At time of booking, member state matches practitioner certified state
    out-of-state: At time of booking, member state does not match practitioner certified state
    missing: If practitioner certified state OR member state is missing
    """

    IN_STATE = "in_state"
    OUT_OF_STATE = "out_of_state"
    MISSING = "missing"
