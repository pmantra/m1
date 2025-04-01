import uuid
from datetime import timedelta
from unittest import mock

from authn.models.user import User
from models.tracks import TrackName, lifecycle

from .utils.gen_billables import generate_enrollment_id


def test_first_member_track(default_user, factories):
    org = factories.OrganizationFactory.create()
    client_track = factories.ClientTrackFactory.create(
        organization=org, track=TrackName.PREGNANCY
    )
    with mock.patch(
        "tracks.service.tracks.TrackSelectionService.validate_initiation",
        return_value=client_track,
    ):
        cur_mt = lifecycle.initiate(
            user=default_user,
            track=TrackName.PREGNANCY,
            eligibility_organization_id=org.id,
        )

        prev_pid = uuid.uuid1()
        old_enrollment_id = str(prev_pid)

        enrollment_id = generate_enrollment_id(
            cur_mt=cur_mt, mt_enrollment_mapping={}, prev_pid=prev_pid
        )

        # first member track, so should generate new enrollment_id
        assert enrollment_id != old_enrollment_id


def test_track_transition(default_user, factories):
    org = factories.OrganizationFactory.create()
    client_track_1 = factories.ClientTrackFactory.create(
        organization=org, track=TrackName.PREGNANCY
    )
    factories.ClientTrackFactory.create(organization=org, track=TrackName.FERTILITY)
    with mock.patch(
        "tracks.service.tracks.TrackSelectionService.validate_initiation",
        return_value=client_track_1,
    ):
        prev_mt = lifecycle.initiate(
            user=default_user,
            track=TrackName.PREGNANCY,
            eligibility_organization_id=org.id,
        )

        # force transition to "illegal" state
        cur_mt = lifecycle.transition(
            source=prev_mt, target=TrackName.FERTILITY, with_validation=False
        )

        prev_pid = uuid.uuid1()
        old_enrollment_id = str(prev_pid)
        enrollment_id = generate_enrollment_id(
            cur_mt=cur_mt, mt_enrollment_mapping={}, prev_mt=prev_mt, prev_pid=prev_pid
        )

    # invalid transition, thus should generate new enrollment id
    assert enrollment_id != old_enrollment_id


def test_track_early_renewal(default_user, factories):
    org = factories.OrganizationFactory.create()
    client_track_1 = factories.ClientTrackFactory.create(
        organization=org, track=TrackName.PREGNANCY
    )
    factories.ClientTrackFactory.create(organization=org, track=TrackName.PREGNANCYLOSS)
    with mock.patch(
        "tracks.service.tracks.TrackSelectionService.validate_initiation",
        return_value=client_track_1,
    ):
        prev_mt = lifecycle.initiate(
            user=default_user,
            track=TrackName.PREGNANCY,
            eligibility_organization_id=org.id,
        )
        cur_mt = lifecycle.transition(source=prev_mt, target=TrackName.PREGNANCYLOSS)
        cur_mt.activated_at = cur_mt.created_at + timedelta(days=10)

        prev_pid = uuid.uuid1()
        old_enrollment_id = str(prev_pid)
        enrollment_id = generate_enrollment_id(
            cur_mt=cur_mt, mt_enrollment_mapping={}, prev_mt=prev_mt, prev_pid=prev_pid
        )

        # early renewal, so should generate new enrollment_id
        assert enrollment_id != old_enrollment_id


def test_track_overlap(default_user, factories):
    org = factories.OrganizationFactory.create()
    client_track_1 = factories.ClientTrackFactory.create(
        organization=org, track=TrackName.PREGNANCY
    )
    factories.ClientTrackFactory.create(organization=org, track=TrackName.PREGNANCYLOSS)
    with mock.patch(
        "tracks.service.tracks.TrackSelectionService.validate_initiation",
        return_value=client_track_1,
    ):
        prev_mt = lifecycle.initiate(
            user=default_user,
            track=TrackName.PREGNANCY,
            eligibility_organization_id=org.id,
        )
        prev_mt.created_at = prev_mt.created_at - timedelta(days=1)
        prev_mt.activated_at = prev_mt.activated_at - timedelta(days=1)

        cur_mt = lifecycle.transition(source=prev_mt, target=TrackName.PREGNANCYLOSS)

        prev_pid = uuid.uuid1()
        old_enrollment_id = str(prev_pid)
        enrollment_id = generate_enrollment_id(
            cur_mt=cur_mt, mt_enrollment_mapping={}, prev_mt=prev_mt, prev_pid=prev_pid
        )

        # overlap, should use earlier enrollment_id
        assert enrollment_id == old_enrollment_id


def test_track_already_associated(default_user, factories):
    org = factories.OrganizationFactory.create()
    client_track_1 = factories.ClientTrackFactory.create(
        organization=org, track=TrackName.PREGNANCY
    )
    with mock.patch(
        "tracks.service.tracks.TrackSelectionService.validate_initiation",
        return_value=client_track_1,
    ):
        cur_mt = lifecycle.initiate(
            user=default_user,
            track=TrackName.PREGNANCY,
            eligibility_organization_id=org.id,
        )

        prev_pid = uuid.uuid1()
        enrollment_id = generate_enrollment_id(
            cur_mt=cur_mt, mt_enrollment_mapping={cur_mt.id: "test"}, prev_pid=prev_pid
        )

        # track already has enrollment_id, so recycle it
        assert enrollment_id == "test"


def test_track_family_happy(default_user, factories):
    org = factories.OrganizationFactory.create()
    # User tracks
    client_track_1 = factories.ClientTrackFactory.create(
        organization=org, track=TrackName.PREGNANCY
    )
    with mock.patch(
        "tracks.service.tracks.TrackSelectionService.validate_initiation",
        return_value=client_track_1,
    ):
        cur_mt = lifecycle.initiate(
            user=default_user,
            track=TrackName.PREGNANCY,
            eligibility_organization_id=org.id,
        )

        # Family tracks
        family_user: User = factories.DefaultUserFactory.create()
        other_org = factories.OrganizationFactory.create()
        client_track_2 = factories.ClientTrackFactory.create(
            organization=other_org, track=TrackName.PREGNANCY
        )
        factories.ClientTrackFactory.create(
            organization=other_org, track=TrackName.PREGNANCYLOSS
        )

        with mock.patch(
            "tracks.service.tracks.TrackSelectionService.validate_initiation",
            return_value=client_track_2,
        ):
            fam_prev_mt = lifecycle.initiate(
                user=family_user,
                track=TrackName.PREGNANCY,
                eligibility_organization_id=other_org.id,
            )
            fam_prev_mt.created_at = fam_prev_mt.created_at - timedelta(days=1)
            fam_prev_mt.activated_at = fam_prev_mt.activated_at - timedelta(days=1)

            fam_cur_mt = lifecycle.transition(
                source=fam_prev_mt, target=TrackName.PREGNANCYLOSS
            )

            prev_pid = uuid.uuid1()
            enrollment_id = generate_enrollment_id(
                cur_mt=cur_mt,
                mt_enrollment_mapping={fam_prev_mt.id: "test1", fam_cur_mt.id: "test2"},
                family_mts=[fam_prev_mt, fam_cur_mt],
                prev_pid=prev_pid,
            )

            # value should be the first enrollment_id in family tracks
            assert enrollment_id == "test1"
