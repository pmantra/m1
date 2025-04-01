import datetime
import io
import zlib
from typing import List
from unittest.mock import patch

import pytest
from werkzeug.datastructures import FileStorage

from care_advocates.models.matching_rules import (
    MatchingRuleEntityType,
    MatchingRuleType,
)
from care_advocates.pytests.factories import MatchingRuleFactory, MatchingRuleSetFactory
from care_advocates.repository.assignable_advocate import AssignableAdvocateRepository
from care_advocates.services.care_advocate import CareAdvocateService
from care_advocates.services.transition_log import (
    CareAdvocateMemberTransitionLogService,
)
from care_advocates.services.transition_template import (
    CareAdvocateMemberTransitionTemplateService,
)
from models.profiles import CareTeamTypes
from models.tracks.track import TrackName
from pytests.factories import (
    AssignableAdvocateFactory,
    CareAdvocateMemberTransitionLogFactory,
    CareAdvocateMemberTransitionTemplateFactory,
    DefaultUserFactory,
    MemberFactory,
    PractitionerUserFactory,
    VerticalFactory,
)


@pytest.fixture
def scheduler():
    scheduler = DefaultUserFactory()
    return scheduler


@pytest.fixture
def completed_transition_log(scheduler):
    completed_transition_log = CareAdvocateMemberTransitionLogFactory(
        user_id=scheduler.id, date_completed=datetime.datetime.now()
    )
    return completed_transition_log


@pytest.fixture
def incompleted_transition_log(scheduler):
    incompleted_transition_log = CareAdvocateMemberTransitionLogFactory(
        user_id=scheduler.id
    )
    return incompleted_transition_log


@pytest.fixture
def all_transition_logs(completed_transition_log, incompleted_transition_log):
    return [completed_transition_log, incompleted_transition_log]


@pytest.fixture
def member():
    member = MemberFactory()
    return member


@pytest.fixture
def member_2():
    member_2 = MemberFactory()
    return member_2


@pytest.fixture
def default_user(factories):
    return factories.DefaultUserFactory.create()


@pytest.fixture
def default_member(factories):
    return factories.MemberFactory.create()


@pytest.fixture
def obgyn_practitioner(factories):
    prac = PractitionerUserFactory.create()
    prac.practitioner_profile.verticals = [VerticalFactory.create(name="OB-GYN")]
    return prac


@pytest.fixture
def care_advocate():
    prac = PractitionerUserFactory()
    AssignableAdvocateFactory.create_with_practitioner(practitioner=prac)
    return prac


@pytest.fixture
def care_advocate_2():
    prac = PractitionerUserFactory()
    AssignableAdvocateFactory.create_with_practitioner(practitioner=prac)
    return prac


@pytest.fixture
def default_member_with_ca(default_member, care_advocate, factories):
    factories.MemberPractitionerAssociationFactory.create(
        user_id=default_member.id,
        practitioner_id=care_advocate.id,
        type=CareTeamTypes.CARE_COORDINATOR,
    )
    return default_member


@pytest.fixture
def farewell_transition_template():
    return CareAdvocateMemberTransitionTemplateFactory(message_type="FAREWELL")


@pytest.fixture
def followup_intro_transition_template():
    return CareAdvocateMemberTransitionTemplateFactory(message_type="FOLLOWUP_INTRO")


@pytest.fixture
def all_transition_templates(
    farewell_transition_template, followup_intro_transition_template
):
    return [farewell_transition_template, followup_intro_transition_template]


@pytest.fixture
def message_types(farewell_transition_template, followup_intro_transition_template):
    message_types = (
        farewell_transition_template.message_type
        + ";"
        + followup_intro_transition_template.message_type
    )
    return message_types


@pytest.fixture
def transitions_csv_filename():
    transitions_csv_filename = "transitions_file.csv"
    return transitions_csv_filename


def create_csv_file_for_submission(
    data_row=None, headers_row="member_id,old_cx_id,new_cx_id,messaging"
) -> FileStorage:

    transitions_csv_filename = "transitions_file.csv"

    csv_data = headers_row
    if data_row is not None:
        csv_data = csv_data + "\n" + data_row
    csv_data_in_bytes = bytes(csv_data, "utf-8")

    stream = io.BytesIO(csv_data_in_bytes)

    csvfile_filestorage = FileStorage(
        content_type="text/csv",
        filename=transitions_csv_filename,
        name=transitions_csv_filename,
        content_length=0,
        stream=stream,
    )
    return csvfile_filestorage


def create_csv_file_for_submission_multiple_rows(
    data_rows: List[str], headers_row="member_id,old_cx_id,new_cx_id,messaging"
) -> FileStorage:

    transitions_csv_filename = "transitions_file.csv"

    csv_data = headers_row
    for data_row in data_rows:
        csv_data = csv_data + "\n" + data_row
    csv_data_in_bytes = bytes(csv_data, "utf-8")

    stream = io.BytesIO(csv_data_in_bytes)

    csvfile_filestorage = FileStorage(
        content_type="text/csv",
        filename=transitions_csv_filename,
        name=transitions_csv_filename,
        content_length=0,
        stream=stream,
    )
    return csvfile_filestorage


