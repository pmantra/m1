import csv
import io
import re

import flask_login as login
from flask import Blueprint, flash, redirect, request
from sqlalchemy.dialects.mysql import insert
from sqlalchemy.exc import IntegrityError

from authn.models.user import User
from authz.models.rbac import (
    AuthzPermission,
    AuthzRole,
    AuthzRolePermission,
    AuthzUserRole,
)
from storage.connection import db
from utils.log import logger

URL_PREFIX = "rbac"

log = logger(__name__)
rbac = Blueprint(URL_PREFIX, __name__)

RBAC_TABLES = {
    "authz_role": AuthzRole,
    "authz_role_permission": AuthzRolePermission,
    "authz_permission": AuthzPermission,
    "authz_user_role": AuthzUserRole,
}

TABLE_UNIQUE_COLUMNS = {
    "authz_role": ["name"],
    "authz_role_permission": ["role_name", "permission_name"],
    "authz_permission": ["name"],
    "authz_user_role": ["role_name", "user_email"],
}

VALIDATION_RULES = {
    "authz_role": {"name": r"^[a-z]+(-[a-z]+)*$"},
    "authz_role_permission": {
        "role_name": r"^[a-z]+(-[a-z]+)*$",
        "permission_name": r"^[a-z]+(-[a-z]+)*:[a-z]+(-[a-z]+)*$",
    },
    "authz_permission": {"name": r"^[a-z]+(-[a-z]+)*:[a-z]+(-[a-z]+)*$"},
    "authz_user_role": {
        "role_name": "^[a-z]+(-[a-z]+)*$",
        "user_email": r"^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$",
    },
}


def validate_row_format(table_name: str, rows: list) -> tuple[list, list]:
    validation_rules = VALIDATION_RULES[table_name]
    bad_format_rows = []
    good_rows = []
    for row in rows:
        has_format_issue = False
        for column_name, value in row.items():
            if column_name in validation_rules:
                regex = validation_rules[column_name]
                if not re.match(regex, value):
                    has_format_issue = True
        if has_format_issue:
            bad_format_rows.append(row)
        else:
            good_rows.append(row)

    return bad_format_rows, good_rows


def insert_rows_handle_duplicates(table_name: str, rows: list) -> tuple[dict, int]:
    successful_rows = []
    duplicate_rows = []
    error_rows: list[dict] = []
    table = RBAC_TABLES[table_name]
    for row in rows:
        try:
            #  if the operation in nested block succeeds it is committed otherwise it rolls back
            # to last committed transaction, in this case it will roll back just one row.
            with db.session.begin_nested():
                db.session.execute(insert(table).values(**row))
            db.session.commit()
            successful_rows.append(row)
        except IntegrityError:
            db.session.rollback()
            duplicate_rows.append(row)
        except Exception as e:
            db.session.rollback()
            error_rows.append({"data": row, "error": str(e)})

    if duplicate_rows or error_rows:
        return (
            {
                "message": "Some data were not inserted due to duplicates.",
                "duplicate_rows": duplicate_rows,
                "errors": error_rows,
            },
            200 if successful_rows else 400,
        )
    else:
        return {"message": "Data uploaded successfully."}, 200


def update_rows_with_ids(table_name: str, rows: list) -> tuple[list[dict], list[dict]]:
    updated_rows: list[dict] = []
    missing_row_data: list[dict] = []
    role_names = set()
    permission_names = set()
    user_emails = set()
    if table_name == "authz_role_permission":
        for row in rows:
            role_names.add(row["role_name"])
            permission_names.add(row["permission_name"])

        role_name_to_id = {
            role.name: role.id
            for role in db.session.query(AuthzRole)
            .filter(AuthzRole.name.in_(role_names))
            .all()
        }
        permission_name_to_id = {
            permission.name: permission.id
            for permission in db.session.query(AuthzPermission)
            .filter(AuthzPermission.name.in_(permission_names))
            .all()
        }

        for row in rows:
            role_id = role_name_to_id.get(row["role_name"], None)
            permission_id = permission_name_to_id.get(row["permission_name"], None)
            if role_id and permission_id:
                updated_rows.append(
                    {"role_id": role_id, "permission_id": permission_id}
                )
            elif not role_id and not permission_id:
                missing_row_data.append(
                    {"data": row, "error": "role and permission not found."}
                )
            elif not role_id:
                missing_row_data.append({"data": row, "error": "role not found."})
            else:
                missing_row_data.append({"data": row, "error": "permission not found."})

    if table_name == "authz_user_role":
        for row in rows:
            role_names.add(row["role_name"])
            user_emails.add(row["user_email"])

        role_name_to_id = {
            role.name: role.id
            for role in db.session.query(AuthzRole)
            .filter(AuthzRole.name.in_(role_names))
            .all()
        }
        user_email_to_id = {
            user.email: user.id
            for user in db.session.query(User).filter(User.email.in_(user_emails)).all()
        }

        for row in rows:
            role_id = role_name_to_id.get(row["role_name"], None)
            user_id = user_email_to_id.get(row["user_email"], None)
            if role_id and user_id:
                updated_rows.append({"role_id": role_id, "user_id": user_id})
            elif not role_id and not user_id:
                missing_row_data.append(
                    {"data": row, "error": "role and user not found."}
                )
            elif not role_id:
                missing_row_data.append({"data": row, "error": "role not found."})
            else:
                missing_row_data.append({"data": row, "error": "user not found."})

    return updated_rows, missing_row_data


@rbac.route("/bulk_insert", methods=["POST"])
@login.login_required
def authz_role_bulk_insert():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    table_name = request.form.get("table")
    if table_name not in RBAC_TABLES:
        flash("Invalid Table name", category="error")
        return redirect("/admin/authz_bulk_insert")

    file_name = f"{table_name}_csv"
    if file_name not in request.files:
        flash("Please upload a file.")
        return redirect("/admin/authz_bulk_insert")

    csv_file = request.files[file_name]
    csv_string = csv_file.read().decode("utf-8")

    with io.StringIO(csv_string) as stream:
        reader = csv.DictReader(stream)
        rows = [r for r in reader]

    if not rows:
        flash("csv is empty")
        return redirect("/admin/authz_bulk_insert")

    if len(rows) > 250:
        flash("Too Many rows please upload a file with less than 250 rows.")
        return redirect("/admin/authz_bulk_insert")

    if table_name in ["authz_user_role", "authz_role_permission"]:
        # reassign the row columns with ids.
        rows, missing_row_data = update_rows_with_ids(table_name, rows)
        if missing_row_data:
            flash(missing_row_data, category="warning")

    bad_format_rows, good_rows = validate_row_format(table_name, rows)
    flash(
        f"These rows have bad format, they will be not inserted. {bad_format_rows}",
        category="warning",
    )

    if not good_rows:
        return redirect("/admin/authz_bulk_insert")

    message_dict, code = insert_rows_handle_duplicates(table_name, good_rows)
    message = message_dict["message"]
    del message_dict["message"]
    message += str(message_dict) if message_dict else ""
    category = "message"
    if code >= 400:
        category = "Error"

    flash(message, category=category)
    return redirect("/admin/authz_bulk_insert")
