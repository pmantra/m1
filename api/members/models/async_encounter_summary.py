from __future__ import annotations

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from models.base import TimeLoggedModelBase


class AsyncEncounterSummary(TimeLoggedModelBase):
    __tablename__ = "async_encounter_summary"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    provider_id = Column(Integer, ForeignKey("user.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    questionnaire_id = Column(
        BigInteger, ForeignKey("questionnaire.id"), nullable=False
    )
    encounter_date = Column(DateTime(), nullable=False)

    provider = relationship("User", foreign_keys=[provider_id])
    user = relationship("User", foreign_keys=[user_id])
    questionnaire = relationship("Questionnaire", lazy="joined")


class AsyncEncounterSummaryAnswer(TimeLoggedModelBase):
    __tablename__ = "async_encounter_summary_answer"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    async_encounter_summary_id = Column(
        BigInteger, ForeignKey("async_encounter_summary.id"), nullable=False
    )
    question_id = Column(BigInteger, ForeignKey("question.id"), nullable=False)
    answer_id = Column(BigInteger, ForeignKey("answer.id"))
    text = Column(String)
    date = Column(DateTime())

    async_encounter_summary = relationship(
        "AsyncEncounterSummary",
        lazy="joined",
        backref="async_encounter_summary_answers",
    )
    question = relationship("Question", lazy="joined")
    answer = relationship("Answer", lazy="joined")
