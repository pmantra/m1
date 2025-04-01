import pytest

from admin.blueprints import enterprise
from eligibility.pytests import factories as e9y_factories


class TestFindMatchingVerificationData:
    def test_when_verification_data_empty(self):
        with pytest.raises(
            enterprise.ManualVerificationError,
            match="No verifications found for user_id=1.",
        ):
            enterprise._find_matching_verification_data(
                user_id=1, verification_data=[], organization_id=None
            )

    @pytest.mark.parametrize(
        "organization_id",
        [None, 100],
    )
    def test_when_only_1_verification(self, organization_id):
        verification = e9y_factories.VerificationFactory.create()
        res = enterprise._find_matching_verification_data(
            user_id=1,
            verification_data=[verification],
            organization_id=organization_id,
        )
        assert res == verification

    def test_when_multiple_verificaitons_but_no_org_id(self):
        verification1 = e9y_factories.VerificationFactory.create(
            organization_id=100,
        )
        verification2 = e9y_factories.VerificationFactory.create(
            organization_id=101,
        )
        with pytest.raises(
            enterprise.ManualVerificationError,
            match="Multiple verifications found for user_id=1, please specify organization id.",
        ):
            enterprise._find_matching_verification_data(
                user_id=1,
                verification_data=[verification1, verification2],
                organization_id=None,
            )

    def test_when_multiple_verificaitons_with_match_org_id(self):
        verification1 = e9y_factories.VerificationFactory.create(
            organization_id=100,
        )
        verification2 = e9y_factories.VerificationFactory.create(
            organization_id=101,
        )
        res = enterprise._find_matching_verification_data(
            user_id=1,
            verification_data=[verification1, verification2],
            organization_id=101,
        )
        assert res == verification2

    def test_when_multiple_verificaitons_with_non_match_org_id(self):
        verification1 = e9y_factories.VerificationFactory.create(
            organization_id=100,
        )
        verification2 = e9y_factories.VerificationFactory.create(
            organization_id=101,
        )
        with pytest.raises(
            enterprise.ManualVerificationError,
            match="No matching verification found for user_id=1, organization_id=108.",
        ):
            enterprise._find_matching_verification_data(
                user_id=1,
                verification_data=[verification1, verification2],
                organization_id=108,
            )