@pytest.fixture
def csv_file_for_submission__valid(
    member,
    care_advocate,
    care_advocate_2,
    farewell_transition_template,
    followup_intro_transition_template,
) -> FileStorage:

    message_type = (
        farewell_transition_template.message_type
        + ";"
        + followup_intro_transition_template.message_type
    )
    data_row = f"{member.id},{care_advocate.id},{care_advocate_2.id},{message_type}"

    csvfile_filestorage = create_csv_file_for_submission(data_row)
    return csvfile_filestorage


@pytest.fixture
def csv_file_for_submission__invalid_filetype() -> FileStorage:
    data_bytes = b"compressed file content"
    transitions_filename = "transitions_file.gzip"
    gzip_data = zlib.compress(data_bytes)
    filestorage = FileStorage(
        content_type="application/gzip",
        filename=transitions_filename,
        name=transitions_filename,
        content_length=0,
        stream=gzip_data,
    )
    return filestorage


@pytest.fixture
def csv_file_for_submission__invalid_encoding(transitions_csv_filename) -> FileStorage:
    csv_data = "1,2,3,"
    csv_data_in_bytes = bytes(csv_data, "utf-16")
    stream = io.BytesIO(csv_data_in_bytes)
    csvfile_filestorage = FileStorage(
        content_type="text/csv",
        filename=transitions_csv_filename,
        name=transitions_csv_filename,
        content_length=0,
        stream=stream,
    )
    return csvfile_filestorage


@pytest.fixture
def csv_file_for_submission__invalid_data(farewell_transition_template) -> FileStorage:
    message_type = farewell_transition_template.message_type

    data_row = f"x,x,x,{message_type}"

    csvfile_filestorage = create_csv_file_for_submission(data_row)
    return csvfile_filestorage


@pytest.fixture
def csv_file_for_submission__missing_headers(
    member,
    care_advocate,
    care_advocate_2,
    farewell_transition_template,
    followup_intro_transition_template,
) -> FileStorage:

    message_type = (
        farewell_transition_template.message_type
        + ";"
        + followup_intro_transition_template.message_type
    )
    # With missing member_id
    headers_row = "old_cx_id,new_cx_id,messaging"
    data_row = f"{care_advocate.id},{care_advocate_2.id},{message_type}"

    csvfile_filestorage = create_csv_file_for_submission(
        data_row=data_row, headers_row=headers_row
    )
    return csvfile_filestorage


@pytest.fixture
def csv_file_for_submission__duplicate_member(
    member, member_2, care_advocate, care_advocate_2, farewell_transition_template
) -> FileStorage:

    message_type = farewell_transition_template.message_type
    data_rows = []
    data_rows.append(
        f"{member.id},{care_advocate.id},{care_advocate_2.id},{message_type}"
    )
    data_rows.append(
        f"{member_2.id},{care_advocate.id},{care_advocate_2.id},{message_type}"
    )
    data_rows.append(
        f"{member.id},{care_advocate.id},{care_advocate_2.id},{message_type}"
    )
    csvfile_filestorage = create_csv_file_for_submission_multiple_rows(data_rows)
    return csvfile_filestorage


@pytest.fixture
def csv_file_for_submission__invalid_message_types(
    member, care_advocate, care_advocate_2
) -> FileStorage:

    message_type = "AN_INVALID_MESSAGE_TYPE"
    data_row = f"{member.id},{care_advocate.id},{care_advocate_2.id},{message_type}"
    csvfile_filestorage = create_csv_file_for_submission(data_row)
    return csvfile_filestorage


@pytest.fixture
def csv_file_for_submission__no_transitions():
    csvfile_filestorage = create_csv_file_for_submission(data_row=None)
    return csvfile_filestorage


# We use `yield` here so that we remain in the patch context, `return` would exit it
@pytest.fixture
def mock_transition_log_repo_cls():
    with patch(
        "care_advocates.services.transition_log.CareAdvocateMemberTransitionLogRepository",
        autospec=True,
    ) as mock_repo_cls:
        yield mock_repo_cls


@pytest.fixture
def mock_transition_log_repo(mock_transition_log_repo_cls):
    return mock_transition_log_repo_cls.return_value


@pytest.fixture
def mock_transition_log_uow_cls(mock_transition_log_repo_cls, mock_transition_log_repo):
    with patch(
        "care_advocates.services.transition_log.SQLAlchemyUnitOfWork", autospec=True
    ) as mock_uow_cls:
        mock_uow_instance = mock_uow_cls.return_value
        mock_uow_instance.__enter__.return_value = mock_uow_instance
        mock_uow_instance.repositories = {
            mock_transition_log_repo_cls: mock_transition_log_repo
        }
        mock_uow_instance.get_repo.return_value = mock_transition_log_repo
        yield mock_uow_cls


