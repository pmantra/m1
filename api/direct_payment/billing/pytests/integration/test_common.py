import pytest
from httpproblem import Problem

from direct_payment.billing.http.common import BillResourceMixin


class TestAuthByBill:
    def test_member_bill_access_fails(self, session, default_user, new_bill):
        with pytest.raises(Problem):
            BillResourceMixin()._user_has_access_to_bill_or_403(
                accessing_user=default_user, bill=new_bill, session=session
            )

    def test_member_bill_is_wallet_user(self, session, bill_user, new_bill):
        try:
            BillResourceMixin()._user_has_access_to_bill_or_403(
                accessing_user=bill_user, bill=new_bill, session=session
            )
        except Problem:
            assert (  # noqa  B011  TODO:  Do not call assert False since python -O removes these calls. Instead callers should raise AssertionError().
                False
            ), "Raised unexpected HTTPProblem"

    def test_member_bill_is_care_coordinator(self, session, ops_user, new_bill):
        try:
            BillResourceMixin()._user_has_access_to_bill_or_403(
                accessing_user=ops_user, bill=new_bill, session=session
            )
        except Problem:
            assert (  # noqa  B011  TODO:  Do not call assert False since python -O removes these calls. Instead callers should raise AssertionError().
                False
            ), "Raised unexpected HTTPProblem"  # noqa  B011  TODO:  Do not call assert False since python -O removes these calls. Instead callers should raise AssertionError().

    def test_non_member_bill_is_care_coordinator(
        self, session, ops_user, employer_bill
    ):
        try:
            BillResourceMixin()._user_has_access_to_bill_or_403(
                accessing_user=ops_user, bill=employer_bill, session=session
            )
        except Problem:
            assert (  # noqa  B011  TODO:  Do not call assert False since python -O removes these calls. Instead callers should raise AssertionError().
                False
            ), "Raised unexpected HTTPProblem"

    def test_non_member_bill_is_not_care_coordinator(
        self, session, bill_user, employer_bill
    ):
        with pytest.raises(Problem):
            BillResourceMixin()._user_has_access_to_bill_or_403(
                accessing_user=bill_user, bill=employer_bill, session=session
            )
