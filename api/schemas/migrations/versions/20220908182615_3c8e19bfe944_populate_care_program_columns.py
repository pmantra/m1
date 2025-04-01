"""Populate new care program columns.

Revision ID: 3c8e19bfe944
Revises: d4b7243e3427
Create Date: 2022-09-08 18:26:15.745294+00:00

"""

from storage.connection import db


# revision identifiers, used by Alembic.
revision = "3c8e19bfe944"
down_revision = "d4b7243e3427"
branch_labels = None
depends_on = None


new_column_values_mapping = {
    "Advanced Maternal Age (40+)": {
        "ecp_flag_type": "RISK",
        "ecp_program_qualifier": "CHRONIC_CONDITIONS",
    },
    "Blood disorder - Existing condition": {
        "ecp_flag_type": "RISK",
        "ecp_program_qualifier": "CHRONIC_CONDITIONS",
    },
    "Fertility treatments": {
        "ecp_flag_type": "RISK",
        "ecp_program_qualifier": "CHRONIC_CONDITIONS",
    },
    "Gestational diabetes - Past pregnancy": {
        "ecp_flag_type": "RISK",
        "ecp_program_qualifier": "CHRONIC_CONDITIONS",
    },
    "Kidney disease - Existing condition": {
        "ecp_flag_type": "RISK",
        "ecp_program_qualifier": "CHRONIC_CONDITIONS",
    },
    "Multiple gestation": {
        "ecp_flag_type": "RISK",
        "ecp_program_qualifier": "CHRONIC_CONDITIONS",
    },
    "Obesity": {
        "ecp_flag_type": "RISK",
        "ecp_program_qualifier": "CHRONIC_CONDITIONS",
    },
    "PCOS": {
        "ecp_flag_type": "RISK",
        "ecp_program_qualifier": "CHRONIC_CONDITIONS",
    },
    "Preterm birth - Past pregnancy": {
        "ecp_flag_type": "RISK",
        "ecp_program_qualifier": "CHRONIC_CONDITIONS",
    },
    "Eclampsia or HELLP - Past pregnancy": {
        "ecp_flag_type": "RISK",
        "ecp_program_qualifier": "CHRONIC_CONDITIONS",
    },
    "High blood pressure - Past pregnancy": {
        "ecp_flag_type": "RISK",
        "ecp_program_qualifier": "CHRONIC_CONDITIONS",
    },
    "Preeclampsia - Past pregnancy": {
        "ecp_flag_type": "RISK",
        "ecp_program_qualifier": "CHRONIC_CONDITIONS",
    },
    "Diabetes - Existing condition": {
        "ecp_flag_type": "CONDITION",
        "ecp_program_qualifier": "CHRONIC_CONDITIONS",
    },
    "Gestational diabetes - Current pregnancy": {
        "ecp_flag_type": "CONDITION",
        "ecp_program_qualifier": "CHRONIC_CONDITIONS",
    },
    "High blood pressure - Existing condition": {
        "ecp_flag_type": "CONDITION",
        "ecp_program_qualifier": "CHRONIC_CONDITIONS",
    },
    "Eclampsia or HELLP - Current pregnancy": {
        "ecp_flag_type": "CONDITION",
        "ecp_program_qualifier": "CHRONIC_CONDITIONS",
    },
    "High blood pressure - Current pregnancy": {
        "ecp_flag_type": "CONDITION",
        "ecp_program_qualifier": "CHRONIC_CONDITIONS",
    },
    "Preeclampsia - Current pregnancy": {
        "ecp_flag_type": "CONDITION",
        "ecp_program_qualifier": "CHRONIC_CONDITIONS",
    },
    "Depression - Existing condition": {
        "ecp_flag_type": "CONDITION",
        "ecp_program_qualifier": "MENTAL_HEALTH",
    },
    "Depression - Past pregnancy": {
        "ecp_flag_type": "RISK",
        "ecp_program_qualifier": "MENTAL_HEALTH",
    },
    "Postpartum depression - Past pregnancy": {
        "ecp_flag_type": "RISK",
        "ecp_program_qualifier": "MENTAL_HEALTH",
    },
    "Depression - Current pregnancy": {
        "ecp_flag_type": "CONDITION",
        "ecp_program_qualifier": "MENTAL_HEALTH",
    },
    "History of preterm labor or delivery": {
        "ecp_flag_type": "RISK",
        "ecp_program_qualifier": "CHRONIC_CONDITIONS",
    },
    "Kidney disease": {
        "ecp_flag_type": "RISK",
        "ecp_program_qualifier": "CHRONIC_CONDITIONS",
    },
    "Diabetes": {
        "ecp_flag_type": "CONDITION",
        "ecp_program_qualifier": "CHRONIC_CONDITIONS",
    },
    "Gestational diabetes": {
        "ecp_flag_type": "CONDITION",
        "ecp_program_qualifier": "CHRONIC_CONDITIONS",
    },
    "High blood pressure": {
        "ecp_flag_type": "CONDITION",
        "ecp_program_qualifier": "CHRONIC_CONDITIONS",
    },
    "Preeclampsia and eclampsia": {
        "ecp_flag_type": "CONDITION",
        "ecp_program_qualifier": "CHRONIC_CONDITIONS",
    },
    "Depression": {
        "ecp_flag_type": "CONDITION",
        "ecp_program_qualifier": "MENTAL_HEALTH",
    },
    "Perinatal mood disorder": {
        "ecp_flag_type": "CONDITION",
        "ecp_program_qualifier": "MENTAL_HEALTH",
    },
    "Issues with the cervix - Past pregnancy": {
        "ecp_flag_type": "RISK",
        "ecp_program_qualifier": "CHRONIC_CONDITIONS",
    },
    "Thrombophilia": {
        "ecp_flag_type": "RISK",
        "ecp_program_qualifier": "CHRONIC_CONDITIONS",
    },
    "Perinatal mood disorder - Past pregnancy": {
        "ecp_flag_type": "RISK",
        "ecp_program_qualifier": "MENTAL_HEALTH",
    },
    "Perinatal mood disorder - Current pregnancy": {
        "ecp_flag_type": "CONDITION",
        "ecp_program_qualifier": "MENTAL_HEALTH",
    },
}


def upgrade():
    # records_to_update = (
    #     db.session.query(UserFlag)
    #     .filter(UserFlag.name.in_(new_column_values_mapping.keys()))
    #     .all()
    # )
    # mappings = [
    #     {
    #         "id": x.id,
    #         "ecp_flag_type": new_column_values_mapping[x.name]["ecp_flag_type"],
    #         "ecp_program_qualifier": new_column_values_mapping[x.name][
    #             "ecp_program_qualifier"
    #         ],
    #     }
    #     for x in records_to_update
    # ]

    # db.session.bulk_update_mappings(UserFlag, mappings)
    db.session.commit()


def downgrade():

    # records_to_update = (
    #     db.session.query(UserFlag)
    #     .filter(UserFlag.name.in_(new_column_values_mapping.keys()))
    #     .all()
    # )
    # mappings = [
    #     {
    #         "id": x.id,
    #         "ecp_flag_type": None,
    #         "ecp_program_qualifier": None,
    #     }
    #     for x in records_to_update
    # ]

    # db.session.bulk_update_mappings(UserFlag, mappings)
    db.session.commit()
