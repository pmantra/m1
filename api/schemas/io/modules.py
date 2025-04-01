import warnings
from typing import Dict, List, Optional, Tuple

from models.enterprise import Assessment, AssessmentLifecycle, AssessmentLifecycleTrack
from models.marketing import TextCopy
from models.programs import Module, Phase, module_vertical_groups
from models.verticals_and_specialties import VerticalGroup, VerticalGroupTrack
from storage.connection import db

from .sorting import sorted_by


@sorted_by("name")
def export():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    return [
        dict(
            name=m.name,
            frontend_name=m.frontend_name,
            phase_logic=m.phase_logic.value,
            program_length_logic=m.program_length_logic.value,
            days_in_transition=m.days_in_transition,
            duration=m.duration,
            is_maternity=m.is_maternity,
            json=m.json,
            partner_module=(m.partner_module and m.partner_module.name),
            intro_message_text_copy=(
                m.intro_message_text_copy and m.intro_message_text_copy.name
            ),
            phases=[
                dict(
                    name=p.name,
                    frontend_name=p.frontend_name,
                    is_entry=p.is_entry,
                    is_transitional=p.is_transitional,
                    onboarding_assessment_lifecycle=(
                        p.onboarding_assessment_lifecycle
                        and p.onboarding_assessment_lifecycle.name
                    ),
                    auto_transition_module=(
                        p.auto_transition_module and p.auto_transition_module.name
                    ),
                    json=p.json,
                )
                for p in m.phases
            ],
            vertical_groups=[v.name for v in m.vertical_groups],
            onboarding_as_partner=m.onboarding_as_partner,
            onboarding_display_label=m.onboarding_display_label,
            onboarding_display_order=m.onboarding_display_order,
            restrict_booking_verticals=m.restrict_booking_verticals,
        )
        for m in Module.query
    ]


def _restore_modules(
    modules: List[dict],
) -> Tuple[Dict[Optional[str], Optional[int]], List[dict]]:
    # Fetch the required associations.
    vertical_group_id_by_name = {
        v.name: v.id
        for v in db.session.query(VerticalGroup.name, VerticalGroup.id).all()
    }
    vertical_groups_by_module_name = {}
    text_copy_id_by_name = {
        t.name: t.id for t in db.session.query(TextCopy.name, TextCopy.id).all()
    }
    if not (vertical_group_id_by_name and text_copy_id_by_name):
        warnings.warn(  # noqa  B028  TODO:  No explicit stacklevel keyword argument found. The warn method from the warnings module uses a stacklevel of 1 by default. This will only show a stack trace for the line on which the warn method is called. It is therefore recommended to use a stacklevel of 2 or greater to provide more information to the user.
            "Restoring modules without Verticals AND Text Copy "
            "will result in incomplete data!"
        )
    else:
        # Special case for modules with no associated intro message
        text_copy_id_by_name[None] = None
        # Build out the associations for existing data
        for m in modules:
            # Map the module-name -> vertical-group-ids
            vertical_groups_by_module_name[m["name"]] = {
                vertical_group_id_by_name[n]
                for n in vertical_group_id_by_name.keys() & {*m["vertical_groups"]}
            }
            # Associate the module to the existing text copy
            m["intro_message_text_copy_id"] = text_copy_id_by_name[
                m["intro_message_text_copy"]
            ]
    # Create the modules
    db.session.bulk_insert_mappings(Module, modules)
    # Get a mapping of module-name -> module-id
    module_id_by_name = {
        m.name: m.id for m in db.session.query(Module.name, Module.id).all()
    }
    # Associate the partner modules
    partner_module_associations = [
        {
            "id": module_id_by_name[m["name"]],
            "partner_module_id": module_id_by_name[m["partner_module"]],
        }
        for m in modules
        if m["partner_module"]
    ]
    db.session.bulk_update_mappings(Module, partner_module_associations)
    # If we have vertical group associations, add them to the database
    if vertical_groups_by_module_name:
        vertical_groups_modules = []
        vertical_groups_tracks = []
        for name, groups in vertical_groups_by_module_name.items():
            if groups:
                m_id = module_id_by_name[name]
                vertical_groups_modules.extend(
                    ({"module_id": m_id, "vertical_group_id": vgid} for vgid in groups)
                )
                vertical_groups_tracks.extend(
                    ({"track_name": name, "vertical_group_id": vgid} for vgid in groups)
                )
        db.session.execute(module_vertical_groups.insert(), vertical_groups_modules)
        db.session.bulk_insert_mappings(VerticalGroupTrack, vertical_groups_tracks)
    # Special case for auto-transition configuration
    module_id_by_name[None] = None
    phases = [
        p.update(module_name=m["name"]) or p for m in modules for p in m["phases"]
    ]
    return module_id_by_name, phases


