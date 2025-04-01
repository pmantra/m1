import uuid
from unittest import mock

import pytest
from maven import feature_flags

from direct_payment.billing.pytests import factories as billing_factories


@pytest.fixture
def ff_test_data():
    with feature_flags.test_data() as td:
        yield td


class TestPaymentDetail:
    def test_payments_detail_bill_not_found(self, client, api_helpers, bill_user):
        res = client.get(
            f"/api/v1/direct_payment/payments/bill/{uuid.uuid4()}/detail",
            headers=api_helpers.json_headers(user=bill_user),
        )
        assert res.status_code == 404

    @pytest.mark.skip(
        "Getting a 404 instead of expected behavior due to use of abort in procedure repo."
    )
    def test_payments_detail_missing_information(
        self, client, api_helpers, bill_user, billing_service
    ):
        # bill without procedure or cost breakdown information
        bill = billing_service.bill_repo.create(
            instance=billing_factories.BillFactory.build()
        )
        with mock.patch(
            "direct_payment.billing.http.common.BillResourceMixin._user_has_access_to_bill_or_403"
        ):
            res = client.get(
                f"/api/v1/direct_payment/payments/bill/{bill.uuid}/detail",
                headers=api_helpers.json_headers(user=bill_user),
            )
        assert res.status_code == 400

    def test_call_payments_detail(
        self,
        client,
        api_helpers,
        bill_user,
        historic_bill,
        past_historic_cost_breakdown,
    ):
        with mock.patch(
            "direct_payment.billing.http.common.BillResourceMixin._user_has_access_to_bill_or_403"
        ):
            res = client.get(
                f"/api/v1/direct_payment/payments/bill/{historic_bill.uuid}/detail",
                headers=api_helpers.json_headers(user=bill_user),
            )
        assert res.status_code == 200
        assert res.json["covered_amount_total"] == 0

    @pytest.mark.parametrize(
        "refund_refinement_phase_2_flag_value, is_cancelled_bill",
        [(True, True), (True, False), (False, True), (False, False)],
    )
    def test_alert_label(
        self,
        client,
        api_helpers,
        bill_user,
        cancelled_bill,
        historic_bill,
        ff_test_data,
        refund_refinement_phase_2_flag_value,
        is_cancelled_bill,
    ):
        ff_test_data.update(
            ff_test_data.flag("refund-refinement-phase-2").variation_for_all(
                refund_refinement_phase_2_flag_value
            )
        )
        if is_cancelled_bill:
            bill = cancelled_bill
        else:
            bill = historic_bill

        with mock.patch(
            "direct_payment.billing.http.common.BillResourceMixin._user_has_access_to_bill_or_403"
        ):
            res = client.get(
                f"/api/v1/direct_payment/payments/bill/{bill.uuid}/detail",
                headers=api_helpers.json_headers(user=bill_user),
            )

            assert res.status_code == 200
            if refund_refinement_phase_2_flag_value and is_cancelled_bill:
                assert res.json["alert_label"] == (
                    "This procedure was cancelled. If applicable, your full payment "
                    "will be refunded to your original payment method."
                )
            elif not refund_refinement_phase_2_flag_value:
                # when the flag is off, won't set the alert_label field
                assert "alert_label" not in res.json
            else:
                # when the flag is on, but the bill is not cancelled, set the field to None
                assert res.json["alert_label"] is None

    @pytest.mark.parametrize("locale", ["es", "fr", "fr_CA"])
    def test_payments_detail_translations(
        self, client, api_helpers, bill_user, historic_bill, locale
    ):
        # given
        expected_english_labels = [
            "Coinsurance",
            "Copay",
            "Deductible",
            "Fees",
            "Not Covered",
            "Maven Benefit",
            "Medical Plan",
            "Total Member Responsibility",
            "Previous Charge(s)",
            "Estimate Adjustment",
        ]
        expected_translation_labels = [
            "payments_mmb_coinsurance",
            "payments_mmb_copay",
            "payments_mmb_deductible",
            "payments_mmb_fees",
            "payments_mmb_not_covered",
            "payments_mmb_maven_benefit",
            "payments_mmb_medical_plan",
            "payments_mmb_total_member_responsibility",
            "payments_mmb_previous_charges",
            "payments_mmb_estimate_adjustment",
        ]

        # when
        with mock.patch(
            "direct_payment.billing.http.common.BillResourceMixin._user_has_access_to_bill_or_403"
        ):
            with feature_flags.test_data() as td:
                td.update(
                    td.flag("release-mono-api-localization").variation_for_all(True)
                )
                res = client.get(
                    f"/api/v1/direct_payment/payments/bill/{historic_bill.uuid}/detail",
                    headers=api_helpers.with_locale_header(
                        api_helpers.json_headers(user=bill_user), locale=locale
                    ),
                )

        # then
        result = res.json
        assert "responsibility_breakdown" in result
        for breakdown in result["responsibility_breakdown"]:
            assert breakdown["label"] not in expected_english_labels
            assert breakdown["label"] not in expected_translation_labels
            assert breakdown["label"] != ""
            assert breakdown["label"] is not None
