from datetime import datetime

from flask_sqlalchemy import SQLAlchemy

from appointments.models.appointment import Appointment
from mpractice.models.appointment import TransactionInfo
from mpractice.repository.transaction import TransactionRepository
from pytests.db_util import enable_db_performance_warnings


class TestTransactionRepository:
    def test_get_transaction_info_by_appointment_id_no_data(
        self,
        db: SQLAlchemy,
        transaction_repo: TransactionRepository,
        appointment_500: Appointment,
    ):
        with enable_db_performance_warnings(database=db, failure_threshold=2):
            result = transaction_repo.get_transaction_info_by_appointment_id(
                appointment_500.id
            )
            assert result == TransactionInfo()

    def test_get_transaction_info_by_appointment_id_with_credit(
        self,
        db: SQLAlchemy,
        transaction_repo: TransactionRepository,
        appointment_300: Appointment,
    ):
        with enable_db_performance_warnings(database=db, failure_threshold=2):
            result = transaction_repo.get_transaction_info_by_appointment_id(
                appointment_300.id
            )
            expected = TransactionInfo(
                credit_latest_used_at=datetime(2023, 3, 3, 9, 0, 0),
                total_used_credits=350,
            )
            assert result == expected

    def test_get_transaction_info_by_appointment_id_with_fee(
        self,
        db: SQLAlchemy,
        transaction_repo: TransactionRepository,
        appointment_400: Appointment,
    ):
        with enable_db_performance_warnings(database=db, failure_threshold=2):
            result = transaction_repo.get_transaction_info_by_appointment_id(
                appointment_400.id
            )
            expected = TransactionInfo(
                fees_count=2,
            )
            assert result == expected

    def test_get_transaction_info_by_appointment_id_with_payment(
        self,
        db: SQLAlchemy,
        transaction_repo: TransactionRepository,
        appointment_100: Appointment,
    ):
        with enable_db_performance_warnings(database=db, failure_threshold=2):
            result = transaction_repo.get_transaction_info_by_appointment_id(
                appointment_100.id
            )
            expected = TransactionInfo(
                payment_amount=100,
                payment_captured_at=datetime(2023, 1, 2, 9, 0, 0),
            )
            assert result == expected
