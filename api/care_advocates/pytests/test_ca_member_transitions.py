import datetime
import json
import sys
from string import Template
from unittest import TestCase, mock
from unittest.mock import MagicMock, call, patch

import arrow
import pytest
from babel import Locale
from werkzeug.datastructures import FileStorage

from care_advocates.models.transitions import (
    CareAdvocateMemberTransitionLog,
    CareAdvocateMemberTransitionResponse,
)
from care_advocates.repository.transition_log import (
    CareAdvocateMemberTransitionLogRepository,
)
from care_advocates.repository.transition_template import (
    CareAdvocateMemberTransitionTemplateRepository,
)
from care_advocates.services.transition_log import (
    AlreadyCompletedTransitionError,
    CareAdvocateMemberTransitionLogServiceMessage,
    CareAdvocateMemberTransitionValidator,
    IncorrectTransitionLogIDError,
    SubmittingTransitionLogErrors,
    TransitionLogValidatorError,
)
from care_advocates.services.transition_template import (
    CareAdvocateMemberTransitionTemplateService,
)
from care_advocates.tasks.transitions import (
    _send_member_message,
    perform_care_advocate_member_transitions,
    reassign_care_advocate,
)
from models.profiles import CareTeamTypes, MemberPractitionerAssociation
from pytests.factories import (
    CareAdvocateMemberTransitionLogFactory,
    CareAdvocateMemberTransitionTemplateFactory,
    DefaultUserFactory,
    MemberPractitionerAssociationFactory,
    MemberProfileFactory,
    PractitionerProfileFactory,
    VerticalFactory,
)
from storage.connection import db


@pytest.fixture
def member_old_new_cx(factories):
    # Setup member
    member = factories.EnterpriseUserFactory()

    # Old cx from member (current)
    old_cx = member.care_coordinators[0]

    # Setup new cx
    new_cx = factories.PractitionerUserFactory()
    factories.AssignableAdvocateFactory.create_with_practitioner(practitioner=new_cx)

    return {"member": member, "old_cx": old_cx, "new_cx": new_cx}


@pytest.fixture
def message_templates_one(farewell_transition_template):
    return [farewell_transition_template]


@pytest.fixture
def message_templates_two(
    farewell_transition_template,
    followup_intro_transition_template,
):
    return [farewell_transition_template, followup_intro_transition_template]


@pytest.fixture
def message_types_one(message_templates_one):
    return [message_templates_one[0].message_type]


