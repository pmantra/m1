import datetime
from unittest import mock

import pytest

from authz.models.roles import ROLES
from authz.pytests.factories import (
    AuthzPermissionFactory,
    AuthzRoleFactory,
    AuthzRolePermissionFactory,
    AuthzUserRoleFactory,
)
from authz.utils.rbac_permissions import DELETE_GDPR_USER
from direct_payment.clinic.pytests.factories import FertilityClinicUserProfileFactory
from pytests import factories, freezegun

GDPR_INITIATOR_USER_ID = 363636


@pytest.fixture()
def mock_stats_incr():
    with mock.patch("common.stats.increment") as mock_stats_incr:
        yield mock_stats_incr


@pytest.fixture()
def mock_trace():
    with mock.patch("traceback.extract_stack") as mock_trace:
        yield mock_trace


@pytest.fixture()
def fertility_clinic_user():
    user = factories.DefaultUserFactory.create()
    FertilityClinicUserProfileFactory.create(user_id=user.id)
    fc_role = factories.RoleFactory.create(name=ROLES.fertility_clinic_user)
    factories.RoleProfileFactory.create(role=fc_role, user=user)

    return user


@pytest.fixture()
def frozen_now():
    now = datetime.datetime.utcnow().replace(microsecond=0).isoformat()
    with freezegun.freeze_time(now) as f:
        yield f


@pytest.fixture()
def gdpr_delete_permission():
    AuthzRoleFactory.create(id=1122334455, name="core-services")
    AuthzUserRoleFactory.create(user_id=GDPR_INITIATOR_USER_ID, role_id=1122334455)
    AuthzPermissionFactory.create(id=5544332211, name=DELETE_GDPR_USER)

    AuthzRolePermissionFactory.create(role_id=1122334455, permission_id=5544332211)
