from direct_payment.treatment_procedure.pytests.factories import (
    TreatmentProcedureFactory,
)
from models.questionnaires import RecordedAnswer, RecordedAnswerSet
from wallet.pytests.factories import ReimbursementRequestCategoryFactory


class TestTreatmentProcedureQuestionnairesRepository:
    def test_read_treatment_procedure_questionnaires_when_none_exist(
        self,
        treatment_procedure_questionnaire_repository,
    ):
        # Act
        result = treatment_procedure_questionnaire_repository.read()

        # Assert
        assert result is None

    def test_read_unique_treatment_procedure_questionnaires(
        self,
        treatment_procedure_questionnaire_repository,
        questionnaire_global_procedures,
    ):
        # Act
        result = treatment_procedure_questionnaire_repository.read()

        assert result is not None

        [procedures, questionnaires] = result

        # Assert
        assert len(procedures) == len(questionnaire_global_procedures)
        # - 1 for the duplicate questionnaire in the fixture
        assert len(questionnaires) == (len(questionnaire_global_procedures) - 1)

    def test_create_treatment_procedure_answer_set_with_invalid_data(
        self,
        treatment_procedure_questionnaire_repository,
    ):
        # Act
        result = treatment_procedure_questionnaire_repository.create_treatment_procedure_answer_set(
            fertility_clinic_id=1,
            questionnaire_id="1",
            questions=[],
            treatment_procedure_id=1,
            user_id=1,
        )

        # Assert
        assert result is None

    def test_create_treatment_procedure_answer_set_with_invalid_treatment_procedure(
        self,
        treatment_procedure_questionnaire_repository,
        fertility_clinic,
        fc_user,
        treatment_procedure_recorded_answer_set_questionnaire,
    ):
        # Arrange
        questionnaire_id = treatment_procedure_recorded_answer_set_questionnaire[
            "questionnaire_id"
        ]
        questions = treatment_procedure_recorded_answer_set_questionnaire["questions"]

        # Act
        result = treatment_procedure_questionnaire_repository.create_treatment_procedure_answer_set(
            fertility_clinic_id=fertility_clinic.id,
            questionnaire_id=questionnaire_id,
            questions=questions,
            treatment_procedure_id=1,
            user_id=fc_user.id,
        )

        # Assert
        assert result is None

    def test_create_treatment_procedure_answer_set_with_valid_data(
        self,
        treatment_procedure_questionnaire_repository,
        fertility_clinic,
        fc_user,
        treatment_procedure_recorded_answer_set_questionnaire,
        treatment_procedure,
    ):
        # Arrange
        questionnaire_id = treatment_procedure_recorded_answer_set_questionnaire[
            "questionnaire_id"
        ]
        questions = treatment_procedure_recorded_answer_set_questionnaire["questions"]

        # Act
        result = treatment_procedure_questionnaire_repository.create_treatment_procedure_answer_set(
            fertility_clinic_id=fertility_clinic.id,
            questionnaire_id=questionnaire_id,
            questions=questions,
            treatment_procedure_id=treatment_procedure.id,
            user_id=fc_user.id,
        )

        # Assert
        assert result.treatment_procedure_id == treatment_procedure.id
        assert result.questionnaire_id == questionnaire_id

        recorded_answer_set = (
            treatment_procedure_questionnaire_repository.session.query(
                RecordedAnswerSet
            )
            .filter(RecordedAnswerSet.id == result.recorded_answer_set_id)
            .all()
        )

        assert len(recorded_answer_set) == 1

        recorded_answer = (
            treatment_procedure_questionnaire_repository.session.query(RecordedAnswer)
            .filter(
                RecordedAnswer.recorded_answer_set_id == result.recorded_answer_set_id
            )
            .all()
        )

        assert len(recorded_answer) == 1

    def test_create_treatment_procedure_answer_set_deletes_existing_questionnaire_rows(
        self,
        treatment_procedure_questionnaire_repository,
        fertility_clinic,
        fc_user,
        treatment_procedure_recorded_answer_set_questionnaire,
    ):
        category = ReimbursementRequestCategoryFactory.create(label="fertility")
        tp_1 = TreatmentProcedureFactory.create(reimbursement_request_category=category)
        tp_2 = TreatmentProcedureFactory.create(reimbursement_request_category=category)

        # Arrange
        questionnaire_id = treatment_procedure_recorded_answer_set_questionnaire[
            "questionnaire_id"
        ]
        questions = treatment_procedure_recorded_answer_set_questionnaire["questions"]

        # Add some rows to the treatment_procedures_needing_questionnaires table
        for tp_id in [tp_1.id, tp_2.id]:
            treatment_procedure_questionnaire_repository.session.execute(
                "INSERT INTO treatment_procedures_needing_questionnaires (treatment_procedure_id) VALUES (:tp_id);",
                {"tp_id": tp_id},
            )

        # Make sure the rows were added
        rows = treatment_procedure_questionnaire_repository.session.execute(
            "SELECT treatment_procedure_id FROM treatment_procedures_needing_questionnaires;"
        ).fetchall()
        assert len(rows) == 2
        assert {tp_id for tp_id, in rows} == {tp_1.id, tp_2.id}

        # Act
        result = treatment_procedure_questionnaire_repository.create_treatment_procedure_answer_set(
            fertility_clinic_id=fertility_clinic.id,
            questionnaire_id=questionnaire_id,
            questions=questions,
            treatment_procedure_id=tp_1.id,
            user_id=fc_user.id,
        )

        # Assert
        assert result.treatment_procedure_id == tp_1.id
        assert result.questionnaire_id == questionnaire_id

        recorded_answer_set = (
            treatment_procedure_questionnaire_repository.session.query(
                RecordedAnswerSet
            )
            .filter(RecordedAnswerSet.id == result.recorded_answer_set_id)
            .all()
        )

        assert len(recorded_answer_set) == 1

        # Make sure the row was deleted
        rows = treatment_procedure_questionnaire_repository.session.execute(
            "SELECT treatment_procedure_id FROM treatment_procedures_needing_questionnaires;"
        ).fetchall()
        assert len(rows) == 1
        assert tp_2.id == rows[0][0]

    def test_create_treatment_procedure_answer_set_no_error_if_tpnq_entry_missing(
        self,
        treatment_procedure_questionnaire_repository,
        fertility_clinic,
        fc_user,
        treatment_procedure_recorded_answer_set_questionnaire,
    ):
        category = ReimbursementRequestCategoryFactory.create(label="fertility")
        tp = TreatmentProcedureFactory.create(reimbursement_request_category=category)

        # Arrange
        questionnaire_id = treatment_procedure_recorded_answer_set_questionnaire[
            "questionnaire_id"
        ]
        questions = treatment_procedure_recorded_answer_set_questionnaire["questions"]

        # Make sure the treatment_procedures_needing_questionnaires table is empty
        rows = treatment_procedure_questionnaire_repository.session.execute(
            "SELECT * FROM treatment_procedures_needing_questionnaires;"
        ).fetchall()
        assert len(rows) == 0

        # Act
        result = treatment_procedure_questionnaire_repository.create_treatment_procedure_answer_set(
            fertility_clinic_id=fertility_clinic.id,
            questionnaire_id=questionnaire_id,
            questions=questions,
            treatment_procedure_id=tp.id,
            user_id=fc_user.id,
        )

        # Assert
        assert result.treatment_procedure_id == tp.id
        assert result.questionnaire_id == questionnaire_id

        recorded_answer_set = (
            treatment_procedure_questionnaire_repository.session.query(
                RecordedAnswerSet
            )
            .filter(RecordedAnswerSet.id == result.recorded_answer_set_id)
            .all()
        )

        assert len(recorded_answer_set) == 1

    def test_create_treatment_procedure_answer_set_with_multiple_questionnaires(
        self,
        treatment_procedure_questionnaire_repository,
        fertility_clinic,
        fc_user,
        treatment_procedure_recorded_answer_set_questionnaire,
        treatment_procedure,
        treatment_procedure_cycle_based,
    ):
        # Arrange
        questionnaire_id = treatment_procedure_recorded_answer_set_questionnaire[
            "questionnaire_id"
        ]
        questions = treatment_procedure_recorded_answer_set_questionnaire["questions"]

        # Act - create answer sets with two different treatment procedures
        result = treatment_procedure_questionnaire_repository.create_treatment_procedure_answer_set(
            fertility_clinic_id=fertility_clinic.id,
            questionnaire_id=questionnaire_id,
            questions=questions,
            treatment_procedure_id=treatment_procedure.id,
            user_id=fc_user.id,
        )

        assert result.treatment_procedure_id == treatment_procedure.id
        assert result.questionnaire_id == questionnaire_id

        result = treatment_procedure_questionnaire_repository.create_treatment_procedure_answer_set(
            fertility_clinic_id=fertility_clinic.id,
            questionnaire_id=questionnaire_id,
            questions=questions,
            treatment_procedure_id=treatment_procedure_cycle_based.id,
            user_id=fc_user.id,
        )

        assert result.treatment_procedure_id == treatment_procedure_cycle_based.id
        assert result.questionnaire_id == questionnaire_id