class TestPerformCAMemberTransitions(TestCase):
    def setUp(self):
        self.scheduler_1 = DefaultUserFactory()
        self.scheduler_profile_1 = MemberProfileFactory(user_id=self.scheduler_1.id)
        self.scheduler_2 = DefaultUserFactory()
        self.scheduler_profile_2 = MemberProfileFactory(user_id=self.scheduler_2.id)

        self.user_1 = DefaultUserFactory()
        self.user_profile_1 = MemberProfileFactory(user_id=self.user_1.id)
        self.user_2 = DefaultUserFactory()
        self.user_profile_2 = MemberProfileFactory(user_id=self.user_2.id)

        self.ca_vertical = VerticalFactory.create_cx_vertical()

        self.practitioner_1 = DefaultUserFactory()
        self.practitioner_profile_1 = PractitionerProfileFactory(
            user_id=self.practitioner_1.id,
            verticals=[self.ca_vertical],
        )
        self.practitioner_2 = DefaultUserFactory()
        self.practitioner_profile_2 = PractitionerProfileFactory(
            user_id=self.practitioner_2.id,
            verticals=[self.ca_vertical],
        )

        self.farewell_template = CareAdvocateMemberTransitionTemplateFactory(
            message_type="FAREWELL",
        )
        self.followup_intro_template = CareAdvocateMemberTransitionTemplateFactory(
            message_type="FOLLOWUP_INTRO",
        )

        self.mpa_1 = MemberPractitionerAssociationFactory(
            user_id=self.user_1.id,
            practitioner_id=self.practitioner_1.id,
            type=CareTeamTypes.CARE_COORDINATOR,
        )
        self.mpa_1 = MemberPractitionerAssociationFactory(
            user_id=self.user_2.id,
            practitioner_id=self.practitioner_1.id,
            type=CareTeamTypes.CARE_COORDINATOR,
        )

    def _set_up_transition_log_entry(
        self, scheduler, member_to_message_types_map, old_cx_id=None, new_cx_id=None
    ):
        if not old_cx_id:
            old_cx_id = self.practitioner_1.id

        if not new_cx_id:
            new_cx_id = self.practitioner_2.id

        transition_content_list = []
        for member_id in member_to_message_types_map:
            transition_content_list.append(
                {
                    "member_id": member_id,
                    "old_cx_id": old_cx_id,
                    "new_cx_id": new_cx_id,
                    "messaging": ";".join(member_to_message_types_map[member_id]),
                }
            )

        transition_content = json.dumps(transition_content_list)
        camt = CareAdvocateMemberTransitionLogFactory(
            user_id=scheduler.id,
            date_completed=None,
            date_scheduled=arrow.utcnow().shift(days=-1).datetime,
            uploaded_content=transition_content,
        )

        return camt

    def _assert_successful_transition(
        self, user_id, practitioner_id=None, assert_opposite=False
    ):
        if not practitioner_id:
            practitioner_id = self.practitioner_2.id

        mpas_for_user = MemberPractitionerAssociation.query.filter_by(
            user_id=user_id
        ).all()

        if not assert_opposite:
            # Assert that they only have 1 MPA (basically ensuring that we didn't just create a new MPA, but
            # instead edited the existing MPA).
            self.assertEqual(
                1,
                len(mpas_for_user),
            )

            # Assert that the only MPA that exists for this user is pointing to the right practitioner
            self.assertEqual(
                practitioner_id,
                mpas_for_user[0].practitioner_id,
            )
        else:
            # Assert that they only have 1 MPA
            self.assertEqual(
                1,
                len(mpas_for_user),
            )

            # Assert that the only MPA that exists for this user is pointing to the original
            # practitioner, which means that no action was taken
            self.assertEqual(
                self.practitioner_1.id,
                mpas_for_user[0].practitioner_id,
            )

    def _assert_failed_transition(self, user_id, practitioner_id=None):
        self._assert_successful_transition(
            user_id, practitioner_id, assert_opposite=True
        )

    def test_perform_care_advocate_member_transitions__no_content__no_transitions_performed(
        self,
    ):
        (
            results_per_member,
            results_per_user,
        ) = perform_care_advocate_member_transitions()

        self.assertEqual(0, len(results_per_member))
        self.assertEqual(0, len(results_per_user))

    def test_perform_care_advocate_member_transitions__single_transition__only_single_user_transitioned(
        self,
    ):
        self._set_up_transition_log_entry(
            self.scheduler_1,
            {self.user_1.id: [self.farewell_template.message_type]},
        )

        (
            results_per_member,
            results_per_user,
        ) = perform_care_advocate_member_transitions()

        self.assertEqual(
            [CareAdvocateMemberTransitionResponse.SUCCESS.name],
            list(results_per_member.keys()),
        )
        self.assertEqual(
            1,
            len(results_per_member[CareAdvocateMemberTransitionResponse.SUCCESS.name]),
        )
        self._assert_successful_transition(self.user_1.id)

    def test_perform_care_advocate_member_transitions__multiple_transitions__multiple_users_transitioned(
        self,
    ):
        self._set_up_transition_log_entry(
            self.scheduler_1,
            {
                self.user_1.id: [self.farewell_template.message_type],
                self.user_2.id: [self.followup_intro_template.message_type],
            },
        )

        (
            results_per_member,
            results_per_user,
        ) = perform_care_advocate_member_transitions()

        self.assertEqual(
            [CareAdvocateMemberTransitionResponse.SUCCESS.name],
            list(results_per_member.keys()),
        )
        self.assertEqual(
            2,
            len(results_per_member[CareAdvocateMemberTransitionResponse.SUCCESS.name]),
        )
        self._assert_successful_transition(self.user_1.id)
        self._assert_successful_transition(self.user_2.id)

    def test_perform_care_advocate_member_transitions__transitions_for_multiple_submitters__results_recorded_per_submitter(
        self,
    ):
        self._set_up_transition_log_entry(
            self.scheduler_1,
            {
                self.user_1.id: [self.farewell_template.message_type],
            },
        )
        self._set_up_transition_log_entry(
            self.scheduler_2,
            {
                self.user_2.id: [self.followup_intro_template.message_type],
            },
        )

        (
            results_per_member,
            results_per_user,
        ) = perform_care_advocate_member_transitions()

        self.assertEqual(
            [CareAdvocateMemberTransitionResponse.SUCCESS.name],
            list(results_per_member.keys()),
        )
        self.assertEqual(
            2,
            len(results_per_member[CareAdvocateMemberTransitionResponse.SUCCESS.name]),
        )

        self.assertEqual(
            {self.scheduler_1.id, self.scheduler_2.id},
            set(results_per_user.keys()),
        )
        self.assertEqual(
            [CareAdvocateMemberTransitionResponse.SUCCESS.name],
            list(results_per_user[self.scheduler_1.id].keys()),
        )
        self.assertEqual(
            [CareAdvocateMemberTransitionResponse.SUCCESS.name],
            list(results_per_user[self.scheduler_1.id].keys()),
        )
        self.assertEqual(
            1,
            len(
                results_per_user[self.scheduler_1.id][
                    CareAdvocateMemberTransitionResponse.SUCCESS.name
                ]
            ),
        )
        self.assertEqual(
            1,
            len(
                results_per_user[self.scheduler_2.id][
                    CareAdvocateMemberTransitionResponse.SUCCESS.name
                ]
            ),
        )

        self._assert_successful_transition(self.user_1.id)
        self._assert_successful_transition(self.user_2.id)

    def test_perform_care_advocate_member_transitions__unknown_message_type__error_recorded(
        self,
    ):
        self._set_up_transition_log_entry(
            self.scheduler_1,
            {
                self.user_1.id: ["Fakey McFake Message Type"],
            },
        )

        (
            results_per_member,
            results_per_user,
        ) = perform_care_advocate_member_transitions()

        self.assertEqual(
            [TransitionLogValidatorError.MESSAGE_TYPE_UNKNOWN.name],
            list(results_per_member.keys()),
        )
        self.assertEqual(
            1,
            len(
                results_per_member[
                    TransitionLogValidatorError.MESSAGE_TYPE_UNKNOWN.name
                ]
            ),
        )
        self._assert_failed_transition(self.user_1.id)

    def test_perform_care_advocate_member_transitions__no_message_type_provided__transition_succeeds(
        self,
    ):
        self._set_up_transition_log_entry(
            self.scheduler_1,
            {self.user_1.id: []},
        )

        (
            results_per_member,
            results_per_user,
        ) = perform_care_advocate_member_transitions()

        self.assertEqual(
            [CareAdvocateMemberTransitionResponse.SUCCESS.name],
            list(results_per_member.keys()),
        )
        self.assertEqual(
            1,
            len(results_per_member[CareAdvocateMemberTransitionResponse.SUCCESS.name]),
        )
        self._assert_successful_transition(self.user_1.id)

    def test_perform_care_advocate_member_transitions__invalid_member__error_recorded(
        self,
    ):
        self._set_up_transition_log_entry(
            self.scheduler_1,
            {123456: [self.farewell_template.message_type]},
        )

        (
            results_per_member,
            results_per_user,
        ) = perform_care_advocate_member_transitions()
        self.assertEqual(
            [TransitionLogValidatorError.ALL_USERS_NOT_FOUND.name],
            list(results_per_member.keys()),
        )
        self.assertEqual(
            1,
            len(
                results_per_member[TransitionLogValidatorError.ALL_USERS_NOT_FOUND.name]
            ),
        )
        self._assert_failed_transition(self.user_1.id)

    def test_perform_care_advocate_member_transitions__invalid_old_cx__error_recorded(
        self,
    ):
        self._set_up_transition_log_entry(
            self.scheduler_1,
            {self.user_1.id: [self.farewell_template.message_type]},
            old_cx_id=123456,
        )

        (
            results_per_member,
            results_per_user,
        ) = perform_care_advocate_member_transitions()

        self.assertEqual(
            [TransitionLogValidatorError.ALL_USERS_NOT_FOUND.name],
            list(results_per_member.keys()),
        )
        self.assertEqual(
            1,
            len(
                results_per_member[TransitionLogValidatorError.ALL_USERS_NOT_FOUND.name]
            ),
        )
        self._assert_failed_transition(self.user_1.id)

    def test_perform_care_advocate_member_transitions__invalid_new_cx__error_recorded(
        self,
    ):
        self._set_up_transition_log_entry(
            self.scheduler_1,
            {self.user_1.id: [self.farewell_template.message_type]},
            new_cx_id=123456,
        )

        (
            results_per_member,
            results_per_user,
        ) = perform_care_advocate_member_transitions()

        self.assertEqual(
            [TransitionLogValidatorError.ALL_USERS_NOT_FOUND.name],
            list(results_per_member.keys()),
        )
        self.assertEqual(
            1,
            len(
                results_per_member[TransitionLogValidatorError.ALL_USERS_NOT_FOUND.name]
            ),
        )
        self._assert_failed_transition(self.user_1.id)

    @mock.patch("care_advocates.tasks.transitions.reassign_care_advocate")
    def test_perform_care_advocate_member_transitions__reassign_care_advocate_1_1(
        self, mock_reassign_care_advocate
    ):
        # Given - transition is scheduled for one user with one message
        member_1 = self.user_1
        old_cx_1 = self.practitioner_1
        new_cx_1 = self.practitioner_2
        message_templates_1 = [self.farewell_template]
        message_types_1 = [self.farewell_template.message_type]
        self._set_up_transition_log_entry(
            self.scheduler_1,
            {member_1.id: message_types_1},
            old_cx_1.id,
            new_cx_1.id,
        )
        mock_reassign_care_advocate.return_value = (
            CareAdvocateMemberTransitionResponse.SUCCESS.name
        )

        # When - we process transitions
        perform_care_advocate_member_transitions()

        # Then reassign_member_transition is called once with the correct parameters
        mock_reassign_care_advocate.assert_called_once()
        mock_reassign_care_advocate.assert_called_with(
            member=member_1,
            old_cx=old_cx_1,
            new_cx=new_cx_1,
            message_templates=message_templates_1,
            l10n_flag=False,
        )

    @mock.patch("care_advocates.tasks.transitions.reassign_care_advocate")
    def test_perform_care_advocate_member_transitions__reassign_care_advocate_2_3(
        self, mock_reassign_care_advocate
    ):
        # Given - transition is scheduled for two user with three messages (2,1)
        # Member 1
        member_1 = self.user_1
        old_cx_1 = self.practitioner_1
        new_cx_1 = self.practitioner_2
        message_templates_1 = [self.farewell_template, self.followup_intro_template]
        message_types_1 = [
            self.farewell_template.message_type,
            self.followup_intro_template.message_type,
        ]
        # Member 2
        member_2 = self.user_2
        old_cx_2 = old_cx_1
        new_cx_2 = new_cx_1
        message_templates_2 = [self.farewell_template]
        message_types_2 = [self.farewell_template.message_type]
        # Setup method currently only allows 1 old/new ca
        self._set_up_transition_log_entry(
            self.scheduler_1,
            {member_1.id: message_types_1, member_2.id: message_types_2},
            old_cx_1.id,
            new_cx_1.id,
        )
        mock_reassign_care_advocate.return_value = (
            CareAdvocateMemberTransitionResponse.SUCCESS.name
        )

        # When - we process transitions
        perform_care_advocate_member_transitions()

        # Then reassign_member_transition is called twice with the correct parameters
        assert mock_reassign_care_advocate.call_count == 2
        calls = [
            mock.call(
                member=member_1,
                old_cx=old_cx_1,
                new_cx=new_cx_1,
                message_templates=message_templates_1,
                l10n_flag=False,
            ),
            mock.call(
                member=member_2,
                old_cx=old_cx_2,
                new_cx=new_cx_2,
                message_templates=message_templates_2,
                l10n_flag=False,
            ),
        ]
        mock_reassign_care_advocate.assert_has_calls(calls)


