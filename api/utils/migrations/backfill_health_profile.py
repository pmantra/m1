import time

import numpy as np

from health.models.health_profile import HealthProfile, HealthProfileHelpers
from storage.connection import db

NUM_CHUNKS = 1000


def get_string_from_health_profile_object(health_profile: HealthProfile) -> str:
    hp_json = health_profile.json
    children_obj = HealthProfileHelpers.get_children_from_json(hp_json)
    children_text = (
        f"{HealthProfileHelpers.dump_to_json_with_date(children_obj)}"
        if children_obj
        else "[]"
    )
    children_text = children_text.replace("'", "''")

    children_age_obj = HealthProfileHelpers.get_children_with_age_from_json(hp_json)
    children_age_text = (
        f"{HealthProfileHelpers.dump_to_json_with_date(children_age_obj)}"
        if children_age_obj
        else "[]"
    )
    children_age_text = children_age_text.replace("'", "''")

    last_child_birthday = HealthProfileHelpers.get_last_child_birthday_from_json(
        hp_json
    )
    last_birthday_text = f"'{last_child_birthday}'" if last_child_birthday else "NULL"

    bmi = HealthProfileHelpers.get_bmi_from_json(hp_json)
    bmi_text = float(bmi) if bmi else "NULL"

    age = HealthProfileHelpers.get_age_from_json(hp_json)
    age_text = age if age else "NULL"
    query_string = (
        f"UPDATE health_profile SET "
        f"bmi_persisted = {bmi_text}, "
        f"age_persisted = {age_text}, "
        f"last_child_birthday_persisted = {last_birthday_text}, "
        f"children_persisted = '{children_text}', "
        f"children_with_age_persisted = '{children_age_text}' "
        f"WHERE user_id = {health_profile.user_id};"
    )
    return query_string


def process_profile_chunk(start_id: int, end_id: int):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    start_time = time.time()
    hp_list = HealthProfile.query.filter(
        HealthProfile.user_id.between(start_id, end_id)
    ).all()
    if not hp_list:
        print(f"No items found between {start_id} and {end_id}")
        return
    health_profile_query = "\n".join(
        [get_string_from_health_profile_object(x) for x in hp_list if x.json]
    )
    query_time = time.time()
    try:
        db.session.execute(health_profile_query)
        db.session.commit()
    except Exception as ex:
        print(f"Error {ex}")
        print(f"query: {health_profile_query}")
        db.session.rollback()

    commit_time = time.time()
    print(
        f"Rows processed: {len(hp_list)}, "
        f"Pull time: {query_time - start_time}, "
        f"Commit time: {commit_time - query_time}, "
        f"Full run: {commit_time - start_time}, "
        f"Start ID: {start_id}, End ID: {end_id}"
    )


def process_full_backfill(num_chunks: int = NUM_CHUNKS, chunks_to_run: int = None):  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[assignment] # Incompatible default for argument "chunks_to_run" (default has type "None", argument has type "int")
    """
    PRIMARY ENTRY POINT
    Usage: Run in dev shell in target environment. Failures where DB is shown as not accessible
    can be resolved through running db.session.rollback()
    """
    max_id = db.session.execute("SELECT max(user_id) from health_profile").fetchall()[
        0
    ][0]
    min_id = db.session.execute("SELECT min(user_id) from health_profile").fetchall()[
        0
    ][0]

    # Commit here prevents hanging session after the script closes
    db.session.commit()

    if not max_id or not min_id:
        print("No max or min, not running")
        return

    size_diff = max_id - min_id

    if size_diff == 0 or size_diff < num_chunks:
        range_list = [min_id]
    else:
        range_list = list(
            np.arange(min_id, max_id, round((max_id - min_id) / num_chunks))
        )

    # Get 1 higher than the max ID to ensure the highest value is updated
    range_list.append(max_id + 1)

    for i, num in enumerate(range_list[:-1]):
        # Chunks are processed inclusive of the ends, this will ensure all rows are updated
        start_id = int(num)
        end_id = int(range_list[i + 1] - 1)
        if chunks_to_run and i > chunks_to_run:
            break
        process_profile_chunk(start_id=start_id, end_id=end_id)
