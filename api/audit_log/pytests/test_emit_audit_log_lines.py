from unittest import TestCase, mock

from sqlalchemy import Column, Integer, String

from audit_log.utils import (
    ActionType,
    emit_audit_log_line,
    emit_bulk_audit_log_create,
    emit_bulk_audit_log_delete,
    emit_bulk_audit_log_read,
    emit_bulk_audit_log_update,
)
from models import base
from pytests.factories import DefaultUserFactory, VerticalFactory


class TestEmitAuditLogLines(TestCase):

    # We'll use this fake class for testing UPDATE/DELETE cases, so that we can control the
    # full list of fields in a way that will be future-proof. For the UPDATE case, we'll
    # unfortunately need to use an object that's actually persisted to the DB, otherwise
    # we'll have no way of differentiating changed from unchanged fields (because
    # before an object is committed to the DB, *ALL* fields look changed).
    class TestAuditableObject(base.ModelBase):
        __tablename__ = "test_auditable_object"

        id = Column(Integer, primary_key=True)
        name = Column(String)
        volume = Column(Integer)

        def __str__(self):
            return self.name

    def setUp(self):
        self.user = DefaultUserFactory(
            id=123,
            first_name="Jason",
            last_name="Statham",
        )

        self.basic_object_args = {
            "id": 1,
            "name": "Test Object",
            "volume": 11,
        }
        self.basic_object = self.TestAuditableObject(**self.basic_object_args)

        self.basic_object_args_2 = {
            "id": 2,
            "name": "Test Object 2",
            "volume": 22,
        }
        self.basic_object_2 = self.TestAuditableObject(**self.basic_object_args_2)

        self.vertical_object_args = {
            "name": "Prenatal Math Tutoring",
            "description": "Teach that baby some differential equations",
            "filter_by_state": False,
        }
        self.vertical = VerticalFactory(**self.vertical_object_args)

    @mock.patch("audit_log.utils._emit_audit_log_line_from_audit_log_info")
    def test_emit_audit_log_line__object_created__all_initial_arguments_captured(
        self, emit_audit_log_patch
    ):
        emit_audit_log_line(
            self.user,
            ActionType.CREATE,
            self.basic_object,
        )

        expected_args = {
            "user_id": self.user.id,
            "action_type": ActionType.CREATE.value,
            "action_target_type": self.TestAuditableObject.__table__.name,
            "action_target_id": str(self.basic_object.id),
            "json_details": self.basic_object_args,
            "action_target_display_name": str(self.basic_object),
            "user_full_name": self.user.full_name,
        }

        call_args = emit_audit_log_patch.call_args.args[0]

        for (arg_name, arg_value) in call_args.items():
            self.assertEqual(
                arg_value,
                expected_args.get(arg_name),
            )

    @mock.patch("audit_log.utils._emit_audit_log_line_from_audit_log_info")
    def test_emit_audit_log_line__object_deleted__all_field_values_captured(
        self, emit_audit_log_patch
    ):
        emit_audit_log_line(
            self.user,
            ActionType.DELETE,
            self.basic_object,
        )

        expected_args = {
            "user_id": self.user.id,
            "action_type": ActionType.DELETE.value,
            "action_target_type": self.TestAuditableObject.__table__.name,
            "action_target_id": str(self.basic_object.id),
            "json_details": self.basic_object_args,
            "action_target_display_name": str(self.basic_object),
            "user_full_name": self.user.full_name,
        }

        call_args = emit_audit_log_patch.call_args.args[0]

        for (arg_name, arg_value) in call_args.items():
            self.assertEqual(
                arg_value,
                expected_args.get(arg_name),
            )

    @mock.patch("audit_log.utils._emit_audit_log_line_from_audit_log_info")
    def test_emit_audit_log_line__object_updated__only_modified_args_captured(
        self, emit_audit_log_patch
    ):
        new_name = "Prenatal Physics Tutoring"
        self.vertical.name = new_name

        new_description = "Teach that baby all about kinematics"
        self.vertical.description = new_description

        new_filter_by_state = True
        self.vertical.filter_by_state = new_filter_by_state

        emit_audit_log_line(
            self.user,
            ActionType.UPDATE,
            self.vertical,
        )

        expected_args = {
            "user_id": self.user.id,
            "action_type": ActionType.UPDATE.value,
            "action_target_type": self.vertical.__table__.name,
            "action_target_id": str(self.vertical.id),
            "json_details": {
                "name": {
                    "old_value": self.vertical_object_args["name"],
                    "new_value": new_name,
                },
                "description": {
                    "old_value": self.vertical_object_args["description"],
                    "new_value": new_description,
                },
                "filter_by_state": {
                    "old_value": str(self.vertical_object_args["filter_by_state"]),
                    "new_value": str(new_filter_by_state),
                },
            },
            "action_target_display_name": str(self.vertical),
            "user_full_name": self.user.full_name,
        }

        call_args = emit_audit_log_patch.call_args.args[0]

        for (arg_name, arg_value) in call_args.items():
            self.assertEqual(
                arg_value,
                expected_args.get(arg_name),
            )

    @mock.patch("audit_log.utils.emit_audit_log_line", return_value=None)
    def test_emit_bulk_audit_log_create(self, emit_audit_log_line_patch):
        with mock.patch("flask_login.current_user", self.user):
            # Check for 2 valid function calls inside the 1
            instances = [self.basic_object, self.basic_object_2]
            emit_bulk_audit_log_create(instances)
            calls = [
                mock.call(self.user, ActionType.CREATE, instances[0]),
                mock.call(self.user, ActionType.CREATE, instances[1]),
            ]
            emit_audit_log_line_patch.assert_has_calls(calls)
            self.assertEqual(emit_audit_log_line_patch.call_count, 2)

    @mock.patch("audit_log.utils.emit_audit_log_line", return_value=None)
    def test_emit_bulk_audit_log_read(self, emit_audit_log_line_patch):
        with mock.patch("flask_login.current_user", self.user):
            # Check for 2 valid function calls inside the 1
            instances = [self.basic_object, self.basic_object_2]
            emit_bulk_audit_log_read(instances)
            calls = [
                mock.call(self.user, ActionType.READ, instances[0]),
                mock.call(self.user, ActionType.READ, instances[1]),
            ]
            emit_audit_log_line_patch.assert_has_calls(calls)
            self.assertEqual(emit_audit_log_line_patch.call_count, 2)

    @mock.patch("audit_log.utils.emit_audit_log_line", return_value=None)
    def test_emit_bulk_audit_log_update(self, emit_audit_log_line_patch):
        with mock.patch("flask_login.current_user", self.user):
            # Check for 2 valid function calls inside the 1
            instances = [self.basic_object, self.basic_object_2]
            emit_bulk_audit_log_update(instances)
            calls = [
                mock.call(self.user, ActionType.UPDATE, instances[0]),
                mock.call(self.user, ActionType.UPDATE, instances[1]),
            ]
            emit_audit_log_line_patch.assert_has_calls(calls)
            self.assertEqual(emit_audit_log_line_patch.call_count, 2)

    @mock.patch("audit_log.utils.emit_audit_log_line", return_value=None)
    def test_emit_bulk_audit_log_delete(self, emit_audit_log_line_patch):
        with mock.patch("flask_login.current_user", self.user):
            # Check for 2 valid function calls inside the 1
            instances = [self.basic_object, self.basic_object_2]
            emit_bulk_audit_log_delete(instances)
            calls = [
                mock.call(self.user, ActionType.DELETE, instances[0]),
                mock.call(self.user, ActionType.DELETE, instances[1]),
            ]
            emit_audit_log_line_patch.assert_has_calls(calls)
            self.assertEqual(emit_audit_log_line_patch.call_count, 2)
