"""Add wallet reporting tables

Revision ID: 2d81c91f9160
Revises: 63c34f7fc0d2
Create Date: 2023-02-06 23:28:31.065126+00:00

"""
from alembic import op
import sqlalchemy as sa

from wallet.models.constants import (
    WalletReportConfigColumnTypes,
    WalletReportConfigCadenceTypes,
)


# revision identifiers, used by Alembic.
revision = "2d81c91f9160"
down_revision = "63c34f7fc0d2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "wallet_client_reports",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "organization_id",
            sa.Integer,
            sa.ForeignKey("organization.id"),
            nullable=False,
        ),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("end_date", sa.Date, nullable=False),
        sa.Column("client_submission_date", sa.Date, nullable=True),
        sa.Column("client_approval_date", sa.Date, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("peakone_sent_date", sa.Date, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
    )
    op.create_index(
        "ix_wallet_client_organization_end_date",
        "wallet_client_reports",
        ["organization_id", "end_date"],
    )
    op.create_table(
        "wallet_client_report_configuration",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "organization_id",
            sa.Integer,
            sa.ForeignKey("organization.id"),
            nullable=False,
        ),
        sa.Column("cadence", sa.Enum(WalletReportConfigCadenceTypes), nullable=False),
    )
    op.create_table(
        "wallet_client_report_reimbursements",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "reimbursement_request_id",
            sa.BigInteger,
            sa.ForeignKey("reimbursement_request.id"),
            unique=True,
            nullable=False,
        ),
        sa.Column(
            "wallet_client_report_id",
            sa.BigInteger,
            sa.ForeignKey("wallet_client_reports.id"),
            nullable=False,
        ),
    )

    config_report_types_table = op.create_table(
        "wallet_client_report_configuration_report_types",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "column_type", sa.Enum(WalletReportConfigColumnTypes), nullable=False
        ),
    )

    config_report_types_list = [
        {"column_type": t.name} for t in WalletReportConfigColumnTypes
    ]

    op.bulk_insert(config_report_types_table, config_report_types_list)

    op.create_table(
        "wallet_client_report_configuration_report_columns",
        sa.Column(
            "wallet_client_report_configuration_id",
            sa.BigInteger,
            sa.ForeignKey("wallet_client_report_configuration.id"),
            nullable=False,
        ),
        sa.Column(
            "wallet_client_report_configuration_report_type_id",
            sa.Integer,
            sa.ForeignKey("wallet_client_report_configuration_report_types.id"),
            nullable=False,
        ),
    )


def downgrade():
    op.drop_constraint(
        "wallet_client_reports_ibfk_1", "wallet_client_reports", type_="foreignkey"
    )
    op.drop_constraint(
        "wallet_client_report_reimbursements_ibfk_1",
        "wallet_client_report_reimbursements",
        type_="foreignkey",
    )
    op.drop_constraint(
        "wallet_client_report_reimbursements_ibfk_2",
        "wallet_client_report_reimbursements",
        type_="foreignkey",
    )
    op.drop_constraint(
        "wallet_client_report_configuration_report_columns_ibfk_1",
        "wallet_client_report_configuration_report_columns",
        type_="foreignkey",
    )
    op.drop_constraint(
        "wallet_client_report_configuration_report_columns_ibfk_2",
        "wallet_client_report_configuration_report_columns",
        type_="foreignkey",
    )

    op.drop_constraint(
        "wallet_client_report_configuration_ibfk_1",
        "wallet_client_report_configuration",
        type_="foreignkey",
    )
    op.drop_index("ix_wallet_client_organization_end_date", "wallet_client_reports")
    op.drop_table("wallet_client_reports")
    op.drop_table("wallet_client_report_configuration")
    op.drop_table("wallet_client_report_reimbursements")
    op.drop_table("wallet_client_report_configuration_report_types")
    op.drop_table("wallet_client_report_configuration_report_columns")
