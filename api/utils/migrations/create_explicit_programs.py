import datetime

from models.enterprise import OrganizationEmployee
from models.programs import CareProgram, CareProgramPhase, Module, Phase
from storage.connection import db
from utils.log import logger
from utils.phases import phase_dicts

log = logger(__name__)


def migrate_to_explicit_programs():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    add_modules_and_phases()

    all_employees = (
        db.session.query(OrganizationEmployee)
        .filter(OrganizationEmployee.user_id.isnot(None))
        .all()
    )

    log.debug("Got %d employees to migrate", len(all_employees))
    for org_emp in all_employees:
        migrate_enterprise_user(org_emp)

    log.debug("All done - committing to DB")
    db.session.commit()
    log.debug("All set!")


def migrate_enterprise_user(org_emp):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    # foo
    log.debug("Migrating %s", org_emp)

    if not org_emp.user:
        log.warning("No user for %s", org_emp)
        return

    if org_emp.user.current_program:
        log.warning("%s already has a program!", org_emp)
        return

    program = CareProgram(user=org_emp.user, organization_employee=org_emp)
    db.session.add(program)

    phase = program.update_user_phase()

    user = org_emp.user
    signup_at = org_emp.user.created_at.date()
    _info = program.calculate_phase_for_user()
    if _info.get("module") in ("pregnancy", "postpartum"):
        phase = _info.get("phase")
        if phase and phase.startswith("week"):
            current_week = int(
                phase.lstrip(  # noqa  B005  TODO:  Using .strip() with multi-character strings is misleading the reader. It looks like stripping a substring. Move your character set to a constant if this is deliberate. Use .replace(), .removeprefix(), .removesuffix(), or regular expressions to remove string fragments.
                    "week-"
                )
            )
            member_length = (datetime.datetime.utcnow().date() - signup_at).days
            member_weeks = int(member_length // 7)

            start_at = current_week - member_weeks
            # will go up to current week - 1 (0 index)
            log.debug(
                "Start: %s/Current: %s/Member %s", start_at, current_week, member_weeks
            )

            for week_num in range(start_at, current_week):
                if week_num > 0:
                    phase = Phase.query.filter_by(name="week-%d" % week_num).first()

                    _start = week_num - start_at
                    started_at = signup_at + datetime.timedelta(days=_start * 7)
                    ended_at = started_at + datetime.timedelta(days=7)
                    if phase:
                        history_phase = CareProgramPhase(
                            program=program,
                            phase=phase,
                            started_at=started_at,
                            ended_at=ended_at,
                        )
                        db.session.add(history_phase)
                        log.debug("Added %s", history_phase)
                    else:
                        log.debug("No phase for week %s", week_num)

    log.debug("Migrated user %s to %s", user, program)
    return program


def add_modules_and_phases():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    modules = add_modules()

    for k, v in phase_dicts.items():
        if Phase.query.filter_by(name=k).first():
            log.debug("Phase for %s exists", v["name"])
            continue

        phase = Phase(name=k, frontend_name=v["name"], content_url=v["phase_content"])

        if k.startswith("week"):
            week = int(
                k.lstrip(  # noqa  B005  TODO:  Using .strip() with multi-character strings is misleading the reader. It looks like stripping a substring. Move your character set to a constant if this is deliberate. Use .replace(), .removeprefix(), .removesuffix(), or regular expressions to remove string fragments.
                    "week-"
                )
            )
            if (week > 0) and (week < 40):
                phase.module = modules["pregnancy"]
            elif week > 0:
                phase.module = modules["postpartum"]
        else:
            phase.module = modules.get(k)

        db.session.add(phase)
        log.debug("Added %s", phase)

    if not Phase.query.filter_by(name="generic").first():
        p = Phase(name="generic", module=modules["generic"])
        db.session.add(p)

    db.session.commit()
    log.debug("All set!")


def add_modules():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    _modules = [
        Module(name="pregnancy"),
        Module(name="postpartum"),
        Module(name="fertility"),
        Module(name="egg_freezing"),
        Module(name="generic"),
    ]
    for _ in _modules:
        if Module.query.filter_by(name=_.name).first():
            continue
        else:
            db.session.add(_)
            db.session.commit()

    keyed = {}
    for m in Module.query.all():
        keyed[m.name] = m
    return keyed
