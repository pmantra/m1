import uuid
from datetime import datetime

from utils import log

logger = log.logger(__name__)


def generate_enrollment_id(
    cur_mt, mt_enrollment_mapping, prev_mt=None, prev_pid=None, family_mts=None
):
    program_id = generate_program_id(cur_mt, prev_mt, prev_pid)
    enrollment_id = str(program_id)
    if mt_enrollment_mapping and cur_mt.id in mt_enrollment_mapping:
        # in this case, just use previously associated enrollment_id
        return mt_enrollment_mapping.get(cur_mt.id)
    if family_mts and has_overlap(family_mts):
        if all_can_transition(family_mts):
            # get the enrollment_id of the first member_track
            return mt_enrollment_mapping.get(family_mts[0].id)

    return enrollment_id


def generate_program_id(cur_mt, prev_mt, prev_pid):
    if is_first_member_track(prev_mt):
        return uuid.uuid1()
    if not can_transition_from_prev(cur_mt, prev_mt):
        return uuid.uuid1()
    if is_early_renewal(cur_mt):
        return uuid.uuid1()
    if is_overlap(cur_mt, prev_mt):
        return prev_pid
    if is_duplicate(cur_mt, prev_mt):
        return prev_pid

    # default to generating new program id
    return uuid.uuid1()


def is_first_member_track(prev_mt):
    return prev_mt is None


def can_transition_from_prev(cur_mt, prev_mt):
    return str(cur_mt.name) in {str(t.name) for t in prev_mt.transitions}


def all_can_transition(mt_list):
    for pmt, cmt in zip(mt_list, mt_list[1:]):
        if not can_transition_from_prev(cmt, pmt):
            return False
    return True


def is_early_renewal(cur_mt):
    return cur_mt.activated_at > cur_mt.created_at


def is_overlap(cur_mt, prev_mt):
    return (
        datetime.date(prev_mt.created_at)
        < cur_mt.start_date
        < prev_mt.get_scheduled_end_date()
    )


def has_overlap(mt_list):
    for pmt, cmt in zip(mt_list, mt_list[1:]):
        if is_overlap(cmt, pmt):
            return True


def is_duplicate(cur_mt, prev_mt):
    return (
        cur_mt.name == prev_mt.name
        and cur_mt.created_at > prev_mt.created_at
        and cur_mt.creatd_at < prev_mt.ended_at
    )
