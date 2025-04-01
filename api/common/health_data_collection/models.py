from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Union

from utils.log import logger

log = logger(__name__)


@dataclass
class UserAssessmentStatus:
    assessment_id: str
    user_id: str
    num_assessment_taken: int
    assessment_slug: str
    completed_assessment: bool = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "bool")
    date_completed: datetime = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "datetime")


@dataclass
class HDCUserAnswer:
    __slots__ = (
        "id",
        "label",
        "question_id",
        "question_version",
        "user_id",
        "mono_needs_assessment_id",
        "contentful_answer_id",
        "user_assessment_status_id",
        "export_flags",
        "export_flag_label_override",
        "question_slug",
        "value",
        "datatype",
    )

    id: str
    label: str
    question_id: str
    question_version: int
    user_id: str
    mono_needs_assessment_id: int
    contentful_answer_id: str
    user_assessment_status_id: str
    export_flags: list
    export_flag_label_override: str
    question_slug: str
    value: Union[float, bool, str, int, datetime]
    datatype: str


@dataclass
class HDCAnswerOption:
    __slots__ = (
        "contentful_entry_id",
        "version",
        "label",
        "value",
        "id",
        "score_value",
        "contentful_answer_id",
        "export_flag_label_override",
        "export_flags",
        "entry_status",
        "mpractice_highlight",
        "mpractice_label",
        "is_mutually_exclusive",
    )

    contentful_entry_id: str
    version: int
    label: str
    value: str
    id: str
    score_value: int
    contentful_answer_id: str
    export_flag_label_override: str
    export_flags: list
    entry_status: str
    mpractice_highlight: bool
    mpractice_label: str
    is_mutually_exclusive: bool


@dataclass
class HDCDisplayCondition:
    show_if_any_answer: List[HDCAnswerOption]
    contentful_entry_id: str
    note: str
    version: int
    entry_status: str = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "str")


@dataclass
class HDCQuestion:
    version: int
    slug: str
    body: str
    required: bool
    widget_type: str
    id: str
    entry_status: str
    mpractice_display: bool
    mpractice_label: str
    microcopy: Optional[Union[str, None]]
    contentful_entry_id: Optional[str]
    export_flags: Optional[List[str]]
    options: Optional[List[HDCAnswerOption]] = dataclasses.field(default_factory=list)
    display_condition: Optional[HDCDisplayCondition] = dataclasses.field(  # type: ignore[assignment] # Incompatible types in assignment (expression has type "List[Never]", variable has type "Optional[HDCDisplayCondition]")
        default_factory=list
    )
    user_answers: Optional[List[HDCUserAnswer]] = dataclasses.field(
        default_factory=list
    )

    @classmethod
    def create_from_api_response(cls, json_response) -> HDCQuestion:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments

        question = HDCQuestion(
            version=json_response.get("version"),
            slug=json_response.get("slug"),
            body=json_response.get("body"),
            required=json_response.get("required"),
            widget_type=json_response.get("widget_type"),
            id=json_response.get("id"),
            entry_status=json_response.get("entry_status"),
            mpractice_display=json_response.get("mpractice_display"),
            mpractice_label=json_response.get("mpractice_label"),
            microcopy=json_response.get("microcopy"),
            contentful_entry_id=json_response.get("contentful_entry_id"),
            export_flags=json_response.get("export_flags"),
        )

        # Convert user answers and options to data models
        user_answer_res = json_response["user_answers"]
        if user_answer_res:
            question.user_answers = [
                HDCUserAnswer(
                    id=res.get("id"),
                    label=res.get("label"),
                    question_id=res.get("question_id"),
                    question_version=res.get("question_version"),
                    user_id=res.get("user_id"),
                    mono_needs_assessment_id=res.get("mono_needs_assessment_id"),
                    contentful_answer_id=res.get("contentful_answer_id"),
                    user_assessment_status_id=res.get("user_assessment_status_id"),
                    export_flags=res.get("export_flags"),
                    export_flag_label_override=res.get("export_flag_label_override"),
                    question_slug=res.get("question_slug"),
                    value=res.get("value"),
                    datatype=res.get("datatype"),
                )
                for res in user_answer_res
            ]

        option_res = json_response["options"]
        if option_res:
            question.options = [
                HDCAnswerOption(
                    contentful_entry_id=res.get("contentful_entry_id"),
                    version=res.get("version"),
                    label=res.get("label"),
                    value=res.get("value"),
                    id=res.get("id"),
                    score_value=res.get("score_value"),
                    contentful_answer_id=res.get("contentful_answer_id"),
                    export_flag_label_override=res.get("export_flag_label_override"),
                    export_flags=res.get("export_flags"),
                    entry_status=res.get("entry_status"),
                    mpractice_highlight=res.get("mpractice_highlight"),
                    mpractice_label=res.get("mpractice_label"),
                    is_mutually_exclusive=res.get("is_mutually_exclusive"),
                )
                for res in option_res
            ]

        dc_res = json_response["display_condition"]
        if dc_res:
            question.display_condition = HDCDisplayCondition(
                show_if_any_answer=dc_res.get("show_if_any_answer"),
                contentful_entry_id=dc_res.get("contentful_entry_id"),
                version=dc_res.get("version"),
                note=dc_res.get("note"),
                entry_status=dc_res.get("entry_status"),
            )

        # log extra fields if present
        if extra_fields := get_extra_fields(
            dataclasses.asdict(question), json_response, []
        ):
            log.warn("Extra fields found in HDC response.", extra_fields=extra_fields)

        return question


@dataclass
class AssessmentMetadata:
    __slots__ = ("id", "slug", "title", "version", "completed", "url")
    id: int
    slug: str
    title: str
    version: int
    completed: bool
    url: str

    @classmethod
    def create_from_api_response(cls, json_res) -> AssessmentMetadata:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        slug = json_res.get("slug")
        return AssessmentMetadata(
            id=json_res.get("id"),
            slug=slug,
            title=json_res.get("title"),
            version=json_res.get("version"),
            completed=(
                json_res.get("user_assessment").get("completed_assessment")
                if json_res.get("user_assessment")
                else False
            ),
            url=f"/app/assessments/{slug}",
        )


def get_extra_fields(hdc_question, json_response, extra_fields):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    for k in json_response:
        if k in hdc_question:
            if isinstance(json_response[k], dict):
                get_extra_fields(hdc_question[k], json_response[k], extra_fields)
            if isinstance(json_response[k], list):
                for hdc_q, json_r in zip(hdc_question[k], json_response[k]):
                    get_extra_fields(hdc_q, json_r, extra_fields) if isinstance(
                        hdc_q, dict
                    ) else None
        else:
            extra_fields.append(k)

    return extra_fields
