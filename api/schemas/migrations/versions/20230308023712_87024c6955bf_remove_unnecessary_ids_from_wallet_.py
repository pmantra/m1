"""remove unnecessary ids from wallet report generation models

Revision ID: 87024c6955bf
Revises: 7ddeec3fd048
Create Date: 2023-03-08 02:37:12.382749+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "87024c6955bf"
down_revision = "7ddeec3fd048"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint(
        "wallet_client_report_configuration_report_columns_ibfk_1",
        "wallet_client_report_configuration_report_columns",
        type_="foreignkey",
    )

    op.drop_constraint(
        "wallet_client_report_configuration_ibfk_1",
        "wallet_client_report_configuration",
        type_="foreignkey",
    )
    op.drop_column("wallet_client_report_configuration", "id")
    op.drop_column("wallet_client_report_configuration", "organization_id")
    op.drop_column(
        "wallet_client_report_configuration_report_columns",
        "wallet_client_report_configuration_id",
    )
    op.add_column(
        "wallet_client_report_configuration",
        sa.Column(
            "organization_id",
            sa.Integer,
            sa.ForeignKey("organization.id"),
            primary_key=True,
        ),
    )
    op.create_primary_key(
        "wallet_client_report_configuration_pk",
        "wallet_client_report_configuration",
        ["organization_id"],
    )
    op.add_column(
        "wallet_client_report_configuration_report_columns",
        sa.Column(
            "wallet_client_report_configuration_id",
            sa.Integer,
            sa.ForeignKey("wallet_client_report_configuration.organization_id"),
            nullable=False,
        ),
    )
    op.drop_column("wallet_client_report_reimbursements", "id")
    op.create_primary_key(
        "wallet_client_report_reimbursements_pk",
        "wallet_client_report_reimbursements",
        ["reimbursement_request_id"],
    )


def downgrade():
    from wallet.models.constants import WalletReportConfigCadenceTypes

    op.drop_constraint(
        "wallet_client_report_configuration_report_columns_ibfk_3",
        "wallet_client_report_configuration_report_columns",
        type_="foreignkey",
    )
    op.drop_constraint(
        "wallet_client_report_configuration_ibfk_1",
        "wallet_client_report_configuration",
        type_="foreignkey",
    )
    op.drop_column(
        "wallet_client_report_configuration_report_columns",
        "wallet_client_report_configuration_id",
    )

    op.drop_table("wallet_client_report_configuration")
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
    op.drop_table("wallet_client_report_configuration_report_columns")
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
    op.drop_table("wallet_client_report_reimbursements")
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
