from traceback import format_exc

from sqlalchemy.orm.scoping import ScopedSession

from app import create_app
from payer_accumulator.accumulation_data_sourcer import AccumulationDataSourcer
from payer_accumulator.accumulation_data_sourcer_esi import AccumulationDataSourcerESI
from payer_accumulator.common import PayerName
from storage.connection import db
from tasks.queues import job
from utils.log import logger

log = logger(__name__)


def run_data_sourcing(payer_name: PayerName, session: ScopedSession):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    log.info("Start payer accumulation report data sourcing.", payer=payer_name.value)
    try:
        if payer_name == PayerName.ESI:
            data_sourcer = AccumulationDataSourcerESI(session=session)
        else:
            data_sourcer = AccumulationDataSourcer(payer_name, session=session)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "AccumulationDataSourcer", variable has type "AccumulationDataSourcerESI")
        data_sourcer.data_source_preparation_for_file_generation()
    except Exception as e:
        log.error(
            "Failed to run payer accumulation report data sourcing.",
            payer=payer_name.value,
            exe_info=True,
            reason=format_exc(),
            error_message=str(e),
        )
        raise

    log.info(
        "Successfully finished payer accumulation report data sourcing.",
        payer=payer_name.value,
    )


@job(service_ns="payer_accumulation", team_ns="payments_platform")
def anthem_data_sourcing() -> None:
    app = create_app()
    with app.app_context():
        run_data_sourcing(PayerName.ANTHEM, db.session)


@job(service_ns="payer_accumulation", team_ns="payments_platform")
def cigna_data_sourcing() -> None:
    app = create_app()
    with app.app_context():
        run_data_sourcing(PayerName.Cigna, db.session)


@job(service_ns="payer_accumulation", team_ns="payments_platform")
def esi_data_sourcing() -> None:
    app = create_app()
    with app.app_context():
        run_data_sourcing(PayerName.ESI, db.session)


@job(service_ns="payer_accumulation", team_ns="payments_platform")
def luminare_data_sourcing() -> None:
    app = create_app()
    with app.app_context():
        run_data_sourcing(PayerName.LUMINARE, db.session)


@job(service_ns="payer_accumulation", team_ns="payments_platform")
def premera_data_sourcing() -> None:
    app = create_app()
    with app.app_context():
        run_data_sourcing(PayerName.PREMERA, db.session)


@job(service_ns="payer_accumulation", team_ns="payments_platform")
def uhc_data_sourcing() -> None:
    app = create_app()
    with app.app_context():
        run_data_sourcing(PayerName.UHC, db.session)
