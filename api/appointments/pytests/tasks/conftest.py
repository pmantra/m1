import pytest


@pytest.fixture
def availability_notification_req(factories, practitioner_user, enterprise_user):
    def make_availability_notification_req(request_dt):
        practitioner = practitioner_user()

        avail_req = factories.AvailabilityNotificationRequestFactory.create(
            member=enterprise_user,
            practitioner=practitioner,
            member_timezone="America/New_York",
            created_at=request_dt,
            modified_at=request_dt,
        )

        channel = factories.ChannelFactory.create(
            name=f"{enterprise_user.first_name}, {practitioner.first_name}"
        )
        channel_user_member = factories.ChannelUsersFactory.create(
            channel_id=channel.id,
            user_id=enterprise_user.id,
            channel=channel,
            user=enterprise_user,
        )
        channel_user_prac = factories.ChannelUsersFactory.create(
            channel_id=channel.id,
            user_id=practitioner.id,
            channel=channel,
            user=practitioner,
        )
        channel.participants = [channel_user_member, channel_user_prac]

        factories.MessageFactory.create(
            availability_notification_request_id=avail_req.id,
            body="",
            channel_id=channel.id,
            created_at=request_dt,
            modified_at=request_dt,
            status=1,
            user_id=avail_req.member.id,
        )

        return avail_req, channel

    return make_availability_notification_req
