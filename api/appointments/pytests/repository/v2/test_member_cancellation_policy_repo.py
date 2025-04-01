from appointments.repository.v2.cancel_appointment import (
    MemberCancellationPolicyRepository,
)
from pytests import factories
from storage.connection import db


class TestMemberCancellationPolicyRepository:
    def test_get_cancellation_policy_struct(self):
        practitioner = factories.PractitionerUserFactory.create()
        cancellation_policy = practitioner.practitioner_profile.cancellation_policy
        vertical = factories.VerticalFactory.create(products=None)
        product = factories.ProductFactory(
            user_id=practitioner.id,
            vertical=vertical,
            minutes=30,
            price=2.0,
        )

        result = MemberCancellationPolicyRepository(
            db.session
        ).get_cancellation_policy_struct(product_id=product.id)

        assert result.id == cancellation_policy.id
        assert result.name == cancellation_policy.name
        assert result.refund_0_hours == cancellation_policy.refund_0_hours
        assert result.refund_2_hours == cancellation_policy.refund_2_hours
        assert result.refund_6_hours == cancellation_policy.refund_6_hours
        assert result.refund_12_hours == cancellation_policy.refund_12_hours
        assert result.refund_24_hours == cancellation_policy.refund_24_hours
        assert result.refund_48_hours == cancellation_policy.refund_48_hours
