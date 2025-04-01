import datetime
from datetime import timezone
from unittest import mock

import pytest

from models.tracks import MemberTrack, TrackLifecycleError
from models.tracks.lifecycle import add_track_closure_reason
from pytests.factories import MemberTrackFactory, TrackChangeReasonFactory


class TestTrackTransition:
    def test_force_transition_and_closure__track_records_track_closure_reason(
        self, admin_client
    ):
        track1, track2 = MemberTrackFactory.create_batch(size=2)
        track_change_reason = TrackChangeReasonFactory.create()

        res = admin_client.post(
            "/admin/actions/tracks/transition",
            data={
                "force_transition": True,
                "member_track_id": track1.id,
                "target": track2.name,
                "closure_reason_id": track_change_reason.id,
            },
        )
        assert res.status_code == 302
        closed_track = MemberTrack.query.get(track1.id)
        assert closed_track.closure_reason_id == track_change_reason.id

    def test_close_track__invalid_closure_reason_id__throws_exception(
        self, admin_client
    ):
        track = MemberTrackFactory.create()
        with pytest.raises(TrackLifecycleError):
            add_track_closure_reason(track, -1)


class TestMemberTrackView:
    @mock.patch("tracks.service.TrackSelectionService.is_enterprise")
    def test_action_reactivate_refills_credits(
        self, mock_is_enterprise, admin_client, monkeypatch
    ):
        from appointments.models.payments import Credit

        mock_user = mock.Mock()
        mock_user.id = 999

        monkeypatch.setattr("admin.views.models.tracks.current_user", mock_user)

        mock_is_enterprise.return_value = True

        current_time = datetime.datetime.now(timezone.utc)
        member_track = MemberTrackFactory.create(
            ended_at=current_time - datetime.timedelta(weeks=1)
        )
        user_id = member_track.user_id

        Credit.expire_all_enterprise_credits_for_user(user_id, expires_at=current_time)

        initial_amount = Credit.available_amount_for_user_id(user_id=user_id)
        assert initial_amount == 0

        monkeypatch.setattr("audit_log.utils.emit_audit_log_update", mock.Mock())

        res = admin_client.post(
            "/admin/membertrack/action/",
            data={
                "action": "reactivate",
                "rowid": member_track.id,
            },
        )

        assert res.status_code == 302

        final_amount = Credit.available_amount_for_user_id(user_id=user_id)
        assert final_amount == 2000

        updated_track = MemberTrack.query.get(member_track.id)
        assert updated_track.ended_at is None
