import uuid
from unittest import mock


class TestEstimateDetailsForWallet:
    def test_no_bill(self, client, api_helpers, bill_wallet):
        res = client.get(
            f"/api/v1/direct_payment/payments/reimbursement_wallet/estimates/{bill_wallet.id}",
            headers=api_helpers.json_headers(bill_wallet.member),
        )
        assert res.json == {"estimates_details": []}

    def test_estimates(self, client, api_helpers, bill_wallet, bill_with_estimate):
        res = client.get(
            f"/api/v1/direct_payment/payments/reimbursement_wallet/estimates/{bill_wallet.id}",
            headers=api_helpers.json_headers(bill_wallet.member),
        )
        assert len(res.json["estimates_details"]) == 1
        detail = res.json["estimates_details"][0]
        assert detail[
            "estimate_creation_date"
        ] == bill_with_estimate.created_at.strftime("%b %d, %Y")
        assert (
            detail["estimate_creation_date_raw"]
            == bill_with_estimate.created_at.isoformat()
        )


class TestEstimateDetailsForBill:
    def test_no_bill(self, client, api_helpers, bill_user):
        res = client.get(
            f"/api/v1/direct_payment/payments/estimate/{str(uuid.uuid4())}/detail",
            headers=api_helpers.json_headers(bill_user),
        )
        assert res.status_code == 404

    def test_unexpected_error(self, client, api_helpers, bill_user, bill_with_estimate):
        with mock.patch(
            "direct_payment.payments.http.estimates_detail.EstimateDetailResource.deserialize",
            side_effect=ValueError("Mock error."),
        ):
            res = client.get(
                f"/api/v1/direct_payment/payments/estimate/{str(bill_with_estimate.uuid)}/detail",
                headers=api_helpers.json_headers(bill_user),
            )
        assert res.status_code == 400

    def test_estimates(self, client, api_helpers, bill_user, bill_with_estimate):
        res = client.get(
            f"/api/v1/direct_payment/payments/estimate/{str(bill_with_estimate.uuid)}/detail",
            headers=api_helpers.json_headers(bill_user),
        )
        assert res.status_code == 200
        assert res.json[
            "estimate_creation_date"
        ] == bill_with_estimate.created_at.strftime("%b %d, %Y")
        assert (
            res.json["estimate_creation_date_raw"]
            == bill_with_estimate.created_at.isoformat()
        )
