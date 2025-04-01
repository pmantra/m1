from datetime import datetime, timedelta

from models.programs import CareProgram
from storage.connection import db


def get_active_non_transitioned_care_programs():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    active_programs = (
        db.session.query(CareProgram)
        .filter(CareProgram.ended_at.is_(None), CareProgram.scheduled_end.is_(None))
        .all()
    )

    schedule_to_end = []
    for p in active_programs:
        try:
            m = p.current_module
            if not m:
                print("No current module %s" % p)
                continue
            tp = m.transitional_phase
            ph = p.current_phase.phase
            if not ph:
                print("No current phase for %s" % p)
                continue
            if m.name not in ("pregnancy", "postpartum"):
                print("No EOP transition set yet for %s" % p)
                continue
            if ph == tp:
                print("Already in transition %s" % p)
                continue

            schedule_to_end.append(p)
        except Exception as e:
            print(e, p)
            continue

    return schedule_to_end


def print_active_non_transitioned_care_programs():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    programs = get_active_non_transitioned_care_programs()
    for p in programs:
        print("%s, %s" % (p.user.id, p.current_module.name))


def set_program_scheduled_end_time(programs=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    today = datetime.utcnow()
    programs = programs or get_active_non_transitioned_care_programs()
    for p in programs:
        m = p.current_module
        days_in_transition = m.days_in_transition or 14
        ph = p.current_phase
        hp = p.user.health_profile
        if not hp:
            print("Program user has no health profile %s" % p)
            continue

        if m.name == "pregnancy" and not p.scheduled_end:
            due_date = hp.due_date or today
            p.scheduled_end = due_date + timedelta(days=(168 + days_in_transition))

        elif m.name == "postpartum" and not p.scheduled_end:
            # expired programs
            if (
                ph.phase.name == "week-63"
                and (ph.started_at + timedelta(days=7)) < today
            ):
                p.scheduled_end = today + timedelta(days=days_in_transition)
            else:
                last_child_birthday = hp.last_child_birthday or today
                p.scheduled_end = last_child_birthday + timedelta(
                    days=(168 + days_in_transition)
                )

        db.session.add(p)
        db.session.commit()


def calibrate_program_scheduled_end_time():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    programs = (
        db.session.query(CareProgram)
        .filter(CareProgram.ended_at.is_(None), CareProgram.scheduled_end.isnot(None))
        .all()
    )
    print("Total programs considering for calibration: %s" % len(programs))

    for program in programs:
        module = program.current_module
        if module and module.name in ("pregnancy", "postpartum"):
            _calc_scheduled_end = program.calculate_scheduled_end_time(module)
            if _calc_scheduled_end != program.scheduled_end:
                print(
                    "%s is recalculated ends at %s. Module=%s Gap=%s"
                    % (
                        program,
                        _calc_scheduled_end,
                        module,
                        (_calc_scheduled_end - program.scheduled_end),
                    )
                )

                program.scheduled_end = _calc_scheduled_end
                db.session.add(program)
                db.session.commit()
