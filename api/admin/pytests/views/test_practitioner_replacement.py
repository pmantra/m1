from unittest import mock

from admin.blueprints.actions import PracReplacementEndpointMessage
from models.profiles import CareTeamTypes
from models.tracks import TrackName
from models.verticals_and_specialties import CX_VERTICAL_NAME
from provider_matching.models.vgc import VGC
from pytests.factories import (
    AssignableAdvocateFactory,
    EnterpriseUserFactory,
    MemberPractitionerAssociationFactory,
    PractitionerTrackVGCFactory,
    PractitionerUserFactory,
    VerticalFactory,
)


class TestPractitionerReplacement:
    def test_none_prac_to_replace(self, admin_client):
        request_data = {
            "practitioner_id": None,
            "remove_only_quiz_type": "True",
        }
        res = admin_client.post(
            "/admin/actions/replace_practitioner/", data=request_data
        )
        assert res.status_code == 400
        assert res.json["error"] == PracReplacementEndpointMessage.MISSING_PRAC_ID

    def test_invalid_prac_id(self, admin_client):
        request_data = {
            "practitioner_id": -1,
            "remove_only_quiz_type": "True",
        }

        res = admin_client.post(
            "/admin/actions/replace_practitioner/", data=request_data
        )
        assert res.status_code == 400
        assert res.json["error"] == PracReplacementEndpointMessage.INVALID_PRAC_ID

    def test_prac_to_replace_in_active_new_pracs(self, admin_client, enterprise_user):
        practitioner = PractitionerUserFactory.create(
            practitioner_profile__verticals=[VerticalFactory.create(name="OB-GYN")]
        )
        MemberPractitionerAssociationFactory.create(
            user_id=enterprise_user.id,
            practitioner_id=practitioner.id,
            type=CareTeamTypes.QUIZ,
        )
        PractitionerTrackVGCFactory.create(
            practitioner_id=practitioner.id,
            track=TrackName.PREGNANCY,
            vgc=VGC.CAREER_COACH,
        )
        request_data = {
            "practitioner_id": practitioner.id,
            "remove_only_quiz_type": "True",
        }

        res = admin_client.post(
            "/admin/actions/replace_practitioner/", data=request_data
        )
        assert res.status_code == 400
        assert (
            res.json["error"]
            == PracReplacementEndpointMessage.PRAC_TO_REPLACE_IN_NEW_PRACS
        )

    def test_prac_to_replace_is_cx_error(self, admin_client, enterprise_user):
        care_advocate = PractitionerUserFactory.create(
            practitioner_profile__verticals=[
                VerticalFactory.create(name=CX_VERTICAL_NAME)
            ]
        )
        MemberPractitionerAssociationFactory.create(
            user_id=enterprise_user.id,
            practitioner_id=care_advocate.id,
            type=CareTeamTypes.CARE_COORDINATOR,
        )
        AssignableAdvocateFactory.create_with_practitioner(practitioner=care_advocate)
        request_data = {
            "practitioner_id": care_advocate.id,
            "remove_only_quiz_type": "False",
        }

        res = admin_client.post(
            "/admin/actions/replace_practitioner/", data=request_data
        )
        assert res.status_code == 400
        assert res.json["error"] == PracReplacementEndpointMessage.PRAC_IS_CARE_ADVOCATE

    def test_no_mpas(self, admin_client):
        # Be sure practitioner is not a CX
        practitioner = PractitionerUserFactory.create(
            practitioner_profile__verticals=[VerticalFactory.create(name="OB-GYN")]
        )
        request_data = {
            "practitioner_id": practitioner.id,
            "remove_only_quiz_type": "True",
        }

        with mock.patch("admin.blueprints.actions.Lock") as LockMock:
            lock_instance = LockMock.return_value
            lock_instance.locked.side_effect = [False, True]
            res = admin_client.post(
                "/admin/actions/replace_practitioner/", data=request_data
            )

        lock_instance.acquire.assert_called_once_with(
            blocking=False, token=str(practitioner.id)
        )
        lock_instance.do_release.assert_called_once_with(
            expected_token=str(practitioner.id)
        )
        assert res.status_code == 400
        assert (
            res.json["error"]
            == PracReplacementEndpointMessage.PRAC_NOT_PRESENT_IN_ANY_CARE_TEAM_AS_QUIZ
        )

    def test_successful_replacement(self, admin_client):
        user = EnterpriseUserFactory.create(tracks__name=TrackName.PREGNANCY)
        practitioner = PractitionerUserFactory.create(
            practitioner_profile__verticals=[VerticalFactory.create(name="OB-GYN")]
        )
        MemberPractitionerAssociationFactory.create(
            user_id=user.id,
            practitioner_id=practitioner.id,
            type=CareTeamTypes.QUIZ,
        )
        new_practitioner = PractitionerUserFactory.create(
            practitioner_profile__verticals=[VerticalFactory.create(name="OB-GYN")]
        )
        PractitionerTrackVGCFactory.create(
            practitioner_id=new_practitioner.id,
            track=TrackName.PREGNANCY,
            vgc=VGC.OB_GYN,
        )
        request_data = {
            "practitioner_id": practitioner.id,
            "remove_only_quiz_type": "True",
        }

        with mock.patch("admin.blueprints.actions.Lock") as LockMock, mock.patch(
            "provider_matching.services.care_team_assignment.replace_practitioner_in_care_teams.delay",
            return_value=mock.MagicMock(id=100),
        ):
            lock_instance = LockMock.return_value
            lock_instance.locked.side_effect = [False, True]
            res = admin_client.post(
                "/admin/actions/replace_practitioner/", data=request_data
            )

        lock_instance.acquire.assert_called_once_with(
            blocking=False, token=str(practitioner.id)
        )
        assert not lock_instance.do_release.called
        assert res.status_code == 200
        assert res.json["message"] == "Success"
        assert res.json["job_ids"] == [100]

    def test_prac_to_replace_is_appointment_remove_only_quiz_type_true_replacement_not_successful(
        self, admin_client
    ):
        user = EnterpriseUserFactory.create(tracks__name=TrackName.PREGNANCY)
        practitioner = PractitionerUserFactory.create(
            practitioner_profile__verticals=[VerticalFactory.create(name="OB-GYN")]
        )
        MemberPractitionerAssociationFactory.create(
            user_id=user.id,
            practitioner_id=practitioner.id,
            # Test difference here
            type=CareTeamTypes.APPOINTMENT,
        )
        new_practitioner = PractitionerUserFactory.create(
            practitioner_profile__verticals=[VerticalFactory.create(name="OB-GYN")]
        )
        PractitionerTrackVGCFactory.create(
            practitioner_id=new_practitioner.id,
            track=TrackName.PREGNANCY,
            vgc=VGC.OB_GYN,
        )
        request_data = {
            "practitioner_id": practitioner.id,
            "remove_only_quiz_type": "True",
        }

        with mock.patch("admin.blueprints.actions.Lock") as LockMock:
            lock_instance = LockMock.return_value
            lock_instance.locked.side_effect = [False, True]
            res = admin_client.post(
                "/admin/actions/replace_practitioner/", data=request_data
            )

        lock_instance.acquire.assert_called_once_with(
            blocking=False, token=str(practitioner.id)
        )
        lock_instance.do_release.assert_called_once_with(
            expected_token=str(practitioner.id)
        )
        assert res.status_code == 400
        assert (
            res.json["error"]
            == PracReplacementEndpointMessage.PRAC_NOT_PRESENT_IN_ANY_CARE_TEAM_AS_QUIZ
        )