# By having mock_transition_log_uow_cls as an argument, pytest will do the work of detecting and
# maintaining yielding fixture contexts for us. That way, when calling `CareAdvocateMemberTransitionLogService()`,
# the `CareAdvocateMemberTransitionLogRepository` class will be mocked
@pytest.fixture
def transition_log_service(
    mock_transition_log_uow_cls,
) -> CareAdvocateMemberTransitionLogService:
    return CareAdvocateMemberTransitionLogService()


@pytest.fixture
def mock_transition_template_repo_cls():
    with patch(
        "care_advocates.services.transition_template.CareAdvocateMemberTransitionTemplateRepository",
        autospec=True,
    ) as mock_repo_cls:
        yield mock_repo_cls


@pytest.fixture
def mock_transition_template_repo(mock_transition_template_repo_cls):
    return mock_transition_template_repo_cls.return_value


@pytest.fixture
def transition_template_service(
    mock_transition_template_repo_cls,
) -> CareAdvocateMemberTransitionTemplateService:
    return CareAdvocateMemberTransitionTemplateService()


@pytest.fixture
def care_advocate_service(session) -> CareAdvocateService:
    return CareAdvocateService()


@pytest.fixture
def assignable_advocate_repository(session) -> AssignableAdvocateRepository:
    return AssignableAdvocateRepository(session=session)


@pytest.fixture
def datetime_today():
    return datetime.datetime.utcnow()


@pytest.fixture()
def jan_1st_next_year():
    return datetime.datetime(datetime.datetime.now().year + 1, 1, 1)


@pytest.fixture
def assignable_advocate():
    prac = PractitionerUserFactory()
    aa = AssignableAdvocateFactory.create_with_practitioner(practitioner=prac)
    return aa


@pytest.fixture()
def module_adoption(factories):
    module_adoption = factories.WeeklyModuleFactory.create(name=TrackName.ADOPTION)
    return module_adoption


@pytest.fixture()
def module_parenting(factories):
    module_parenting = factories.WeeklyModuleFactory.create(
        name=TrackName.PARENTING_AND_PEDIATRICS
    )
    return module_parenting


@pytest.fixture()
def module_pregnancy(factories):
    module_pregnancy = factories.WeeklyModuleFactory.create(name=TrackName.PREGNANCY)
    return module_pregnancy


@pytest.fixture
def complete_matching_rule_set(
    assignable_advocate, module_adoption, module_parenting, module_pregnancy
):
    # In order to create copies of a complete matching rule set
    # Reference: https://stackoverflow.com/a/21590140
    class CompleteMatchingRuleSetFactory:
        def get(self, an_assignable_advocate=None, module=None):
            if an_assignable_advocate:
                mrs = MatchingRuleSetFactory(assignable_advocate=an_assignable_advocate)
            else:
                mrs = MatchingRuleSetFactory(assignable_advocate=assignable_advocate)

            track_mr = MatchingRuleFactory(
                type=MatchingRuleType.INCLUDE.value,
                entity=MatchingRuleEntityType.MODULE.value,
                matching_rule_set=mrs,
            )
            if module:
                track_mr.identifiers.append(str(module.id))
            else:
                track_mr.identifiers.append(str(module_adoption.id))
                track_mr.identifiers.append(str(module_parenting.id))
                track_mr.identifiers.append(str(module_pregnancy.id))

            MatchingRuleFactory(
                type=MatchingRuleType.INCLUDE.value,
                entity=MatchingRuleEntityType.COUNTRY.value,
                matching_rule_set=mrs,
                all=True,
            )

            MatchingRuleFactory(
                type=MatchingRuleType.INCLUDE.value,
                entity=MatchingRuleEntityType.ORGANIZATION.value,
                matching_rule_set=mrs,
                all=True,
            )

            MatchingRuleFactory(
                type=MatchingRuleType.INCLUDE.value,
                entity=MatchingRuleEntityType.USER_FLAG.value,
                matching_rule_set=mrs,
                all=True,
            )

            MatchingRuleFactory(
                type=MatchingRuleType.EXCLUDE.value,
                entity=MatchingRuleEntityType.USER_FLAG.value,
                matching_rule_set=mrs,
                all=True,
            )

            return mrs

    return CompleteMatchingRuleSetFactory()


@pytest.fixture()
def catch_all_prac_profile(factories, assignable_advocate, complete_matching_rule_set):

    complete_matching_rule_set.get(assignable_advocate)
    catch_all_prac_profile = assignable_advocate.practitioner

    return catch_all_prac_profile


@pytest.fixture
def mock_ca_validate_availability_flag(ff_test_data):
    def _mock(is_on: bool = True):
        ff_test_data.update(
            ff_test_data.flag("experiment-ca-validate-availability").variation_for_all(
                is_on
            )
        )

    return _mock
