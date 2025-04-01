from unittest import mock

import pytest
from babel import Locale

from learn.models import article


@pytest.mark.parametrize(
    "input_list,expected_output",
    [
        (None, None),
        ([], None),
        (["Donald Duck"], "Donald Duck"),
        (["Donald Duck", "Mickey Mouse"], "Donald Duck and Maven Mickey Mouse"),
        (
            ["Mental Health Provider, Donald Duck", "OB-GYN, Mickey Mouse"],
            "Mental Health Provider, Donald Duck, and Maven OB-GYN, Mickey Mouse",
        ),
        (
            [
                "Mental Health Provider, Donald Duck",
                "OB-GYN, Mickey Mouse",
                "Lactation Consultant, Goofy",
            ],
            "Mental Health Provider, Donald Duck, Maven OB-GYN, Mickey Mouse, and Maven Lactation Consultant, Goofy",
        ),
    ],
)
def test_concatenate_with_comma_and_and(input_list, expected_output):
    assert article.join_with_comma_and_and(input_list) == expected_output


def test_default_medically_reviewed():
    medically_reviewed = article.MedicallyReviewed.from_contentful_entry(None)
    assert medically_reviewed.reviewers is None


@pytest.mark.parametrize(
    argnames=("locale", "show_medical_reviewers"),
    argvalues=((Locale("en"), True), (Locale("en", "US"), True), (Locale("es"), False)),
)
@mock.patch("l10n.utils.get_locale")
def test_medically_reviewed(get_locale, locale, show_medical_reviewers):
    get_locale.return_value = locale

    reviewer1 = mock.Mock(name_vertical="Mental Health Provider, Donald Duck")
    reviewer2 = mock.Mock(name_vertical="OB-GYN, Mickey Mouse")
    medically_reviewed = article.MedicallyReviewed.from_contentful_entry(
        [reviewer1, reviewer2]
    )

    if show_medical_reviewers:
        assert (
            medically_reviewed.reviewers
            == "Mental Health Provider, Donald Duck, and Maven OB-GYN, Mickey Mouse"
        )
    else:
        assert medically_reviewed.reviewers is None