class TestCareAdvocateMemberTransitionLogService:
    def test_uow(
        self,
        transition_log_service,
        mock_transition_log_repo,
        mock_transition_log_repo_cls,
    ):
        # Given
        expected_repository = mock_transition_log_repo

        # When
        with transition_log_service.uow() as uow:
            # Then
            assert uow.get_repo(mock_transition_log_repo_cls) is expected_repository

    def test_get_transition_logs_data__no_content(
        self, transition_log_service, mock_transition_log_repo
    ):
        # Given
        expected_logs_data = []
        mock_transition_log_repo.all.return_value = expected_logs_data

        # When
        transition_logs_data = transition_log_service.get_transition_logs_data()

        # Then
        mock_transition_log_repo.all.assert_called_once_with("date_transition")
        assert transition_logs_data == expected_logs_data

    def test_get_transition_logs_data__successful(
        self, transition_log_service, mock_transition_log_repo, all_transition_logs
    ):
        # Given
        expected_transition_logs_data = [
            {
                "id": tl.id,
                "user_id": tl.user_id,
                "user_name": tl.user.full_name,
                "date_uploaded": tl.created_at,
                "date_of_transition": tl.date_transition,
                "uploaded_file": tl.uploaded_filename,
                "canDelete": False if tl.date_completed else True,
                "rowProps": {"style": {"fontWeight": "bold"}}
                if not tl.date_completed
                else {},
            }
            for tl in all_transition_logs
        ]
        mock_transition_log_repo.all.return_value = all_transition_logs

        # When
        transition_logs_data = transition_log_service.get_transition_logs_data()

        # Then
        mock_transition_log_repo.all.assert_called_once()
        assert transition_logs_data == expected_transition_logs_data

    def test_delete_transition_log__transition_log_does_not_exist(
        self, transition_log_service, mock_transition_log_repo
    ):
        # Given
        invalid_transition_log_id = 1
        mock_transition_log_repo.get.return_value = None

        # Then
        with pytest.raises(IncorrectTransitionLogIDError):
            # When
            transition_log_service.delete_transition_log(
                id=invalid_transition_log_id,
            )

        # Then
        mock_transition_log_repo.get.assert_called_once_with(
            id=invalid_transition_log_id
        )

    def test_delete_transition_log__cant_delete_completed_transition_log(
        self, transition_log_service, mock_transition_log_repo, completed_transition_log
    ):
        # Given
        mock_transition_log_repo.get.return_value = completed_transition_log

        # Then
        with pytest.raises(AlreadyCompletedTransitionError):
            # When
            transition_log_service.delete_transition_log(
                id=completed_transition_log.id,
            )

        # Then
        mock_transition_log_repo.get.assert_called_once_with(
            id=completed_transition_log.id
        )

    @mock.patch("flask_login.current_user")
    def test_delete_transition_log__can_delete_incompleted_transition_log(
        self,
        mock_current_user,
        transition_log_service,
        mock_transition_log_uow_cls,
        mock_transition_log_repo,
        incompleted_transition_log,
    ):
        # Given
        mock_transition_log_repo.get.return_value = incompleted_transition_log
        mock_transition_log_repo.delete.return_value = 1

        # When
        transition_log_service.delete_transition_log(id=incompleted_transition_log.id)

        # Then
        mock_transition_log_repo.get.assert_called_once_with(
            id=incompleted_transition_log.id
        )
        mock_transition_log_repo.delete.assert_called_once_with(
            id=incompleted_transition_log.id
        )

        mock_transition_log_uow_cls.return_value.commit.assert_called_once()

    def test_download_transition_log_csv__transition_log_does_not_exist(
        self, transition_log_service, mock_transition_log_repo
    ):
        # Given
        invalid_transition_log_id = 1
        mock_transition_log_repo.get.return_value = None

        # Then
        with pytest.raises(IncorrectTransitionLogIDError):
            # When
            transition_log_service.download_transition_log_csv(
                id=invalid_transition_log_id,
            )
        mock_transition_log_repo.get.assert_called_once_with(
            id=invalid_transition_log_id
        )

    def test_download_transition_log_csv__successful_download(
        self,
        transition_log_service,
        mock_transition_log_repo,
        completed_transition_log,
    ):
        # Given
        mock_transition_log_repo.get.return_value = completed_transition_log
        # When
        (
            csv_lines_str,
            uploaded_filename,
        ) = transition_log_service.download_transition_log_csv(
            id=completed_transition_log.id,
        )

        # Then
        mock_transition_log_repo.get.assert_called_once_with(
            id=completed_transition_log.id
        )
        assert uploaded_filename == completed_transition_log.uploaded_filename

        # expected_csv_lines_str built from looking at CareAdvocateMemberTransitionLogFactory
        expected_csv_lines_str = "member_id,old_cx_id,new_cx_id,messaging\n1,2,3,SHORT_GOODBYE;SOFT_INTRO\n4,5,6,LONG_GOODBYE"
        assert csv_lines_str == expected_csv_lines_str

    @mock.patch("flask_login.current_user")
    def test_submit_transition_log__successful(
        self,
        mock_current_user,
        transition_log_service,
        mock_transition_log_uow_cls,
        mock_transition_log_repo,
        scheduler,
    ):
        # Given
        member_id, old_prac_id, new_prac_id = 1, 2, 3
        message_type = "FAREWELL;FOLLOWUP_INTRO"
        transitions_csv_filename = "transitions_file.csv"
        transitions_csv_mock = MagicMock(autospec=FileStorage)
        transitions_csv_mock.filename = transitions_csv_filename
        mocked_transition_log = MagicMock(autospec=CareAdvocateMemberTransitionLog)
        mocked_transition_log.user_id = scheduler.id
        datetime_now = datetime.datetime.now().replace(microsecond=0)
        mocked_transition_log.date_scheduled = datetime_now
        mocked_transition_log.uploaded_filename = transitions_csv_filename

        mock_transition_log_repo.create.return_value = mocked_transition_log

        with patch(
            "care_advocates.services.transition_log.CareAdvocateMemberTransitionLogService._parse_transitions_data_from_csv"
        ) as _parse_transitions_data_from_csv_mock, patch(
            "care_advocates.services.transition_log.CareAdvocateMemberTransitionLogService._convert_transitions_json"
        ) as _convert_transitions_json_mock:

            _parse_transitions_data_from_csv_mock_return_value = [
                [member_id, old_prac_id, new_prac_id, message_type]
            ]
            _parse_transitions_data_from_csv_mock.return_value = (
                _parse_transitions_data_from_csv_mock_return_value
            )
            _convert_transitions_json_mock.return_value = [
                {
                    "member_id": member_id,
                    "old_cx_id": old_prac_id,
                    "new_cx_id": new_prac_id,
                    "messaging": message_type,
                }
            ]

            # When
            transition_log = transition_log_service.submit_transition_log(
                user_id=scheduler.id,
                transition_date=datetime_now,
                transitions_csv=transitions_csv_mock,
            )

        # Then
        mock_transition_log_repo.create.assert_called_once()
        _parse_transitions_data_from_csv_mock.assert_called_once_with(
            transitions_csv_mock
        )
        _convert_transitions_json_mock.assert_called_once_with(
            _parse_transitions_data_from_csv_mock_return_value
        )
        mock_transition_log_uow_cls.return_value.commit.assert_called_once()

        assert transition_log is not None
        assert transition_log.user_id == scheduler.id
        assert transition_log.date_scheduled == datetime_now
        assert transition_log.uploaded_filename == transitions_csv_filename

    def test__parse_transitions_data_from_csv__successful(
        self,
        transition_log_service,
        member,
        care_advocate,
        care_advocate_2,
        message_types,
        csv_file_for_submission__valid,
    ):
        # Given

        # When
        transitions_data = transition_log_service._parse_transitions_data_from_csv(
            csv_file_for_submission__valid
        )

        # Then
        assert transitions_data == [
            [member.id, care_advocate.id, care_advocate_2.id, message_types]
        ]

    def test__parse_transitions_data_from_csv__invalid_filetype(
        self,
        transition_log_service,
        csv_file_for_submission__invalid_filetype,
    ):
        # When
        with pytest.raises(SubmittingTransitionLogErrors) as e:
            transition_log_service._parse_transitions_data_from_csv(
                csv_file_for_submission__invalid_filetype
            )
        # Then
        assert (
            e.value.errors[0].split(":")[0]
            == CareAdvocateMemberTransitionLogServiceMessage.FILE_ATTRIBUTE_ERROR
        )

    def test__parse_transitions_data_from_csv__invalid_encoding(
        self,
        transition_log_service,
        csv_file_for_submission__invalid_encoding,
    ):
        # When
        with pytest.raises(SubmittingTransitionLogErrors) as e:
            transition_log_service._parse_transitions_data_from_csv(
                csv_file_for_submission__invalid_encoding
            )
        # Then
        assert (
            e.value.errors[0].split(":")[0]
            == CareAdvocateMemberTransitionLogServiceMessage.NOT_IN_CSV_FORMAT
        )

    def test__parse_transitions_data_from_csv__invalid_data(
        self,
        transition_log_service,
        csv_file_for_submission__invalid_data,
    ):
        # When
        with pytest.raises(SubmittingTransitionLogErrors) as e:
            transition_log_service._parse_transitions_data_from_csv(
                csv_file_for_submission__invalid_data
            )
        # Then
        assert (
            e.value.errors[0].split(":")[0]
            == TransitionLogValidatorError.INVALID_CSV_DATA
        )

    def test__parse_transitions_data_from_csv__invalid_csv_headers(
        self,
        transition_log_service,
        csv_file_for_submission__missing_headers,
    ):
        # When
        with pytest.raises(SubmittingTransitionLogErrors) as e:
            transition_log_service._parse_transitions_data_from_csv(
                csv_file_for_submission__missing_headers
            )
        # Then
        assert (
            e.value.errors[0].split(":")[0]
            == TransitionLogValidatorError.INVALID_CSV_HEADERS
        )

    def test__parse_transitions_data_from_csv__no_transitions(
        self,
        transition_log_service,
        message_types,
        csv_file_for_submission__no_transitions,
    ):
        # Given
        with pytest.raises(SubmittingTransitionLogErrors) as e:
            # When
            transition_log_service._parse_transitions_data_from_csv(
                csv_file_for_submission__no_transitions
            )
        # Then
        assert (
            e.value.errors[0]
            == CareAdvocateMemberTransitionLogServiceMessage.NO_TRANSITIONS_FOUND
        )

    def test__convert_transitions_json(self, transition_log_service):
        # Given
        transitions = [[1, 2, 3, "FAREWELL"], [4, 5, 6, "FOLLOWUP_INTRO"]]
        expected_transitions_json = [
            {
                "member_id": 1,
                "old_cx_id": 2,
                "new_cx_id": 3,
                "messaging": "FAREWELL",
            },
            {
                "member_id": 4,
                "old_cx_id": 5,
                "new_cx_id": 6,
                "messaging": "FOLLOWUP_INTRO",
            },
        ]

        # When
        transitions_json = transition_log_service._convert_transitions_json(transitions)

        # Then
        assert transitions_json == expected_transitions_json

    def test__transition_error_str__row_is_dict(self, transition_log_service):
        # Given
        error = (TransitionLogValidatorError.MISSING_MEMBER_PROFILE,)
        row = {
            "member_id": "1",
            "old_cx_id": "2",
            "new_cx_id": "3",
            "messaging": "FAREWELL",
        }
        expected_error_str = f"{error}: {list(row.values())}"
        # When
        error_str = transition_log_service._transition_error_str(error, row)
        # Then
        assert error_str == expected_error_str

    def test__transition_error_str__row_is_not_dict(self, transition_log_service):
        # Given
        error = (TransitionLogValidatorError.MISSING_MEMBER_PROFILE,)
        row = [1, 2, 3, "FAREWELL"]
        expected_error_str = f"{error}: {row}"
        # When
        error_str = transition_log_service._transition_error_str(error, row)
        # Then
        assert error_str == expected_error_str


