from unittest import mock

import pytest

from models.enterprise import OnboardingState
from utils.braze import BrazeUserOnboardingState
from utils.migrations.braze_users.backfill_onboarding_status import (
    ONBOARDING_STATES_FOR_MARKETING_CAMPAIGN,
    backfill,
    query_onboarding_state_counts,
    report_onboarding_states_to_braze,
)


@pytest.fixture
def fake_onboarding_states(factories):
    return (
        factories.UserOnboardingStateFactory.create(
            user=factories.DefaultUserFactory.create(),
            state=OnboardingState.USER_CREATED,
        ),
        factories.UserOnboardingStateFactory.create(
            user=factories.DefaultUserFactory.create(),
            state=OnboardingState.USER_CREATED,
        ),
        factories.UserOnboardingStateFactory.create(
            user=factories.DefaultUserFactory.create(),
            state=OnboardingState.FILELESS_INVITED_DEPENDENT,
        ),
    )


@pytest.fixture
def patch_send_onboarding_states():
    with mock.patch("utils.braze.send_onboarding_states") as send_onboarding_states:
        yield send_onboarding_states


@pytest.fixture
def patch_query_onboarding_state_counts():
    with mock.patch(
        "utils.migrations.braze_users.backfill_onboarding_status.query_onboarding_state_counts"
    ) as q:
        q.return_value = (0, 0)
        yield q


@pytest.fixture
def patch_report_onboarding_states_to_braze():
    with mock.patch(
        "utils.migrations.braze_users.backfill_onboarding_status.report_onboarding_states_to_braze"
    ) as r:
        yield r


def test_query_onboarding_state_counts(fake_onboarding_states):
    (
        all_onboarding_state_count,
        useful_onboarding_state_count,
    ) = query_onboarding_state_counts()

    assert all_onboarding_state_count == len(fake_onboarding_states)
    assert useful_onboarding_state_count == sum(
        user_onboarding_state.state in ONBOARDING_STATES_FOR_MARKETING_CAMPAIGN
        for user_onboarding_state in fake_onboarding_states
    )


def test_report_onboarding_states_to_braze_when_all(
    fake_onboarding_states, patch_send_onboarding_states
):
    with mock.patch("storage.connection.db.session.commit") as mock_commit:
        report_onboarding_states_to_braze(False, True, 2, None)

        assert patch_send_onboarding_states.call_count == 2
        patch_send_onboarding_states.assert_has_calls(
            [
                mock.call(
                    [
                        BrazeUserOnboardingState(
                            fake_onboarding_states[0].user.esp_id,
                            fake_onboarding_states[0].state,
                        ),
                        BrazeUserOnboardingState(
                            fake_onboarding_states[1].user.esp_id,
                            fake_onboarding_states[1].state,
                        ),
                    ]
                ),
                mock.call(
                    [
                        BrazeUserOnboardingState(
                            fake_onboarding_states[2].user.esp_id,
                            fake_onboarding_states[2].state,
                        )
                    ]
                ),
            ]
        )

        mock_commit.assert_called_once()


def test_report_onboarding_states_to_braze_with_page_limit(
    fake_onboarding_states, patch_send_onboarding_states
):
    report_onboarding_states_to_braze(False, True, 1, 1)
    assert patch_send_onboarding_states.call_count == 1


def test_report_onboarding_states_to_braze_with_dry_run(
    fake_onboarding_states, patch_send_onboarding_states
):
    report_onboarding_states_to_braze(True, True, 10, None)
    patch_send_onboarding_states.assert_not_called()


def test_report_onboarding_states_to_braze_when_filtered(
    fake_onboarding_states, patch_send_onboarding_states
):
    with mock.patch("storage.connection.db.session.commit") as mock_commit:
        report_onboarding_states_to_braze(False, False, 2, None)

        useful_states = list(
            filter(
                lambda user_onboarding_state: user_onboarding_state.state
                in ONBOARDING_STATES_FOR_MARKETING_CAMPAIGN,
                fake_onboarding_states,
            )
        )

        assert len(useful_states) == 2
        assert patch_send_onboarding_states.call_count == 1
        patch_send_onboarding_states.assert_called_with(
            [
                BrazeUserOnboardingState(
                    useful_states[0].user.esp_id,
                    useful_states[0].state,
                ),
                BrazeUserOnboardingState(
                    useful_states[1].user.esp_id,
                    useful_states[1].state,
                ),
            ]
        )

        mock_commit.assert_called_once()


def test_backfill_gets_statistics_on_dry_run(
    patch_query_onboarding_state_counts, patch_report_onboarding_states_to_braze
):
    backfill(True)

    patch_query_onboarding_state_counts.assert_called_once()
    patch_report_onboarding_states_to_braze.assert_called_once()


def test_backfill_reports_to_braze(
    patch_query_onboarding_state_counts, patch_report_onboarding_states_to_braze
):
    backfill(False)

    patch_query_onboarding_state_counts.assert_not_called()
    patch_report_onboarding_states_to_braze.assert_called_once()
