import datetime
import os
from datetime import date
from unittest import mock
from unittest.mock import ANY

import factory
import pytest
from freezegun import freeze_time
from maven import feature_flags

from cost_breakdown.pytests.factories import CostBreakdownFactory
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureType,
)
from direct_payment.treatment_procedure.pytests.factories import (
    TreatmentProcedureFactory,
)
from payer_accumulator.common import PayerName, TreatmentAccumulationStatus
from payer_accumulator.errors import (
    NoMappingDataProvidedError,
    SkipAccumulationDueToMissingInfo,
)
from payer_accumulator.file_generators import AccumulationFileGeneratorUHC
from payer_accumulator.file_generators.fixed_width_accumulation_file_generator import (
    FixedWidthAccumulationFileGenerator,
)
from payer_accumulator.models.accumulation_treatment_mapping import (
    AccumulationTreatmentMapping,
)
from payer_accumulator.pytests.factories import (
    AccumulationTreatmentMappingFactory,
    PayerAccumulationReportsFactory,
)
from wallet.models.constants import (
    MemberHealthPlanPatientRelationship,
    MemberHealthPlanPatientSex,
    ReimbursementRequestExpenseTypes,
    ReimbursementRequestState,
    WalletState,
)
from wallet.models.reimbursement_wallet import MemberHealthPlan
from wallet.pytests.factories import (
    MemberHealthPlanFactory,
    ReimbursementRequestCategoryFactory,
    ReimbursementRequestFactory,
    ReimbursementServiceCategoryFactory,
    ReimbursementWalletFactory,
    WalletExpenseSubtypeFactory,
)
from wallet.repository.health_plan import (
    HEALTH_PLAN_YOY_FLAG,
    NEW_BEHAVIOR,
    OLD_BEHAVIOR,
)


class MockConfig:
    HEADER_ROW = {}
    DETAIL_ROW = {}
    TRAILER_ROW = {}


class RawAccumulationFileGenerator(FixedWidthAccumulationFileGenerator):
    def file_name(self):
        pass

    def _generate_detail(
        self,
        record_id,
        record_type,
        sequence_number,
        cost_breakdown,
        service_start_date,
        deductible,
        oop_applied,
        hra_applied,
        member_health_plan,
        is_reversal,
        is_regeneration,
    ):
        pass

    def get_oop_from_row(self, detail_row: {}) -> int:
        pass

    def get_deductible_from_row(self, detail_row: {}) -> int:
        pass

    def get_cardholder_id_from_detail_dict(detail_row_dict: {}):
        pass

    def get_cardholder_id(member_health_plan: MemberHealthPlan):
        pass

    def get_detail_rows(report_rows: []) -> []:
        pass

    def get_dob_from_report_row(self, detail_row_dict: {}) -> date:
        pass


@pytest.fixture
def mock_config():
    return MockConfig()


@pytest.fixture
def file_generator(db, mock_config):
    with mock.patch(
        "payer_accumulator.helper_functions.get_payer_id", return_value=100
    ), mock.patch("importlib.import_module", return_value=mock_config):
        return RawAccumulationFileGenerator(
            payer_name=PayerName.UHC, session=db.session
        )


@pytest.fixture
def wallet():
    return ReimbursementWalletFactory.create(state=WalletState.QUALIFIED)


@pytest.fixture
def wallet_category(wallet):
    return wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
        0
    ].reimbursement_request_category


@pytest.fixture
def mhp_yoy_feature_flag_on(request):
    with feature_flags.test_data() as ff_test_data:
        ff_test_data.update(
            ff_test_data.flag(HEALTH_PLAN_YOY_FLAG).variations(request.param)
        )
        yield ff_test_data


