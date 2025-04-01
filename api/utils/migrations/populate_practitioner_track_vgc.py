from models.profiles import PractitionerProfile
from models.tracks import TrackName
from models.verticals_and_specialties import Vertical
from provider_matching.models.practitioner_track_vgc import PractitionerTrackVGC
from provider_matching.models.vgc import VGC
from storage.connection import db
from tasks.queues import job
from utils.log import logger

log = logger(__name__)

CARE_TEAM_BY_TRACK = {
    TrackName.ADOPTION: {
        VGC.ADOPTION_COACH: [
            162641,
            233509,
            247480,
        ],
        VGC.MENTAL_HEALTH: [
            130702,
            101733,
            178299,
            242832,
            171128,
            99916,
            24473,
        ],
        VGC.PEDIATRICIAN: [
            101798,
            32643,
            10117,
            210550,
            212864,
        ],
        VGC.REPRODUCTIVE_ENDOCRINOLOGIST: [
            146189,
            167335,
            262918,
            268274,
            267062,
        ],
        VGC.REPRODUCTIVE_NURSE: [
            234306,
            233842,
            239468,
        ],
        VGC.WELLNESS_COACH: [248858],
    },
    TrackName.BREAST_MILK_SHIPPING: {
        # For Breast Milk Shipping we split the lactation consultants into two groups to give each member
        # 2 options instead of one.
        VGC.LACTATION_CONSULTANT: [
            75,
            104,
            194,
            292259,
            298862,
            308931,
            190143,
            149829,
            261923,
            82044,
            301365,
            158841,
        ],
    },
    TrackName.EGG_FREEZING: {
        VGC.REPRODUCTIVE_ENDOCRINOLOGIST: [
            262918,
            268274,
            146189,
            167335,
            267062,
        ],
        VGC.MENTAL_HEALTH: [
            130702,
            79232,
            242832,
            171128,
            101733,
            149553,
            99916,
        ],
        VGC.NUTRITIONIST: [
            154463,
            194683,
            522,
            66507,
        ],
        VGC.OB_GYN: [
            2587,
            37607,
            135005,
            190233,
            149557,
            37964,
            78506,
            91086,
        ],
        VGC.REPRODUCTIVE_NURSE: [
            234306,
            233842,
            239468,
        ],
        VGC.OTHER_WELLNESS: [
            143062,
        ],
        VGC.EGG_DONOR_CONSULTANT: [
            173523,
        ],
        VGC.WELLNESS_COACH: [248858],
    },
    TrackName.FERTILITY: {
        VGC.REPRODUCTIVE_ENDOCRINOLOGIST: [
            262918,
            268274,
            146189,
            167335,
            267062,
        ],
        VGC.MENTAL_HEALTH: [
            130702,
            79232,
            242832,
            171128,
            101733,
            149553,
            99916,
        ],
        VGC.OTHER_WELLNESS: [
            143062,
        ],
        VGC.OB_GYN: [
            2587,
            135005,
            190233,
            37964,
            149557,
            78506,
            91086,
        ],
        VGC.NUTRITIONIST: [
            154463,
            194683,
            522,
            66507,
        ],
        VGC.REPRODUCTIVE_NURSE: [
            234306,
            233842,
            239468,
        ],
        VGC.WELLNESS_COACH: [248858],
    },
    TrackName.GENERAL_WELLNESS: {
        VGC.OB_GYN: [
            2587,
            78506,
            76371,
            135005,
            91086,
        ],
        VGC.CAREER_COACH: [
            262465,
            143143,
            123571,
            141342,
            267082,
        ],
        VGC.MENTAL_HEALTH: [
            178299,
            101733,
            149553,
            242832,
            171128,
            99916,
            24473,
        ],
        VGC.NUTRITIONIST: [
            154463,
            194683,
            522,
            66507,
        ],
        VGC.OTHER_WELLNESS: [
            143062,
        ],
        VGC.FERTILITY_AWARENESS_EDUCATOR: [
            209044,
            274304,
            274770,
            270465,
        ],
        VGC.WELLNESS_COACH: [248858],
    },
    TrackName.PARENTING_AND_PEDIATRICS: {
        VGC.PEDIATRICIAN: [
            101798,
            32643,
            10117,
            210550,
            212864,
        ],
        VGC.MENTAL_HEALTH: [
            79232,
            101733,
            214847,
            242832,
            171128,
            149553,
            99916,
            24473,
        ],
        VGC.PARENT_COACH: [
            217364,
            216130,
            217962,
        ],
        VGC.SLEEP_COACH: [
            56070,
            51393,
            161633,
            54804,
            154103,
            158929,
            187733,
            155166,
            183663,
            215095,
            143033,
            221009,
            308349,
        ],
        VGC.CHILDCARE_CONSULTANT: [
            217973,
            218273,
        ],
        VGC.WELLNESS_COACH: [248858],
    },
    TrackName.PARTNER_FERTILITY: {
        VGC.REPRODUCTIVE_NURSE: [
            234306,
            233842,
            239468,
        ],
        VGC.REPRODUCTIVE_ENDOCRINOLOGIST: [
            262918,
            268274,
            146189,
            167335,
            267062,
        ],
        VGC.MENTAL_HEALTH: [
            130702,
            79232,
            242832,
            171128,
            101733,
            149553,
            99916,
            24473,
        ],
        VGC.NUTRITIONIST: [
            154463,
            194683,
            522,
            66507,
        ],
        VGC.FERTILITY_AWARENESS_EDUCATOR: [
            209044,
            274304,
            274770,
            270465,
        ],
        VGC.WELLNESS_COACH: [248858],
    },
    TrackName.PARTNER_NEWPARENT: {
        VGC.SLEEP_COACH: [
            56070,
            51393,
            161633,
            54804,
            154103,
            158929,
            187733,
            155166,
            183663,
            215095,
            143033,
            221009,
            308349,
        ],
        VGC.PEDIATRICIAN: [
            101798,
            32643,
            10117,
            210550,
            212864,
        ],
        VGC.MENTAL_HEALTH: [
            188212,
            117233,
            206257,
            178299,
            99916,
            130702,
            101733,
            149553,
            79232,
            242832,
            171128,
        ],
        VGC.CAREER_COACH: [
            123571,
            141342,
            143143,
            267082,
        ],
        VGC.NUTRITIONIST: [
            154463,
            194683,
            522,
            66507,
        ],
        VGC.WELLNESS_COACH: [248858],
    },
    TrackName.PARTNER_PREGNANT: {
        VGC.OB_GYN: [
            2587,
            37607,
            135005,
            190233,
            78506,
            37964,
            76371,
            91086,
        ],
        VGC.LACTATION_CONSULTANT: [
            75,
            104,
            190143,
            149829,
            261923,
            17,
            82739,
            82044,
            194,
            292259,
            301365,
            298862,
            158841,
            308931,
        ],
        VGC.MENTAL_HEALTH: [
            24473,
            101733,
            149553,
            188212,
            242832,
            171128,
            99916,
            24473,
        ],
        VGC.DOULA: [
            130767,
            3886,
            1545,
            255200,
        ],
        VGC.NUTRITIONIST: [
            149555,
            154463,
            194683,
            522,
            66507,
        ],
        VGC.CAREER_COACH: [
            262465,
            123571,
            141342,
            143143,
            267082,
        ],
        VGC.WELLNESS_COACH: [248858],
    },
    TrackName.POSTPARTUM: {
        VGC.SLEEP_COACH: [
            56070,
            51393,
            161633,
            54804,
            154103,
            158929,
            187733,
            155166,
            183663,
            215095,
            143033,
            221009,
            308349,
        ],
        VGC.LACTATION_CONSULTANT: [
            17,
            82739,
            261923,
            581,
            82044,
            194,
            292259,
            301365,
            298862,
            158841,
            308931,
        ],
        VGC.PEDIATRICIAN: [
            101798,
            32643,
            10117,
            210550,
            212864,
        ],
        VGC.MENTAL_HEALTH: [
            188212,
            117233,
            206257,
            178299,
            99916,
            130702,
            101733,
            149553,
            79232,
            242832,
            171128,
        ],
        VGC.CAREER_COACH: [
            123571,
            141342,
            143143,
            267082,
        ],
        VGC.PHYSICAL_THERAPY: [
            48023,
            56,
            209057,
            190396,
            146441,
            204543,
        ],
        VGC.WELLNESS_COACH: [248858],
    },
    TrackName.PREGNANCY: {
        VGC.OB_GYN: [
            2587,
            37607,
            135005,
            190233,
            78506,
            37964,
            76371,
            91086,
        ],
        VGC.LACTATION_CONSULTANT: [
            75,
            104,
            190143,
            149829,
            261923,
            17,
            82739,
            581,
            82044,
            194,
            292259,
            301365,
            298862,
            158841,
            308931,
        ],
        VGC.MENTAL_HEALTH: [
            24473,
            101733,
            149553,
            188212,
            242832,
            171128,
            99916,
        ],
        VGC.DOULA: [
            130767,
            3886,
            1545,
            255200,
        ],
        VGC.NUTRITIONIST: [
            149555,
            154463,
            194683,
            522,
            66507,
        ],
        VGC.CAREER_COACH: [
            262465,
            123571,
            141342,
            143143,
            267082,
        ],
        VGC.WELLNESS_COACH: [248858],
    },
    TrackName.PREGNANCYLOSS: {
        VGC.MENTAL_HEALTH: [
            130702,
            79232,
            188212,
            242832,
            171128,
            101733,
            149553,
            99916,
        ],
        VGC.OB_GYN: [
            2587,
            37607,
            135005,
            78506,
            91086,
        ],
        VGC.OTHER_WELLNESS: [
            143062,
        ],
        VGC.REPRODUCTIVE_ENDOCRINOLOGIST: [
            146189,
            262918,
            268274,
            167335,
            267062,
        ],
        VGC.REPRODUCTIVE_NURSE: [
            234306,
            233842,
            239468,
        ],
        VGC.WELLNESS_COACH: [248858],
    },
    TrackName.SURROGACY: {
        VGC.SURROGACY_COACH: [
            160965,
            237069,
            214587,
        ],
        VGC.REPRODUCTIVE_NURSE: [
            234306,
            239468,
        ],
        VGC.REPRODUCTIVE_ENDOCRINOLOGIST: [
            262918,
            268274,
            146189,
            167335,
            260097,
            267062,
        ],
        VGC.PEDIATRICIAN: [
            101798,
            32643,
            10117,
            210550,
            212864,
        ],
        VGC.OB_GYN: [
            2587,
            37607,
            135005,
            190233,
            78506,
            37964,
            76371,
            91086,
        ],
        VGC.MENTAL_HEALTH: [
            242832,
            171128,
            130702,
            101733,
            149553,
            178299,
            99916,
            24473,
        ],
        VGC.WELLNESS_COACH: [248858],
    },
    TrackName.TRYING_TO_CONCEIVE: {
        VGC.OB_GYN: [
            2587,
            78506,
            76371,
            135005,
            91086,
        ],
        VGC.CAREER_COACH: [
            262465,
            143143,
            123571,
            141342,
            267082,
        ],
        VGC.MENTAL_HEALTH: [
            178299,
            101733,
            149553,
            242832,
            171128,
            149553,
            99916,
        ],
        VGC.NUTRITIONIST: [
            154463,
            194683,
            522,
            66507,
        ],
        VGC.OTHER_WELLNESS: [
            143062,
        ],
        VGC.FERTILITY_AWARENESS_EDUCATOR: [
            209044,
            274304,
            274770,
            270465,
        ],
        VGC.WELLNESS_COACH: [248858],
    },
    # Generic track is used rarely and isn't a track that requires onboarding
    # see: https://mavenclinic.slack.com/archives/CH25MRT1S/p1607705650093200
    TrackName.GENERIC: {},
}


