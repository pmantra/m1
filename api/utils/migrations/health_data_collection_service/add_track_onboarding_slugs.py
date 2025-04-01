# Simple Data Insert Script to create HDC Assessment Track relationship objects
from app import create_app
from models.tracks import TrackName
from models.tracks.assessment import AssessmentTrack
from storage.connection import db

data = {
    TrackName.SURROGACY.value: "surrogacy-welcome",
    TrackName.PARENTING_AND_PEDIATRICS.value: "parenting-and-pediatrics-welcome",
    TrackName.PARTNER_NEWPARENT.value: "partner-newparent-onboarding",
    TrackName.GENERAL_WELLNESS.value: "general-wellness-welcome",
    TrackName.BREAST_MILK_SHIPPING.value: "bms-onboarding",
    TrackName.EGG_FREEZING.value: "egg-freezing-welcome",
    TrackName.PREGNANCYLOSS.value: "loss",
    TrackName.PARTNER_FERTILITY.value: "partner-fertility-onboarding",
    TrackName.PREGNANCY.value: "pregnancy-welcome",
    TrackName.ADOPTION.value: "adoption-welcome",
    TrackName.FERTILITY.value: "fertility-welcome",
    TrackName.PARTNER_PREGNANT.value: "partner-pregnant-onboarding",
    TrackName.POSTPARTUM.value: "postbaby-welcome",
}


def load_data():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    create_assessment_tracks = []
    for track_name in data.keys():
        create_assessment_tracks.append(
            AssessmentTrack(
                track_name=track_name, assessment_onboarding_slug=data.get(track_name)
            )
        )
    print(create_assessment_tracks)
    db.session.add_all(create_assessment_tracks)
    db.session.commit()


if __name__ == "__main__":
    with create_app().app_context():
        load_data()
