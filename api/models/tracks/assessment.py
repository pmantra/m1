from sqlalchemy import Column, Integer, String

from models.base import TimeLoggedSnowflakeModelBase


class AssessmentTrack(TimeLoggedSnowflakeModelBase):
    """
    Replaces AssessmentLifecycle and AssessmentLifecycleTrack to connect to the Health Data Collection service.
    """

    __tablename__ = "assessment_track_relationships"

    id = Column(Integer, primary_key=True)
    assessment_onboarding_slug = Column(String, unique=True)
    track_name = Column(String, unique=True)