@job
def populate_prod():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    for track in CARE_TEAM_BY_TRACK:
        for vgc in CARE_TEAM_BY_TRACK[track]:  # type: ignore[attr-defined] # "object" has no attribute "__iter__"; maybe "__dir__" or "__str__"? (not iterable)
            for p_id in CARE_TEAM_BY_TRACK[track][vgc]:  # type: ignore[index] # Value of type "object" is not indexable
                practitioner = db.session.query(PractitionerProfile).get(p_id)

                if not practitioner:
                    log.warning("Practitioner not found", user_id=p_id)
                    continue

                # Check that ptvgc does not already exist
                existing_ptvgc = PractitionerTrackVGC.query.filter_by(
                    practitioner_id=p_id, track=track.value, vgc=vgc.value
                ).one_or_none()
                if existing_ptvgc:
                    log.info(
                        "PractitionerTrackVGC row already exists in table",
                        practitioner_id=p_id,
                        track=track.value,
                        vgc=vgc.value,
                    )
                else:
                    ptvgc = PractitionerTrackVGC(
                        practitioner_id=p_id,
                        track=track.value,
                        vgc=vgc.value,
                    )

                    log.info(
                        "Adding PractitionerTrackVGC row",
                        practitioner_id=p_id,
                        track=track.value,
                        vgc=vgc.value,
                    )

                    db.session.add(ptvgc)

            db.session.commit()


