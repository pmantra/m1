import secrets

from app import create_app
from models.enterprise import OrganizationEmployee
from storage.connection import db
from utils.log import logger
from wallet.models.constants import WalletState
from wallet.models.reimbursement_wallet import ReimbursementWallet

log = logger(__name__)


def _get_new_id():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    return secrets.token_hex(15)


def create_organization_employee_alegeus_id():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    try:
        active_organization_employees_with_qualified_wallets = (
            db.session.query(OrganizationEmployee)
            .join(ReimbursementWallet)
            .filter(
                ReimbursementWallet.state == WalletState.QUALIFIED,
                OrganizationEmployee.alegeus_id.is_(None),
                OrganizationEmployee.deleted_at.is_(None),
            )
            .all()
        )

    except:  # noqa  B001  TODO:  Do not use bare `except:`, it also catches unexpected events like memory errors, interrupts, system exit, and so on.  Prefer `except Exception:`.  If you're sure what you're doing, be explicit and write `except BaseException:`.
        log.info("There was an error retrieving the organization_employees")

    count = 0
    for employee in active_organization_employees_with_qualified_wallets:
        try:
            employee.alegeus_id = _get_new_id()
            db.session.add(employee)
            count += 1
        except Exception as e:
            log.info(f"There was an error assigning the alegeus_id {e}")

    db.session.commit()
    log.info(f"{count} alegeus ids were successfully created.")


if __name__ == "__main__":
    with create_app().app_context():
        create_organization_employee_alegeus_id()