@pytest.fixture(scope="function")
def member_health_plan(enterprise_user, employer_health_plan):
    return MemberHealthPlanFactory.create(
        employer_health_plan_id=1,
        reimbursement_wallet=ReimbursementWalletFactory.create(
            id=5, state=WalletState.QUALIFIED
        ),
        employer_health_plan=employer_health_plan,
        reimbursement_wallet_id=5,
        is_subscriber=True,
        patient_sex=MemberHealthPlanPatientSex.FEMALE,
        patient_relationship=MemberHealthPlanPatientRelationship.CARDHOLDER,
        member_id=enterprise_user.id,
        subscriber_insurance_id="u1234567801",
    )


@pytest.fixture(scope="function")
def reimbursement_requests(member_health_plan):
    category = ReimbursementRequestCategoryFactory.create(label="fertility")
    rsc_fertility = ReimbursementServiceCategoryFactory(
        category="FERTILITY", name="Fertility"
    )
    wallet_expense_subtype = WalletExpenseSubtypeFactory.create(
        expense_type=ReimbursementRequestExpenseTypes.FERTILITY,
        reimbursement_service_category=rsc_fertility,
        code="FIVF",
        description="IVF (with fresh transfer)",
    )
    rrs = ReimbursementRequestFactory.create_batch(
        size=5,
        service_start_date=datetime.datetime(2024, 1, 1),
        service_end_date=datetime.datetime(2024, 2, 1),
        person_receiving_service_id=member_health_plan.member_id,
        reimbursement_wallet_id=member_health_plan.reimbursement_wallet_id,
        reimbursement_request_category_id=category.id,
        state=ReimbursementRequestState.APPROVED,
        wallet_expense_subtype_id=wallet_expense_subtype.id,
        procedure_type=TreatmentProcedureType.MEDICAL.value,
    )
    CostBreakdownFactory.create_batch(
        size=5,
        deductible=10000,
        oop_applied=10000,
        reimbursement_request_id=factory.Iterator([rr.id for rr in rrs]),
    )
    return rrs


@pytest.fixture(scope="function")
def accumulation_treatment_mappings_regenerate(uhc_payer, reimbursement_requests):
    return AccumulationTreatmentMappingFactory.create_batch(
        size=4,
        payer_id=uhc_payer.id,
        reimbursement_request_id=factory.Iterator(
            [rr.id for rr in reimbursement_requests]
        ),
        treatment_accumulation_status=factory.Iterator(
            [
                TreatmentAccumulationStatus.SUBMITTED,
                TreatmentAccumulationStatus.SUBMITTED,
                TreatmentAccumulationStatus.SUBMITTED,
            ]
        ),
        deductible=factory.Iterator([500, 300, 0, -2300]),
        oop_applied=factory.Iterator([400, 200, 0, -1200]),
    )


@pytest.fixture(scope="function")
def regenerated_uhc_test_file() -> str:
    file_path = os.path.join(
        os.path.dirname(__file__),
        "../test_files/regenerated_Maven_UHC_Accumulator_File",
    )
    with open(file_path, "r") as file:
        content = file.read()
    return content


