import datetime
from unittest.mock import Mock, patch

import pytest
import requests

from authn.domain import model
from preferences import models, repository
from preferences.pytests.factories import PreferenceFactory
from utils.migrations.backfill_email_consent import (
    BrazeUnsubscribeResponseEmail,
    InsertDataRow,
    backfill_preferences,
    get_opted_in_insert_statements,
    get_unsubscribe_insert_statements,
    get_unsubscribes_from_braze,
)


@pytest.fixture
def created_member(factories) -> model.User:
    user: model.User = factories.EnterpriseUserFactory.create()
    return user


@pytest.fixture
def preference_repository(session) -> repository.PreferenceRepository:
    return repository.PreferenceRepository(session=session, is_in_uow=True)


@pytest.fixture
def created_preference(
    preference_repository: repository.PreferenceRepository,
) -> models.Preference:
    created: models.Preference = preference_repository.create(
        instance=models.Preference(
            name="PREFERENCE",
            default_value="DEFAULT",
            type="str",
        )
    )
    return created


@pytest.fixture
def member_preferences_repository(session) -> repository.MemberPreferencesRepository:
    return repository.MemberPreferencesRepository(session=session, is_in_uow=True)


@pytest.fixture
def created_member_preference(
    member_preferences_repository: repository.MemberPreferencesRepository,
    created_member: model.User,
    created_preference: models.Preference,
) -> models.MemberPreference:
    created: models.MemberPreference = member_preferences_repository.create(
        instance=models.MemberPreference(
            value="VALUE",
            member_id=created_member.id,
            preference_id=created_preference.id,
        )
    )
    return created


@patch("utils.migrations.backfill_email_consent.API_KEY", "FOO")
def test_braze_request(faker):
    data = [{"email": faker.email(), "unsubscribed_at": faker.past_date()}]

    with patch("utils.migrations.backfill_email_consent.requests.get") as mock_request:
        mock_request.return_value = Mock(status_code=200, json=lambda: {"emails": data})

        unsubscribe_data = get_unsubscribes_from_braze()

        assert len(unsubscribe_data) == 1
        assert unsubscribe_data[0].email == data[0]["email"]


@patch("utils.migrations.backfill_email_consent.API_KEY", "FOO")
def test_braze_request_http_error():
    mock_error = requests.HTTPError()
    mock_error.response = requests.Response()
    mock_error.response.status_code = 418
    mock_error.response.json = lambda: {}

    with patch("utils.migrations.backfill_email_consent.requests.get") as mock_request:
        mock_request().raise_for_status.side_effect = mock_error

        with pytest.raises(requests.HTTPError):
            get_unsubscribes_from_braze()


@patch("utils.migrations.backfill_email_consent.API_KEY", "FOO")
def test_braze_request_exception():
    mock_error = Exception()
    mock_error.response = requests.Response()
    mock_error.response.status_code = 418
    mock_error.response.json = lambda: {}

    with patch("utils.migrations.backfill_email_consent.requests.get") as mock_request:
        mock_request().raise_for_status.side_effect = mock_error

        with pytest.raises(  # noqa  B017  TODO:  `assertRaises(Exception)` and `pytest.raises(Exception)` should be considered evil. They can lead to your test passing even if the code being tested is never executed due to a typo. Assert for a more specific exception (builtin or custom), or use `assertRaisesRegex` (if using `assertRaises`), or add the `match` keyword argument (if using `pytest.raises`), or use the context manager form with a target.
            Exception
        ):
            get_unsubscribes_from_braze()


def test_email_does_not_match_user(faker):
    with patch(
        "utils.migrations.backfill_email_consent.get_unsubscribes_from_braze"
    ) as mock_braze:
        mock_braze.return_value = [
            BrazeUnsubscribeResponseEmail(
                email=faker.email(),
                unsubscribed_at=faker.past_date(),
            )
        ]

        preference = PreferenceFactory.create()
        rows = get_unsubscribe_insert_statements(preference)

        assert len(rows) == 0