def _get_one_associated_vertical(vgc):  # type: ignore[no-untyped-def] # Function is missing a type annotation

    if vgc == VGC.MENTAL_HEALTH:
        vertical_name_to_look_for = "Mental health provider"
    elif vgc == VGC.DOULA:
        vertical_name_to_look_for = "Doula and childbirth educator"
    elif vgc == VGC.SLEEP_COACH:
        vertical_name_to_look_for = "Pediatric sleep coach"
    elif vgc == VGC.OTHER_WELLNESS:
        vertical_name_to_look_for = "Certified nutritional therapy practitioner"
    elif vgc == VGC.REPRODUCTIVE_NURSE:
        vertical_name_to_look_for = "Nurse practitioner"
    elif vgc == VGC.OB_GYN:
        vertical_name_to_look_for = "OB-GYN"
    else:
        vertical_name_to_look_for = vgc

    vertical = (
        db.session.query(Vertical)
        .filter(Vertical.name == vertical_name_to_look_for)
        .one_or_none()
    )
    return vertical


def populate_dev():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    for track in CARE_TEAM_BY_TRACK:
        for vgc in CARE_TEAM_BY_TRACK[track]:  # type: ignore[attr-defined] # "object" has no attribute "__iter__"; maybe "__dir__" or "__str__"? (not iterable)
            vertical = _get_one_associated_vertical(vgc)

            if not vertical:
                log.warning("No vertical found for this VGC", vgc=vgc.value)
                continue

            p_profiles_that_serve_vertical = (
                PractitionerProfile.query.join(PractitionerProfile.verticals)
                .filter(Vertical.id == vertical.id)
                .all()
            )

            p_ids_that_serve_vertical = [
                pp.user_id for pp in p_profiles_that_serve_vertical
            ]
            if not p_ids_that_serve_vertical:
                log.warning("No users that serve VGC")
                continue

            for p_id in p_ids_that_serve_vertical:

                # Check that ptvgc does not already exist
                existing_ptvgc = PractitionerTrackVGC.query.filter_by(
                    practitioner_id=p_id, track=track.value, vgc=vgc.value
                ).one_or_none()
                if existing_ptvgc:
                    log.info(
                        "PractitionerTrackVGC row already exists in table",
                        practitioner_id=p_id,
                        track=track.value,
                        vgc=vgc.value,
                    )
                else:
                    ptvgc = PractitionerTrackVGC(
                        practitioner_id=p_id,
                        track=track.value,
                        vgc=vgc.value,
                    )
                    log.info(
                        "Adding PractitionerTrackVGC row",
                        practitioner_id=p_id,
                        track=track.value,
                        vgc=vgc.value,
                    )
                    db.session.add(ptvgc)

            db.session.commit()