class TestAccumulationFileGenerator:
    def test_json_validation_against_config(self, file_generator, mock_config):
        with pytest.raises(ValueError) as e:
            file_generator.validate_json_against_config(
                report_data={"id": 1, "test_field": "test_value"},
                row=1,
                expected_config=mock_config.DETAIL_ROW,
            )
            assert (
                str(e.value)
                == "ValueError: Unexpected columns in row 0: test_field, id"
            )

    def test_json_validation_against_config_passes(self, file_generator, mock_config):
        mock_config.DETAIL_ROW = {"id": {}, "test_field": {}}
        res = file_generator.validate_json_against_config(
            report_data={"id": 1, "test_field": "test_value"},
            row=1,
            expected_config=mock_config.DETAIL_ROW,
        )
        assert res is True

    @pytest.mark.parametrize(
        "mhp_yoy_feature_flag_on", [NEW_BEHAVIOR, OLD_BEHAVIOR], indirect=True
    )
    def test__generate_detail_by_reimbursement_request(
        self,
        file_generator,
        make_new_reimbursement_request_for_report_row,
        uhc_payer,
        mhp_yoy_feature_flag_on,
        cost_breakdown_mr_100,
    ):
        reimbursement_request = make_new_reimbursement_request_for_report_row()
        reimbursement_request.service_start_date = datetime.datetime(
            year=2025, month=1, day=10
        )
        with mock.patch.object(file_generator, "_generate_detail") as generate_detail:
            file_generator._generate_detail_by_reimbursement_request(
                reimbursement_request=reimbursement_request,
                record_type="MEDICAL",
                sequence_number=1,
                deductible_apply_amount=100,
                oop_apply_amount=200,
                cost_breakdown=cost_breakdown_mr_100,
            )
            assert generate_detail.called
            assert generate_detail.call_args.kwargs == {
                "record_id": reimbursement_request.id,
                "record_type": TreatmentProcedureType.MEDICAL,
                "sequence_number": 1,
                "cost_breakdown": cost_breakdown_mr_100,
                "service_start_date": reimbursement_request.service_start_date,
                "member_health_plan": ANY,
                "deductible": 100,
                "oop_applied": 200,
                "hra_applied": 0,
                "is_reversal": False,
                "is_regeneration": False,
            }

    @pytest.mark.parametrize(
        "mhp_yoy_feature_flag_on", [NEW_BEHAVIOR, OLD_BEHAVIOR], indirect=True
    )
    def test__generate_detail_by_treatment_procedure(
        self,
        file_generator,
        make_new_procedure_for_report_row,
        uhc_payer,
        cost_breakdown_mr_100,
        mhp_yoy_feature_flag_on,
    ):
        treatment_procedure = make_new_procedure_for_report_row(
            payer=uhc_payer, cost_breakdown_deductible=0
        )
        treatment_procedure.start_date = datetime.datetime(year=2025, month=1, day=10)
        treatment_procedure.end_date = datetime.datetime(year=2025, month=1, day=15)
        with mock.patch.object(
            file_generator, "_generate_detail"
        ) as generate_detail, mock.patch.object(
            file_generator, "get_cost_breakdown", return_value=cost_breakdown_mr_100
        ):
            file_generator._generate_detail_by_treatment_procedure(
                treatment_procedure=treatment_procedure,
                sequence_number=1,
                deductible=100,
                oop_applied=200,
                cost_breakdown=cost_breakdown_mr_100,
            )
            assert generate_detail.called
            assert generate_detail.call_args.kwargs == {
                "record_id": treatment_procedure.id,
                "record_type": TreatmentProcedureType.MEDICAL,
                "sequence_number": 1,
                "cost_breakdown": cost_breakdown_mr_100,
                "service_start_date": treatment_procedure.start_date,
                "member_health_plan": ANY,
                "deductible": 100,
                "oop_applied": 200,
                "hra_applied": 0,
                "is_reversal": False,
                "is_regeneration": False,
            }

    def test_get_mapping_data_for_accumulation(
        self, file_generator, wallet, wallet_category
    ):
        treatment_procedures = TreatmentProcedureFactory.create_batch(size=3)
        reimbursement_requests = ReimbursementRequestFactory.create_batch(
            size=3,
            wallet=wallet,
            reimbursement_wallet_id=wallet.id,
            category=wallet_category,
        )
        mappings = AccumulationTreatmentMappingFactory.create_batch(
            size=6,
            treatment_procedure_uuid=factory.Iterator(
                [tp.uuid for tp in treatment_procedures] + [None, None, None]
            ),
            reimbursement_request_id=factory.Iterator(
                [None, None, None] + [rr.id for rr in reimbursement_requests]
            ),
            treatment_accumulation_status=factory.Iterator(
                [
                    TreatmentAccumulationStatus.PAID,
                    TreatmentAccumulationStatus.PAID,
                    TreatmentAccumulationStatus.WAITING,  # will not be returned by query
                    TreatmentAccumulationStatus.PAID,
                    TreatmentAccumulationStatus.PAID,
                    TreatmentAccumulationStatus.WAITING,  # will not be returned by query
                ]
            ),
            payer_id=factory.Iterator(
                [
                    file_generator.payer_id,
                    file_generator.payer_id + 1,  # will not be returned by query
                    file_generator.payer_id,
                    file_generator.payer_id,
                    file_generator.payer_id + 1,  # will not be returned by query
                    file_generator.payer_id,
                ]
            ),
        )

        mapping_tuples = file_generator._accumulation_mappings_with_data
        assert len(mapping_tuples) == 2
        valid_mappings = {mapping_tuple[0] for mapping_tuple in mapping_tuples}
        assert valid_mappings == {mappings[0], mappings[3]}
        valid_treatment_procedures = {
            mapping_tuple[1] for mapping_tuple in mapping_tuples
        }
        assert valid_treatment_procedures == {treatment_procedures[0], None}
        valid_reimbursement_requests = {
            mapping_tuple[2] for mapping_tuple in mapping_tuples
        }
        assert valid_reimbursement_requests == {reimbursement_requests[0], None}
        for mapping_tuple in mapping_tuples:
            assert mapping_tuple[1] is None or mapping_tuple[2] is None

    def test_get_cost_breakdown_for_treatment_procedure(self, file_generator):
        treatment_procedure = TreatmentProcedureFactory.create()
        expected_cost_breakdown = CostBreakdownFactory.create(
            treatment_procedure_uuid=treatment_procedure.uuid,
        )
        treatment_procedure.cost_breakdown_id = expected_cost_breakdown.id
        cost_breakdown = file_generator.get_cost_breakdown(
            treatment_procedure=treatment_procedure,
            reimbursement_request=None,
        )
        assert cost_breakdown == expected_cost_breakdown

    def test_get_cost_breakdown_for_reimbursement_request(
        self, file_generator, wallet, wallet_category
    ):
        reimbursement_request = ReimbursementRequestFactory.create(
            wallet=wallet, reimbursement_wallet_id=wallet.id, category=wallet_category
        )
        CostBreakdownFactory.create(
            treatment_procedure_uuid=None,
            reimbursement_request_id=reimbursement_request.id,
            created_at=datetime.datetime.utcnow() - datetime.timedelta(days=1),
        )
        expected_cost_breakdown = CostBreakdownFactory.create(
            treatment_procedure_uuid=None,
            reimbursement_request_id=reimbursement_request.id,
        )
        cost_breakdown = file_generator.get_cost_breakdown(
            treatment_procedure=None,
            reimbursement_request=reimbursement_request,
        )
        assert cost_breakdown == expected_cost_breakdown

    def test_get_cost_breakdown_fails(self, file_generator):
        with pytest.raises(NoMappingDataProvidedError):
            file_generator.get_cost_breakdown(
                treatment_procedure=None,
                reimbursement_request=None,
            )

    @pytest.mark.parametrize(
        "deductible,oop,treatment_procedure,reimbursement_request,raises",
        [
            (0, 0, None, None, SkipAccumulationDueToMissingInfo),
            (100, 110, None, None, NoMappingDataProvidedError),
        ],
    )
    def test_get_detail_fails(
        self,
        file_generator,
        deductible,
        oop,
        treatment_procedure,
        reimbursement_request,
        raises,
        cost_breakdown_mr_100,
    ):
        with pytest.raises(raises):
            file_generator.get_detail(
                deductible,
                oop,
                cost_breakdown_mr_100,
                1,
                treatment_procedure,
                reimbursement_request,
            )

    @pytest.mark.parametrize(
        "treatment_procedure,reimbursement_request,called",
        [
            (mock.Mock(), None, "_generate_detail_by_treatment_procedure"),
            (
                None,
                mock.Mock(procedure_type=TreatmentProcedureType.MEDICAL),
                "_generate_detail_by_reimbursement_request",
            ),
        ],
    )
    def test_get_detail(
        self,
        file_generator,
        treatment_procedure,
        reimbursement_request,
        called,
        cost_breakdown_mr_100,
    ):
        with mock.patch(
            f"payer_accumulator.file_generators.fixed_width_accumulation_file_generator.FixedWidthAccumulationFileGenerator.{called}"
        ) as detail_func:
            file_generator.get_detail(
                100,
                110,
                cost_breakdown_mr_100,
                1,
                0,
                treatment_procedure,
                reimbursement_request,
            )
        assert detail_func.called

    def test_skip_mappings(self, file_generator):
        treatment_procedure = TreatmentProcedureFactory.create()
        cost_breakdown = CostBreakdownFactory.create(
            treatment_procedure_uuid=treatment_procedure.uuid,
            deductible=0,
            oop_remaining=0,
        )
        treatment_procedure.cost_breakdown_id = cost_breakdown.id
        expected_mapping = AccumulationTreatmentMappingFactory.create(
            treatment_procedure_uuid=treatment_procedure.uuid,
            payer_id=file_generator.payer_id,
        )
        buffered_contents = file_generator.generate_file_contents()
        mapping = AccumulationTreatmentMapping.query.get(expected_mapping.id)
        assert (
            mapping.treatment_accumulation_status
            == expected_mapping.treatment_accumulation_status
        )
        assert len(buffered_contents.getvalue()) == 0

    @pytest.mark.parametrize(
        "mhp_yoy_feature_flag_on", [NEW_BEHAVIOR, OLD_BEHAVIOR], indirect=True
    )
    def test__get_member_health_plan_found(
        self,
        file_generator,
        make_new_reimbursement_request_for_report_row,
        mhp_yoy_feature_flag_on,
    ):
        reimbursement_request = make_new_reimbursement_request_for_report_row()
        reimbursement_request.service_start_date = datetime.datetime(
            year=2025, month=2, day=1
        )
        member_health_plan = file_generator.get_member_health_plan(
            member_id=reimbursement_request.person_receiving_service_id,
            wallet_id=reimbursement_request.reimbursement_wallet_id,
            effective_date=reimbursement_request.service_start_date,
        )
        assert member_health_plan

    def test__get_member_health_plan_found_not_found(
        self,
        file_generator,
        make_new_reimbursement_request_for_report_row,
        mhp_yoy_feature_flag_enabled,
    ):
        reimbursement_request = make_new_reimbursement_request_for_report_row()
        # Health Plan starts in 2025 in factory settings
        reimbursement_request.service_start_date = datetime.datetime(
            year=2024, month=2, day=1
        )
        member_health_plan = file_generator.get_member_health_plan(
            member_id=reimbursement_request.person_receiving_service_id,
            wallet_id=reimbursement_request.reimbursement_wallet_id,
            effective_date=reimbursement_request.service_start_date,
        )
        assert member_health_plan is None


class TestRegenerateFileContentsFromReport:
    @freeze_time("2025-01-08 20:00:00")
    def test_regenerate_file_contents_from_report__success(
        self,
        uhc_payer,
        accumulation_treatment_mappings_regenerate,
        regenerated_uhc_test_file,
    ):
        # given
        report = PayerAccumulationReportsFactory.create(payer_id=uhc_payer.id)
        report.treatment_mappings = accumulation_treatment_mappings_regenerate
        file_generator = AccumulationFileGeneratorUHC()
        # when

        content = file_generator.regenerate_file_contents_from_report(report)
        # then
        regenerated_uhc_test_file_lines = regenerated_uhc_test_file.split("\n")
        content_lines = content.getvalue().split("\r\n")
        formatted_content_lines = [line.strip() for line in content_lines]
        # uses values from accumulation treatment mapping record, not cost breakdown
        assert regenerated_uhc_test_file_lines == formatted_content_lines

    def test_regenerate_file_contents_from_report__no_mappings(
        self,
        uhc_payer,
        file_generator,
    ):
        # given
        report = PayerAccumulationReportsFactory.create(payer_id=uhc_payer.id)
        # when
        content = file_generator.regenerate_file_contents_from_report(report)
        # then
        assert content.getvalue() == ""