def test_member_already_has_preference(
    faker,
    created_member: model.User,
    created_preference: models.Preference,
    created_member_preference: models.MemberPreference,
):
    with patch(
        "utils.migrations.backfill_email_consent.get_unsubscribes_from_braze"
    ) as mock_braze, patch(
        "utils.migrations.backfill_email_consent.service.MemberPreferencesService.get_by_preference_name"
    ) as mock_member_preference_get, patch(
        "utils.migrations.backfill_email_consent.UserRepository.get_by_email"
    ) as mock_user_repo:
        mock_braze.return_value = [
            BrazeUnsubscribeResponseEmail(
                email=created_member.email,
                unsubscribed_at=faker.past_date(),
            )
        ]

        mock_user_repo.return_value = created_member
        mock_member_preference_get.return_value = created_member_preference
        rows = get_unsubscribe_insert_statements(created_preference)

        assert len(rows) == 0
        assert mock_member_preference_get.called


def test_unsubscribe(
    faker,
    created_member: model.User,
    created_preference: models.Preference,
):
    with patch(
        "utils.migrations.backfill_email_consent.get_unsubscribes_from_braze"
    ) as mock_braze, patch(
        "utils.migrations.backfill_email_consent.service.MemberPreferencesService.get_by_preference_name"
    ) as mock_member_preference_get, patch(
        "utils.migrations.backfill_email_consent.UserRepository.get_by_email"
    ) as mock_user_repo:
        mock_braze.return_value = [
            BrazeUnsubscribeResponseEmail(
                email=created_member.email,
                unsubscribed_at=faker.past_date(),
            )
        ]

        mock_user_repo.return_value = created_member
        mock_member_preference_get.return_value = None
        rows = get_unsubscribe_insert_statements(created_preference)

        assert len(rows) == 1
        assert rows[0].member_id == str(created_member.id)
        assert rows[0].preference_id == str(created_preference.id)
        assert rows[0].value == "false"


def test_opt_in(enterprise_user, created_preference: models.Preference):
    unsubscribed_user_ids = [enterprise_user.id + 1]

    batches = get_opted_in_insert_statements(created_preference, unsubscribed_user_ids)

    all_batches = list(batches)
    assert len(all_batches) == 1

    batch = all_batches[0]
    assert len(batch) == 1

    assert batch[0].member_id == str(enterprise_user.id)
    assert batch[0].preference_id == str(created_preference.id)
    assert batch[0].value == "true"


def test_backfill_preferences(
    enterprise_user,
    created_member: model.User,
    created_preference: models.Preference,
    member_preferences_repository: repository.MemberPreferencesRepository,
):
    current_time = datetime.datetime.utcnow()

    with patch(
        "utils.migrations.backfill_email_consent.service.PreferenceService.get_by_name"
    ) as mock_preference_get, patch(
        "utils.migrations.backfill_email_consent.get_unsubscribe_insert_statements"
    ) as mock_unsubscribe_inserts, patch(
        "utils.migrations.backfill_email_consent.get_opted_in_insert_statements"
    ) as mock_opted_in_inserts:
        mock_preference_get.return_value = created_preference

        mock_unsubscribe_inserts.return_value = [
            InsertDataRow(
                member_id=str(created_member.id),
                preference_id=str(created_preference.id),
                value="false",
                created_at=current_time,
                modified_at=current_time,
            )
        ]

        mock_opted_in_inserts.return_value = (
            [
                InsertDataRow(
                    member_id=str(enterprise_user.id),
                    preference_id=str(created_preference.id),
                    value="false",
                    created_at=current_time,
                    modified_at=current_time,
                )
            ],
        )

        # there shouldn't be any member preferences yet
        assert len(member_preferences_repository.all()) == 0

        backfill_preferences()

        assert len(member_preferences_repository.all()) == 2