class TestCareAdvocateMemberTransitionTemplateService:
    def test_uow(
        self,
        transition_template_service,
        mock_transition_template_repo,
        mock_transition_template_repo_cls,
    ):
        # Given
        expected_repository = mock_transition_template_repo

        # When
        with transition_template_service.uow() as uow:
            assert (
                uow.get_repo(mock_transition_template_repo_cls) is expected_repository
            )

    def test_get_all_message_types__no_transition_templates(
        self, transition_template_service, mock_transition_template_repo
    ):
        # Given
        expected_message_types = []
        mock_transition_template_repo.all.return_value = expected_message_types
        # When
        message_types = transition_template_service.get_all_message_types()
        # Then
        mock_transition_template_repo.all.assert_called_once()
        assert message_types == expected_message_types

    def test_get_all_message_types__successful(
        self,
        transition_template_service,
        mock_transition_template_repo,
        farewell_transition_template,
        followup_intro_transition_template,
    ):
        # Given
        expected_message_types = [
            farewell_transition_template.message_type,
            followup_intro_transition_template.message_type,
        ]
        mock_transition_template_repo.all.return_value = [
            farewell_transition_template,
            followup_intro_transition_template,
        ]
        # When
        message_types = transition_template_service.get_all_message_types()
        # Then
        mock_transition_template_repo.all.assert_called_once()
        assert message_types == expected_message_types

    def test_get_transition_templates_data__no_transitions_templates(
        self, transition_template_service, mock_transition_template_repo
    ):
        # Given
        sort_column = "message_type"
        transition_templates_edit_url = "a_fake_transition_templates_edit_url/_id_"
        mock_transition_template_repo.all.return_value = []
        # When
        transition_templates_data = (
            transition_template_service.get_transition_templates_data(
                sort_column, transition_templates_edit_url
            )
        )
        # Then
        mock_transition_template_repo.all.assert_called_once()
        assert transition_templates_data == []

    def test_get_transition_templates_data__successful(
        self,
        transition_template_service,
        mock_transition_template_repo,
        farewell_transition_template,
        followup_intro_transition_template,
    ):
        # Given
        sort_column = "message_type"
        transition_templates_edit_url = "a_fake_transition_templates_edit_url/_id_"
        mock_transition_template_repo.all.return_value = [
            farewell_transition_template,
            followup_intro_transition_template,
        ]
        paragraph_preview_mocked_response = "a_paragraph_preview_mocked_response"
        expected_transition_templates_data = [
            {
                "id": tt.id,
                "message_type": tt.message_type,
                "message_description": tt.message_description,
                "message_body": paragraph_preview_mocked_response,
                "EditURL": transition_templates_edit_url.replace("_id_", str(tt.id)),
            }
            for tt in [farewell_transition_template, followup_intro_transition_template]
        ]

        with patch(
            "care_advocates.services.transition_template.CareAdvocateMemberTransitionTemplateService._get_paragraph_preview",
            return_value=paragraph_preview_mocked_response,
        ) as _get_paragraph_preview_mock:

            # When
            transition_templates_data = (
                transition_template_service.get_transition_templates_data(
                    sort_column, transition_templates_edit_url
                )
            )

        # Then
        _get_paragraph_preview_mock.assert_has_calls(
            [
                call(farewell_transition_template.message_body),
                call(followup_intro_transition_template.message_body),
            ]
        )
        mock_transition_template_repo.all.assert_called_once()
        assert transition_templates_data == expected_transition_templates_data

    def test__get_paragraph_preview__large_min_preview_length(
        self,
        transition_template_service,
        farewell_transition_template,
    ):
        # Given
        expected_paragraph_preview = farewell_transition_template.message_body
        # When
        paragraph_preview = transition_template_service._get_paragraph_preview(
            paragraph=farewell_transition_template.message_body,
            min_preview_length=sys.maxsize,
        )
        # Then
        assert expected_paragraph_preview == paragraph_preview

    def test__get_paragraph_preview__default_args(self, farewell_transition_template):

        # Given
        # Lets set message body to be of length between 150 and 160 (default args)
        message_body = "hi " * (160 // len("hi "))
        farewell_transition_template.message_body = message_body
        expected_paragraph_preview = ""
        while len(expected_paragraph_preview) <= 150:
            expected_paragraph_preview += "hi "
        expected_paragraph_preview = expected_paragraph_preview[:-1] + "..."
        # When
        paragraph_preview = (
            CareAdvocateMemberTransitionTemplateService()._get_paragraph_preview(
                paragraph=farewell_transition_template.message_body
            )
        )
        # Then
        assert paragraph_preview == expected_paragraph_preview


class TestCareAdvocateMemberTransitionLogRepository:
    def test_make_table(self):
        # When
        table = CareAdvocateMemberTransitionLogRepository().make_table()
        # Then
        assert table.name == "ca_member_transition_log"

    def test_table_name(self):
        # When
        table_name = CareAdvocateMemberTransitionLogRepository().table_name()
        # Then
        assert table_name == "ca_member_transition_log"

    def test_table_columns(self):
        # When
        table_columns = CareAdvocateMemberTransitionLogRepository().table_columns()
        # Then
        assert table_columns == ()

    def test_instance_to_values(self, completed_transition_log):
        # Given
        expected_values = {
            "id": completed_transition_log.id,
            "user_id": completed_transition_log.user_id,
            "date_completed": completed_transition_log.date_completed,
            "date_scheduled": completed_transition_log.date_scheduled,
            "uploaded_filename": completed_transition_log.uploaded_filename,
            "uploaded_content": completed_transition_log.uploaded_content,
        }
        # When
        values = CareAdvocateMemberTransitionLogRepository().instance_to_values(
            completed_transition_log
        )
        # Then
        assert values == expected_values

    def test_all__no_transition_logs(self):
        # Given
        expected_transition_logs = []
        # When
        transition_logs = CareAdvocateMemberTransitionLogRepository().all()
        # Then
        assert transition_logs == expected_transition_logs

    def test_all__default_sort(self, all_transition_logs):
        # Given
        all_transition_logs.sort(key=lambda x: x.date_transition, reverse=True)
        expected_transition_logs = all_transition_logs
        # When
        transition_logs = CareAdvocateMemberTransitionLogRepository().all()
        # Then
        assert transition_logs == expected_transition_logs

    def test_all__custom_sort(self, all_transition_logs):
        # Given
        all_transition_logs.sort(key=lambda x: x.created_at, reverse=True)
        expected_transition_logs = all_transition_logs
        # When
        transition_logs = CareAdvocateMemberTransitionLogRepository().all("created_at")
        # Then
        assert transition_logs == expected_transition_logs


class TestCareAdvocateMemberTransitionTemplateRepository:
    def test_make_table(self):
        # When
        table = CareAdvocateMemberTransitionTemplateRepository().make_table()
        # Then
        assert table.name == "ca_member_transition_template"

    def test_table_name(self):
        # When
        table_name = CareAdvocateMemberTransitionTemplateRepository().table_name()
        # Then
        assert table_name == "ca_member_transition_template"

    def test_table_columns(self):
        # When
        table_columns = CareAdvocateMemberTransitionTemplateRepository().table_columns()
        # Then
        assert table_columns == ()

    def test_instance_to_values(self, farewell_transition_template):
        # Given
        expected_values = {
            "id": farewell_transition_template.id,
            "message_type": farewell_transition_template.message_type,
            "message_description": farewell_transition_template.message_description,
            "message_body": farewell_transition_template.message_body,
        }
        # When
        values = CareAdvocateMemberTransitionTemplateRepository().instance_to_values(
            farewell_transition_template
        )
        # Then
        assert values == expected_values

    def test_all__no_transition_templates(self):
        # Given
        expected_transition_templates = []
        # When
        transition_templates = CareAdvocateMemberTransitionTemplateRepository().all()
        # Then
        assert transition_templates == expected_transition_templates

    def test_all__default_sort(self, all_transition_templates):
        # Given
        all_transition_templates.sort(key=lambda x: x.message_type, reverse=False)
        expected_transition_templates = all_transition_templates
        # When
        transition_templates = CareAdvocateMemberTransitionTemplateRepository().all()
        # Then
        assert transition_templates == expected_transition_templates

    def test_all__custom_sort(self, all_transition_templates):
        # Given
        all_transition_templates.sort(key=lambda x: x.message_body, reverse=False)
        expected_transition_templates = all_transition_templates
        # When
        transition_templates = CareAdvocateMemberTransitionTemplateRepository().all(
            "message_body"
        )
        assert transition_templates == expected_transition_templates


class TestReassignCareAdvocate:
    @mock.patch.object(Template, "__init__")
    def test_reassign_care_advocate__valid_transition_no_message(
        self,
        mock_template,
        member_old_new_cx,
    ):
        # Given - the information is all valid, (no message to send still)

        # When - we process the reassign
        response = reassign_care_advocate(
            member_old_new_cx["member"],
            member_old_new_cx["old_cx"],
            member_old_new_cx["new_cx"],
            {},
        )

        # Then - the expected error response is returned
        assert response == CareAdvocateMemberTransitionResponse.SUCCESS.name
        mock_template.assert_not_called()

    @mock.patch("care_advocates.tasks.transitions._send_member_message")
    def test_reassign_care_advocate__valid_one_message(
        self,
        mock_send_member_message,
        member_old_new_cx,
        message_templates_one,
    ):
        # Given - the information is all valid
        # When - we process the reassign
        response = reassign_care_advocate(
            member_old_new_cx["member"],
            member_old_new_cx["old_cx"],
            member_old_new_cx["new_cx"],
            message_templates_one,
        )

        # Then - success and the message class is called one time
        assert response == CareAdvocateMemberTransitionResponse.SUCCESS.name
        mock_send_member_message.assert_called_once()

    @mock.patch("care_advocates.tasks.transitions._send_member_message")
    def test_reassign_care_advocate__valid_two_messages(
        self, mock_send_member_message, member_old_new_cx, message_templates_two
    ):
        # Given - the information is all valid
        # When - we process the reassign
        response = reassign_care_advocate(
            member_old_new_cx["member"],
            member_old_new_cx["old_cx"],
            member_old_new_cx["new_cx"],
            message_templates_two,
        )

        # Then - success and the message class is called one time
        assert response == CareAdvocateMemberTransitionResponse.SUCCESS.name
        assert mock_send_member_message.call_count == 2

    @mock.patch("care_advocates.tasks.transitions._send_member_message")
    @pytest.mark.parametrize(
        "member_locale",
        [
            Locale("en"),
            Locale("es"),
            Locale("fr"),
            Locale("fr_ca"),
        ],
    )
    def test_reassign_care_advocate__with_locale(
        self,
        mock_send_member_message,
        member_locale,
        member_old_new_cx,
        message_templates_two,
        release_mono_api_localization_on,
    ):
        """
        Tests that message bodies are translated before sending to the member
        """
        expected_message_body = "abc"

        with mock.patch(
            "care_advocates.tasks.transitions.TranslateDBFields.get_translated_ca_member_transition",
            return_value=expected_message_body,
        ) as translation_mock, mock.patch(
            "care_advocates.tasks.transitions.LocalePreferenceService.get_preferred_locale_for_user",
        ) as get_preferred_locale_mock:
            get_preferred_locale_mock.return_value = member_locale
            # When - we process the reassign
            response = reassign_care_advocate(
                member_old_new_cx["member"],
                member_old_new_cx["old_cx"],
                member_old_new_cx["new_cx"],
                message_templates_two,
                l10n_flag=True,
            )

        # Then
        assert response == CareAdvocateMemberTransitionResponse.SUCCESS.name
        assert mock_send_member_message.call_count == 2

        assert translation_mock.call_count == 2
        mock_send_member_message.assert_has_calls(
            [
                call(
                    member_old_new_cx["old_cx"],
                    member_old_new_cx["member"],
                    expected_message_body,
                ),
                call(
                    member_old_new_cx["old_cx"],
                    member_old_new_cx["member"],
                    expected_message_body,
                ),
            ],
            any_order=True,
        )

    @mock.patch("tasks.messaging.send_to_zendesk.delay")
    @mock.patch("tasks.notifications.notify_new_message.delay")
    def test__send_member_message(
        self,
        mock_notify_new_message,
        mock_send_to_zendesk_delay,
        member_old_new_cx,
    ):

        # When - we send the message
        response = _send_member_message(
            member_old_new_cx["member"], member_old_new_cx["old_cx"], "Test Message"
        )

        # Then - We didn't get an error
        assert response != CareAdvocateMemberTransitionResponse.MESSAGE_EXCEPTION
        # The zendesk/notification methods are called
        mock_notify_new_message.assert_called_once()
        mock_send_to_zendesk_delay.assert_called_once_with(
            mock.ANY,
            initial_cx_message=True,
            user_need_when_solving_ticket="customer-need-member-proactive-outreach-care-team-update",
            service_ns="admin_care_advocate_member_transitions",
            team_ns="care_discovery",
            caller="reassign_care_advocate",
        )


class TestCareAdvocateMemberTransitionValidator:
    def test_init__message_templates_templates(self, message_templates_two):
        # Given - two message types loaded (fixture)
        # When - we create a validator instance
        validator = CareAdvocateMemberTransitionValidator()

        # Then - the templates are loaded from the database
        assert len(validator.message_templates) == 2
        assert message_templates_two[0] in validator.message_templates.values()
        assert message_templates_two[1] in validator.message_templates.values()

    def test_validate__all_users_not_found(self, message_types_one):
        # Given - an invalid new_cx, member, old_cx
        member = None
        old_cx = None
        new_cx = None
        expected_error = TransitionLogValidatorError.ALL_USERS_NOT_FOUND.name

        # When - we validate the record
        validator = CareAdvocateMemberTransitionValidator()
        validation_error = validator.validate(member, old_cx, new_cx, message_types_one)

        # Then - the correct error message is returned
        assert validation_error.message_name == expected_error

    def test_validate__all_users_not_found__member_is_none(
        self, message_types_one, member_old_new_cx
    ):
        # Given - an invalid member, valid old_cx, valid new_cx
        member = None
        old_cx = member_old_new_cx["old_cx"]
        new_cx = member_old_new_cx["new_cx"]
        expected_error = TransitionLogValidatorError.ALL_USERS_NOT_FOUND.name

        # When - we validate the record
        validator = CareAdvocateMemberTransitionValidator()
        validation_error = validator.validate(member, old_cx, new_cx, message_types_one)

        # Then - the correct error message is returned
        assert validation_error.message_name == expected_error

    def test_validate__all_users_not_found__old_cx_is_none(
        self, message_types_one, member_old_new_cx
    ):
        # Given - an invalid old_cx, valid member, valid new_cx
        member = member_old_new_cx["member"]
        old_cx = None
        new_cx = member_old_new_cx["new_cx"]
        expected_error = TransitionLogValidatorError.ALL_USERS_NOT_FOUND.name

        # When - we validate the record
        validator = CareAdvocateMemberTransitionValidator()
        validation_error = validator.validate(member, old_cx, new_cx, message_types_one)

        # Then - the correct error message is returned
        assert validation_error.message_name == expected_error

    def test_validate__all_users_not_found__new_cx_is_none(
        self, message_types_one, member_old_new_cx
    ):
        # Given - an invalid new_cx, valid member, valid old_cx
        member = member_old_new_cx["member"]
        old_cx = member_old_new_cx["old_cx"]
        new_cx = None
        expected_error = TransitionLogValidatorError.ALL_USERS_NOT_FOUND.name

        # When - we validate the record
        validator = CareAdvocateMemberTransitionValidator()
        validation_error = validator.validate(member, old_cx, new_cx, message_types_one)

        # Then - the correct error message is returned
        assert validation_error.message_name == expected_error

    def test_validate__message_type_unknown(self, member_old_new_cx):
        # Given - an unknown message type
        member = member_old_new_cx["member"]
        old_cx = member_old_new_cx["old_cx"]
        new_cx = member_old_new_cx["new_cx"]
        message_types_one = ["INVALID_MESSAGE_TYPE"]
        expected_error = TransitionLogValidatorError.MESSAGE_TYPE_UNKNOWN.name

        # When - we validate the record
        validator = CareAdvocateMemberTransitionValidator()
        validation_error = validator.validate(member, old_cx, new_cx, message_types_one)

        # Then - the correct error message is returned
        assert validation_error.message_name == expected_error

    def test_validate__duplicate_member_found(
        self, message_types_one, member_old_new_cx
    ):
        # Given - all valid information
        member = member_old_new_cx["member"]
        old_cx = member_old_new_cx["old_cx"]
        new_cx = member_old_new_cx["new_cx"]
        expected_error = TransitionLogValidatorError.DUPLICATE_MEMBER_FOUND.name

        # When - we validate the same record twice
        validator = CareAdvocateMemberTransitionValidator()
        validation_error_1 = validator.validate(
            member, old_cx, new_cx, message_types_one
        )
        validation_error_2 = validator.validate(
            member, old_cx, new_cx, message_types_one
        )

        # Then - the first time is None, the second time is the expected error
        assert validation_error_1 is None
        assert validation_error_2.message_name == expected_error

    def test_validate__missing_member_profile(
        self, message_types_one, member_old_new_cx
    ):
        # Given - a user without a member_profile
        # This user isn't assigned to the cx, but that is ok for this test
        member = DefaultUserFactory()
        old_cx = member_old_new_cx["old_cx"]
        new_cx = member_old_new_cx["new_cx"]
        expected_error = TransitionLogValidatorError.MISSING_MEMBER_PROFILE.name
        # We need to commit before the uow in the Validator init
        db.session.commit()

        # When - we validate the record
        validator = CareAdvocateMemberTransitionValidator()
        validation_error = validator.validate(member, old_cx, new_cx, message_types_one)

        # Then - the correct error message is returned
        assert validation_error.message_name == expected_error

    def test_validate__invalid_old_cx(
        self, message_types_one, member_old_new_cx, factories
    ):
        # Given - an old_cx that isn't a cx
        member = member_old_new_cx["member"]
        old_cx = factories.PractitionerUserFactory()
        old_cx.practitioner_profile.verticals = [VerticalFactory(name="OB-GYN")]
        new_cx = member_old_new_cx["new_cx"]
        expected_error = TransitionLogValidatorError.INVALID_OLD_CX
        # We need to commit before the uow in the Validator init
        db.session.commit()

        # When - we validate the record
        validator = CareAdvocateMemberTransitionValidator()
        validation_error = validator.validate(member, old_cx, new_cx, message_types_one)

        # Then - the correct error message is returned
        assert validation_error.message_name == expected_error.name

    def test_validate__invalid_new_cx(
        self, message_types_one, member_old_new_cx, factories
    ):
        # Given - a new_cx that isn't a cx
        member = member_old_new_cx["member"]
        old_cx = member_old_new_cx["old_cx"]
        new_cx = factories.PractitionerUserFactory()
        new_cx.practitioner_profile.verticals = [VerticalFactory(name="OB-GYN")]
        expected_error = TransitionLogValidatorError.INVALID_NEW_CX
        # We need to commit before the uow in the Validator init
        db.session.commit()

        # When - we validate the record
        validator = CareAdvocateMemberTransitionValidator()
        validation_error = validator.validate(member, old_cx, new_cx, message_types_one)

        # Then - the correct error message is returned
        assert validation_error.message_name == expected_error.name

    def test_validate__new_cx_already_assigned(
        self, message_types_one, member_old_new_cx
    ):
        # Given - the new_cx is already assigned (we can just switch the pair around)
        member = member_old_new_cx["member"]
        old_cx = member_old_new_cx["new_cx"]
        new_cx = member_old_new_cx["old_cx"]
        expected_error = CareAdvocateMemberTransitionResponse.SUCCESS.name

        # When - we validate the record
        validator = CareAdvocateMemberTransitionValidator()
        validation_error = validator.validate(member, old_cx, new_cx, message_types_one)

        # Then - the correct error message is returned (it is actually a success)
        assert validation_error.message_name == expected_error

    def test_validate__old_cx_not_assigned(
        self, message_types_one, member_old_new_cx, factories
    ):
        # Given - the member has a different cx than assigned
        member = member_old_new_cx["member"]
        old_cx = factories.PractitionerUserFactory()
        factories.AssignableAdvocateFactory.create_with_practitioner(
            practitioner=old_cx
        )
        new_cx = member_old_new_cx["new_cx"]
        expected_error = TransitionLogValidatorError.OLD_CX_NOT_ASSIGNED.name
        # We need to commit before the uow in the Validator init
        db.session.commit()

        # When - we validate the record
        validator = CareAdvocateMemberTransitionValidator()
        validation_error = validator.validate(member, old_cx, new_cx, message_types_one)

        # Then - the correct error message is returned
        assert validation_error.message_name == expected_error
