import csv
from io import BytesIO, StringIO

import pytest as pytest

from admin.blueprints.rbac import validate_row_format


class AuthzRBACBulkInsert:
    def test_bulk_insert__authz(self, admin_client):
        # Given - csv file
        csv_data = {
            "authz_role": [
                ["name", "description"],
                ["authz-role", "role for permissions"],
                ["test-team", "role for test team"],
            ],
            "authz_permission": [
                ["name", "description"],
                ["read:authz", "read authz permissions"],
                ["write:authz", "write authz permissions"],
            ],
            "authz_role_permission": [
                ["role_name", "permission_name"],
                ["authz-role", "read:authz"],
                ["authz-role", "write:authz"],
            ],
            "authz_user_role": [
                ["role_name", "user_email"],
                ["authz-role", "test+staff@mavenclinic.com"],
                ["test-team", "test+staff@mavenclinic.com"],
            ],
        }

        for table, csv_datum in csv_data.items():
            csv_stream = StringIO()
            csv.writer(csv_stream).writerows(csv_datum)
            csv_encoded = csv_stream.getvalue().encode("utf-8")
            csv_file = (BytesIO(csv_encoded), f"{table}.csv")

            # When - we submit to the endpoint

            res = admin_client.post(
                "/admin/rbac/bulk_insert",
                data={
                    "table": table,
                    f"{table}_csv": csv_file,
                },
                headers={"Content-Type": "multipart/form-data"},
                follow_redirects=True,
            )

            # Then - expected invalid response
            assert res.status_code == 200


@pytest.mark.parametrize(
    argnames="table_name,rows,good_row_count,bad_row_count",
    argvalues=[
        (
            "authz_permission",
            [
                {"name": "verb:object", "description": "should pass"},
                {
                    "name": "two-verbs:objects-separated-by-dash",
                    "description": "should pass",
                },
                {"name": "verb:object1", "description": "should fail due to number"},
                {
                    "name": "two-verbs:",
                    "description": "should fail, nothing after colon",
                },
                {"name": ":", "description": "should fail, no at least need one word"},
                {"name": "verb:unexpected-charter$", "description": "should fail"},
            ],
            2,
            4,
        ),
        (
            "authz_role",
            [
                {"name": "object", "description": "should pass"},
                {"name": "two-nouns", "description": "should pass"},
                {"name": "two-nouns", "description": "should pass"},
                {"name": "nouns-bad-character%:", "description": "should fail"},
                {"name": "one1", "description": "should fail due to number"},
                {"name": "", "description": "should fail"},
            ],
            3,
            3,
        ),
        (
            "authz_user_role",
            [
                {"role_name": "object", "user_email": "thisshoud@pass.com"},
                {"role_name": "two-nouns", "user_email": "should fail"},
                {"role_name": "one1", "user_email": "thisshoud@fail.com"},
                {"role_name": "", "user_email": "thisshoud@fail.com"},
                {"role_name": "", "user_email": ""},
            ],
            1,
            4,
        ),
        (
            "authz_role_permission",
            [
                {"role_name": "object", "permission_name": "verb:object"},
                {
                    "role_name": "two-nouns",
                    "permission_name": "two-verbs:objects-separated-by-dash",
                },
                {"role_name": "two-nouns", "permission_name": "fail:"},
                {
                    "role_name": "nouns-bad-character%:",
                    "permission_name": "should:fail",
                },
                {"role_name": "one", "permission_name": "permission:!"},
                {"role_name": "one1", "permission_name": "verb:1"},
                {"role_name": "", "permission_name": ""},
            ],
            2,
            5,
        ),
    ],
    ids=[
        "authz_permission",
        "authz_role",
        "authz_user_role",
        "authz_role_permission",
    ],
)
def test_validate_row_format(table_name, rows, good_row_count, bad_row_count):
    bad_format_rows, good_rows = validate_row_format(table_name, rows)
    assert len(bad_format_rows) == bad_row_count
    assert len(good_rows) == good_row_count
