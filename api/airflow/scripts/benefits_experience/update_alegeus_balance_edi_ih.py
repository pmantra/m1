import typing

from airflow.utils import with_app_context
from wallet.utils.alegeus.edi_processing.process_edi_balance_update import (
    process_balance_update,
)


@with_app_context(team_ns="benefits_experience", service_ns="wallet")
def process_balance_update_job(**kwargs: typing.Any) -> None:
    process_balance_update(**kwargs)