def _restore_phases(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    phases: List[dict],
    module_id_by_name: Dict[Optional[str], Optional[int]],
    with_assessments: bool,
):
    # If we have signaled for assessments, fetch them and build our associations
    assessment_lifecycle_id_by_name = {}
    if with_assessments:
        # Get a mapping of (lifecycle-name, assessment-version) -> assessment-id
        assessment_id_by_key = {
            (a.name, a.version): a.id
            for a in db.session.query(
                AssessmentLifecycle.name, Assessment.version, Assessment.id
            )
            .select_from(Assessment)
            .join(AssessmentLifecycle)
            .all()
        }
        # Get a mapping of assessment-lifecycle-name -> assessment-lifecycle-id
        assessment_lifecycle_id_by_name = {
            al.name: al.id
            for al in db.session.query(
                AssessmentLifecycle.name, AssessmentLifecycle.id
            ).filter(
                AssessmentLifecycle.name.in_(
                    (
                        p["onboarding_assessment_lifecycle"]
                        for p in phases
                        if p["onboarding_assessment_lifecycle"]
                    )
                )
            )
        }
        # If we've asked for assessments, they must exist!
        assert (
            assessment_id_by_key and assessment_lifecycle_id_by_name
        ), "Phases with assessments require Assessments to be restored."
        # Special case for phase with no associated assessment lifecycle.
        assessment_lifecycle_id_by_name[None] = None

    assessment_lifecycle_id_by_module_name = {}
    for phase in phases:
        onboarding_assessment_lifecycle_id = None
        if with_assessments:
            onboarding_assessment_lifecycle_id = assessment_lifecycle_id_by_name[
                phase["onboarding_assessment_lifecycle"]
            ]

            if onboarding_assessment_lifecycle_id:
                assessment_lifecycle_id_by_module_name[
                    phase["module_name"]
                ] = onboarding_assessment_lifecycle_id

        phase.update(
            module_id=module_id_by_name[phase["module_name"]],
            auto_transition_module_id=module_id_by_name[
                phase["auto_transition_module"]
            ],
            onboarding_assessment_lifecycle_id=onboarding_assessment_lifecycle_id,
        )

    # Create the phases
    db.session.bulk_insert_mappings(Phase, phases)

    # Update the assessment_lifecycle_tracks_values_to_insert association table
    if with_assessments:
        db.session.bulk_insert_mappings(
            AssessmentLifecycleTrack,
            [
                dict(
                    assessment_lifecycle_id=assessment_lifecycle_id,
                    track_name=module_name,
                )
                for (
                    module_name,
                    assessment_lifecycle_id,
                ) in assessment_lifecycle_id_by_module_name.items()
            ],
        )


def _restore(mm, with_assessments):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    module_id_by_name, phases = _restore_modules(mm)
    _restore_phases(phases, module_id_by_name, with_assessments)


def restore(mm):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    return _restore(mm, with_assessments=True)


def restore_without_assessments(mm):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    return _restore(mm, with_assessments=False)
