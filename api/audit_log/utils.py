from enum import Enum
from typing import Optional

import flask_login as login
import inflection

from storage.connection import db
from utils.log import logger

log = logger(__name__)


class ActionType(Enum):
    CREATE = "CREATE"
    READ = "READ"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"


# Create - Log after the commit (needs the record id)
def emit_audit_log_create(instance):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    emit_audit_log_line(login.current_user, ActionType.CREATE, instance)


def emit_bulk_audit_log_create(instances: list):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    for instance in instances:
        emit_audit_log_create(instance)


# Read
def emit_audit_log_read(instance):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    emit_audit_log_line(login.current_user, ActionType.READ, instance)


def emit_bulk_audit_log_read(instances: list):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    for instance in instances:
        emit_audit_log_read(instance)


# Update - Log before the commit
def emit_audit_log_update(instance):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    emit_audit_log_line(login.current_user, ActionType.UPDATE, instance)


def emit_bulk_audit_log_update(instances: list):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    for instance in instances:
        emit_audit_log_update(instance)


# Delete - Log after the commit
def emit_audit_log_delete(instance):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    emit_audit_log_line(login.current_user, ActionType.DELETE, instance)


def emit_bulk_audit_log_delete(instances: list):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    for instance in instances:
        emit_audit_log_line(login.current_user, ActionType.DELETE, instance)


# Login - Log after login
def emit_audit_log_login(instance):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    emit_audit_log_line(login.current_user, ActionType.LOGIN, instance)


# Logout - Log before logout
def emit_audit_log_logout(instance):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    emit_audit_log_line(login.current_user, ActionType.LOGOUT, instance)


def emit_audit_log_line(user, action_type, instance, is_inline: bool = False):  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    user_id = user.id
    if hasattr(instance, "__table__"):
        action_target_type = instance.__table__.name
    # not sqlalchemy models like UserExternalIdentity do not have a __table__ attribute
    # their table name is declared in BaseRepository::table_name()
    else:
        action_target_type = inflection.underscore(instance.__class__.__name__)

    action_target_id = _get_instance_id_string(instance)

    audit_log_info = {
        "user_id": user_id,
        "action_type": action_type.value,
        "action_target_type": action_target_type,
        "action_target_id": action_target_id,
        "is_inline": is_inline,
    }

    if (
        action_type == ActionType.UPDATE
    ):  # If we ever wanted to save object's field values for CREATE, we would need to include ActionType.CREATE in this if statement
        modified_fields = _get_modified_fields(
            instance,
            action_type,
        )
        audit_log_info["modified_fields"] = modified_fields

    _emit_audit_log_line_from_audit_log_info(audit_log_info)


def _emit_audit_log_line_from_audit_log_info(audit_log_info):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    log.info(
        "audit_log_events",
        audit_log_info=audit_log_info,
    )


def _get_instance_id_string(instance):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    # This may seem overly complicated (i.e. "Why don't we just return instance.id?"), but it handles 2 important cases:
    #
    # 1. The instance's model uses a field other than `id` for its primary key
    # 2. The instance's model uses a composite primary key based on 2 or more fields
    #
    # We use the table's primary key definition to extract these values, and in the case of a composite primary key
    # we write that list of primary key values in the same manner that we could use to query back that individual entry.
    #
    # E.g. If CompositeModel has primary keys A and B, and the instances is {A: 123, B: 789}, we'd output the ID string
    #      as [123, 789], since we'd be able to get this entry by calling CompositeModel.query.get([123, 789])
    # This all applies to sqlalchemy models. For non sqlalchemy models (those without a __table__ attribute, like UserExternalIdentity), we will just use instance.id
    if hasattr(instance, "__table__"):
        primary_key_columns = list(instance.__table__.primary_key.columns)
        if len(primary_key_columns) == 1:
            return str(getattr(instance, primary_key_columns[0].name))
        else:
            return str(
                [getattr(instance, column.name) for column in primary_key_columns]
            )
    elif hasattr(instance, "__mapper__"):
        return str(getattr(instance, instance.__mapper__.primary_key[0].name))
    else:
        return str(instance.id)


def _get_instance_display_name(instance):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    # This could be overwritten (by means of an override mapping) for any types
    # that want to specify their display name as something other than str(type)
    return str(instance)


def _get_modified_fields(instance, action_type):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if action_type == ActionType.UPDATE:
        return _get_modified_field_values_map(instance)
    else:  # For now we will never enter this section, given that we only call _get_modified_fields if action_type is UPDATE. Nonetheless, leaving this for prosperity as we may want to save updated fields for CREATE in the future
        return _get_field_values_map(instance)


def _get_field_values_map(instance):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """
    We are not using this function for now. It should be invoked in the future if we would like to keep field value maps for new objects created.
    """
    values_map = {}

    model_info = db.inspect(instance)
    column_names = [attr.key for attr in db.inspect(instance).attrs]
    model_data_map = model_info.dict

    for (key, value) in model_data_map.items():
        # We want to check that this is a column that actually exists on the model, since `db.insepct(instance).dict
        # can contain some extra non-column fields about current state.
        if key in column_names:
            values_map[key] = value

    return values_map


def _get_modified_field_values_map(model_instance):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    modified_fields = set()
    # values_map = {}, remove comment is enabling saving value updates

    # Technically db.inspect(model) also includes a field `unmodified` that is a list of "unmodified" fields, but that
    # won't include fields that we've changed locally (e.g. attaching an attribute to a model instance, when that
    # attribute doesn't exist in the DB). As such, we can't just take a look at the fields that AREN'T in `unmodified`,
    # and instead we need to take a look at the history of our current db transaction to manually pull out the
    # fields that have changed by looking in db.inspect(model).attrs
    #
    # NOTE: Despite the names `added` and `deleted`, these will actually be represented when a field is updated.
    #       If a model Fruit has its field `foo` updated from `123` to `456`, we will see:
    #           attr.history.added = 456
    #           attr.history.deleted = 123
    # NOTE: For many flask-admin models, a json field gets automatically updated when changes to other fields occurr. Hence, do not be surprised if the json field gets unexpectly reported in the modified_fields
    model_info = db.inspect(model_instance)
    for attr in model_info.attrs:
        if attr.history.added or attr.history.deleted:
            modified_fields.add(attr.key)
            # Leaving how to save updated values here for posterity, in case we want to save those values in the future
            # values_map[attr.key] = {
            #     "old_value": _get_instance_display_name(
            #         model_info.committed_state[attr.key]
            #     ),
            #     "new_value": _get_instance_display_name(model_info.dict[attr.key]),
            # }

    return list(modified_fields)


def get_modified_field_value(model_instance, field_name):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    model_info = db.inspect(model_instance)
    for attr in model_info.attrs:
        if attr.key == field_name:
            return attr.value


def get_flask_admin_user() -> Optional[login.current_user]:
    """
    Checks if login.current_user has login_manager and then returns the current_user if available.
    Used in functions that are triggered via Admin and RQ jobs.

    Should return None in RQ job contexts. Otherwise will return current_user in flask admin context.
    """
    has_login_manager = hasattr(login.current_user, "login_manager")
    admin_user = None
    if has_login_manager:
        admin_user = login.current_user
    return admin_user
