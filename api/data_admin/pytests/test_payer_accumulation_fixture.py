from unittest import mock

from data_admin.views import apply_specs
from payer_accumulator.models.payer_accumulation_reporting import (
    PayerAccumulationReports,
)
from pytests.factories import EnterpriseUserFactory


def test_payer_accumulation_fixture(data_admin_app, load_fixture):
    # given
    test_user = EnterpriseUserFactory.create(
        email="test+mvnqa-payer_cigna_test@mavenclinic.com"
    )
    fixture = load_fixture("wallet/accumulation_report_cigna.json")

    # when
    with data_admin_app.test_request_context(), mock.patch(
        "data_admin.makers.user._add_a_user", return_value=test_user
    ), mock.patch("payer_accumulator.file_handler.AccumulationFileHandler.upload_file"):
        created, errors = apply_specs(fixture)

    # then
    assert errors == [], f"Errors in applying the fixture: {', '.join(errors)}"
    (
        payer,
        organization,
        org_settings,
        category,
        ehp,
        mock_user,
        wallet,
        mhp,
        cb_rr,
        cb_tp,
        report,
    ) = created
    assert isinstance(report, PayerAccumulationReports)
    assert report.payer_id == payer.id
