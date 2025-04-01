import contextlib
import time
from typing import Callable, Generator

from maven import feature_flags, observability

from app import create_app
from storage import connection
from utils.log import logger
from wallet.constants import ALEGEUS_SYNCH_IN_CATEGORY_SETTINGS_JOB
from wallet.models.models import CategoryRuleProcessingResultSchema
from wallet.services.reimbursement_category_activation_visibility import (
    CategoryActivationService,
)

log = logger(__name__)


def main() -> int:
    with create_app().app_context():
        res = job_driver()
        exit_code = int(not res)
        log.info("Job Terminating.", exit_code=exit_code)
        return exit_code  # 0 is success


def job_driver() -> tuple[bool, int, int]:
    to_return, tot_success_cnt, tot_failure_cnt = True, 0, 0
    from wallet.services.reimbursement_category_activation_visibility import (
        CategoryActivationService,
    )

    all_results = {}
    svc = CategoryActivationService(session=connection.db.session)
    for svc_fn in [
        svc.process_allowed_categories_that_have_rules,
        svc.process_allowed_categories_without_rules,
    ]:
        try:
            results = _run_processing_functions(svc, svc_fn)
            if results:
                all_results[svc_fn.__name__] = results
        except Exception as e:
            log.exception(
                "Error processing categories. The run for the function may have partially committed. Check logs.",
                svc_fn=svc_fn.__name__,
                exception=e,
            )
            # any exceptions lead to the job failing.
            to_return = False
    for fn_name, results in all_results.items():
        failures = [r for r in results if not r.success]
        failure_cnt = len(failures)
        success_cnt = len(results) - len(failures)
        tot_success_cnt += success_cnt
        tot_failure_cnt += failure_cnt
        log.info(
            "Processing Function Summary.",
            fn_name=fn_name,
            cnt_failure=failure_cnt,
            cnt_success=success_cnt,
        )
        for rec in failures:
            log.info("Failed record:", record=rec)
    log.info(
        "Job summary.",
        return_status=to_return,
        cnt_tot_success=tot_success_cnt,
        cnt_tot_failure=tot_failure_cnt,
    )
    return to_return, tot_success_cnt, tot_failure_cnt


@contextlib.contextmanager
def time_processing_fn(fn_name: str) -> Generator[float, None, None]:
    """Context manager for timing function execution and logging results."""
    start_time = time.perf_counter()
    log.info(
        "Processing Function - run started.",
        fn_name=fn_name,
        start_time=start_time,
    )
    yield start_time
    end_time = time.perf_counter()
    log.info(
        "Processing Function - run completed.",
        fn_name=fn_name,
        start_time=start_time,
        end_time=end_time,
        run_time_in_seconds=f"{end_time - start_time:.3f}",
    )


@observability.wrap
def _run_processing_functions(
    svc: CategoryActivationService, svc_fn: Callable
) -> list[CategoryRuleProcessingResultSchema]:
    bypass_alegeus = not feature_flags.bool_variation(
        ALEGEUS_SYNCH_IN_CATEGORY_SETTINGS_JOB, default=False
    )

    to_return: list[CategoryRuleProcessingResultSchema] = []
    commit_count = 0
    with time_processing_fn(svc_fn.__name__):
        for results in svc_fn(bypass_alegeus=bypass_alegeus, commit_size=40):
            svc.session.commit()
            to_return += results
            log.info("Committing Batch:", commit_count=commit_count)
            commit_count += 1
    return to_return


if __name__ == "__main__":
    main()
