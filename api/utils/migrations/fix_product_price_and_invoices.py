"""
fix_product_price_and_invoices.py
https://app.shortcut.com/maven-clinic/story/104918/incorrect-payments-to-providers-due-to-incorrect-active-product

Fix a product price and any invoices with the incorrect price set

vertical_id: the vertical that needs to be fixed
incorrect_price: the price that we need to correct
correct_price: the price that we need to change to
minutes: what minutes are we fixing
start_date: when do we want to start looking
dry_run: only show output or actually run the updates (defaults to True)

- Not using plain kwargs or **kwargs because there are multiple functions to pass to
- Thought about making a class for it all, but that seemed like more work than worth 

Usage example:
    from utils.migrations.fix_product_price_and_invoices import (
        validate_args,
        fix_vertical_products,
        fix_vertical,
        fix_products,
        export_incorrect_invoices_fees,
    )
    args = {}
    args["vertical_id"] = 26
    args["incorrect_price"] = 25
    args["correct_price"] = 28
    args["minutes"] = 20
    args["start_date"] = "2022-07-26"
    args["dry_run"] = True

    args = validate_args(args)
    fix_vertical_products(args)
    export_incorrect_invoices_fees(args)
"""

import csv
from collections import defaultdict
from copy import deepcopy
from datetime import datetime
from sys import exit, stdout

from appointments.models.appointment import Appointment
from appointments.models.payments import (
    FeeAccountingEntry,
    FeeAccountingEntryTypes,
    Invoice,
)
from authn.models.user import User
from models.products import Product
from models.verticals_and_specialties import Vertical
from storage.connection import db
from utils.log import logger

log = logger(__name__)


# Fix the records in the vertical and product tables
def fix_vertical_products(args):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    fix_vertical(args)
    fix_products(args)
    return


# Fix the vertical (remove and add if need be)
def fix_vertical(args):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    vertical = (
        db.session.query(Vertical).filter(Vertical.id == args["vertical_id"]).first()
    )
    if not vertical:
        log.error("Vertical not found", vertical_id=args["vertical_id"])
        exit()

    # Look for the incorrect and correct product price
    has_change = False
    correct_price_found = False
    # sqlalchemy doesn't see deep changes, won't run the update otherwise
    # https://amercader.net/blog/beware-of-json-fields-in-sqlalchemy/
    vertical.products = deepcopy(vertical.products)
    for i, product in enumerate(vertical.products):
        # Look for the minutes first
        if product["minutes"] == args["minutes"]:
            # Remove the incorrect record if found
            if product["price"] == args["incorrect_price"]:
                has_change = True
                vertical.products.pop(i)
                log.info(
                    f"{args['dry_run_text']}Product removed from vertical record",
                    product=product,
                )
            # Did we find the correct one?
            elif product["price"] == args["correct_price"]:
                correct_price_found = True

    # Correct price not found? Add it
    if not correct_price_found:
        product = {"minutes": args["minutes"], "price": args["correct_price"]}
        vertical.products.append(product)
        has_change = True
        log.info(
            f"{args['dry_run_text']}Product added to vertical record", product=product
        )

    # Update the vertical if need be
    if has_change and not args["dry_run"]:
        db.session.commit()
    return


# Fix the product per prac
def fix_products(args):  # type: ignore[no-untyped-def] # Function is missing a type annotation

    # Get just the query first (we can store the user_ids and update with it)
    incorrect_products_query = db.session.query(Product).filter(
        Product.vertical_id == args["vertical_id"],
        Product.price == args["incorrect_price"],
        Product.minutes == args["minutes"],
        Product.is_active == 1,
    )
    incorrect_products = incorrect_products_query.all()
    if not incorrect_products:
        log.info("No incorrect products found")
        return

    # Incorrect products to deactivate
    incorrect_user_ids = []
    for incorrect_product in incorrect_products:
        incorrect_user_ids.append(incorrect_product.user_id)
        incorrect_product.is_active = 0

    log.info(
        f"{args['dry_run_text']}Products deactivated for the following users",
        user_ids=incorrect_user_ids,
    )

    # Which users have the correct product
    correct_products_query = db.session.query(Product).filter(
        Product.vertical_id == args["vertical_id"],
        Product.price == args["correct_price"],
        Product.minutes == args["minutes"],
    )
    correct_products = correct_products_query.all()
    correct_user_ids = []
    activated_products_user_ids = []
    for correct_product in correct_products:
        correct_user_ids.append(correct_product.user_id)
        # Activate if necessary
        if correct_product.is_active == 0:
            correct_product.is_active = 1
            activated_products_user_ids.append(correct_product.user_id)

    # Add product for users in incorrect, but not in correct
    product_user_ids = []
    for user_id in incorrect_user_ids:
        if user_id not in correct_user_ids:
            product = Product(
                user_id=user_id,
                vertical_id=args["vertical_id"],
                minutes=args["minutes"],
                price=args["correct_price"],
            )
            product_user_ids.append(user_id)
            if not args["dry_run"]:
                db.session.add(product)

    log.info(
        f"{args['dry_run_text']}Products activated for the following users",
        user_ids=activated_products_user_ids,
    )
    log.info(
        f"{args['dry_run_text']}Products added for the following users",
        user_ids=product_user_ids,
    )

    # Run the updates
    if not args["dry_run"]:
        db.session.commit()

    return


# Fix the records in the invoice and fee_accounting_entry
def export_incorrect_invoices_fees(args):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    sql = """SELECT user.id AS user_id, user.first_name, user.last_name, 
            prod.id AS prod_id, appt.id AS appt_id, 
            DATE(appt.scheduled_start) AS appt_date,
            fae.amount AS fae_amt, inv.id AS inv_id, 
            DATE(inv.started_at) AS inv_started,
            DATE(inv.completed_at) AS inv_completed,
            pae.amount AS pae_amount, pae.amount_captured as pae_captured
            FROM product prod
            JOIN user ON user.id = prod.user_id
            LEFT JOIN appointment appt ON appt.product_id = prod.id
            LEFT JOIN fee_accounting_entry fae ON fae.appointment_id = appt.id
            LEFT JOIN invoice inv ON inv.id = fae.invoice_id
            LEFT JOIN payment_accounting_entry pae ON pae.appointment_id = appt.id
            WHERE prod.vertical_id = :vertical_id
            AND prod.price = :price
            AND prod.minutes = :minutes
            AND prod.created_at >= :start_date
            AND appt.id IS NOT NULL
            AND appt.cancelled_at IS NULL
            ORDER BY user.first_name, user.last_name, user.id"""
    results = db.session.execute(
        sql,
        {
            "vertical_id": args["vertical_id"],
            "price": args["incorrect_price"],
            "minutes": args["minutes"],
            "start_date": args["start_date"],
        },
    ).fetchall()

    csv_writer = csv.writer(stdout)
    csv_writer.writerow(
        [
            "user_id",
            "first_name",
            "last_name",
            "prod_id",
            "appt_id",
            "appt_date",
            "fae_amt",
            "inv_id",
            "inv_started",
            "inv_completed",
            "pae_amount",
            "pae_captured",
        ]
    )
    for result in results:
        csv_writer.writerow(result)
    return


# Are the values set and in the correct format?
def validate_args(args):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    has_error = False
    try:
        int(args["vertical_id"])
    except:  # noqa  B001  TODO:  Do not use bare `except:`, it also catches unexpected events like memory errors, interrupts, system exit, and so on.  Prefer `except Exception:`.  If you're sure what you're doing, be explicit and write `except BaseException:`.
        log.error("Invalid vertial_id")
        has_error = True
    try:
        float(args["incorrect_price"])
    except:  # noqa  B001  TODO:  Do not use bare `except:`, it also catches unexpected events like memory errors, interrupts, system exit, and so on.  Prefer `except Exception:`.  If you're sure what you're doing, be explicit and write `except BaseException:`.
        log.error("Invalid incorrect_price")
        has_error = True
    try:
        float(args["correct_price"])
    except:  # noqa  B001  TODO:  Do not use bare `except:`, it also catches unexpected events like memory errors, interrupts, system exit, and so on.  Prefer `except Exception:`.  If you're sure what you're doing, be explicit and write `except BaseException:`.
        log.error("Invalid correct_price")
        has_error = True
    try:
        int(args["minutes"])
    except:  # noqa  B001  TODO:  Do not use bare `except:`, it also catches unexpected events like memory errors, interrupts, system exit, and so on.  Prefer `except Exception:`.  If you're sure what you're doing, be explicit and write `except BaseException:`.
        log.error("Invalid minutes")
        has_error = True
    try:
        args["start_date"] = datetime.strptime(args["start_date"], "%Y-%m-%d")
    except:  # noqa  B001  TODO:  Do not use bare `except:`, it also catches unexpected events like memory errors, interrupts, system exit, and so on.  Prefer `except Exception:`.  If you're sure what you're doing, be explicit and write `except BaseException:`.
        log.error("Invalid start_date")
        has_error = True
    if "dry_run" in args:
        try:
            args["dry_run"] = bool(args["dry_run"])
        except:  # noqa  B001  TODO:  Do not use bare `except:`, it also catches unexpected events like memory errors, interrupts, system exit, and so on.  Prefer `except Exception:`.  If you're sure what you're doing, be explicit and write `except BaseException:`.
            log.error("Invalid dry_run")
            has_error = True
    else:
        args["dry_run"] = True

    # Dry run? Set text
    args["dry_run_text"] = "[Dry Run] " if args["dry_run"] else ""

    # Return updated args or exit
    if has_error:
        log.error("Error validating arguments", args=args)
        exit("Fatal Argument Error")
    else:
        return args


# Create fees for appointments with the total difference between current appointment price and correct_product_price
def create_fee_for_appointments(  # type: ignore[no-untyped-def] # Function is missing a type annotation
    appt_ids, correct_product_price, fee_backdate, current_month_date, args
):
    by_practitioner = defaultdict(int)
    appts = db.session.query(Appointment).filter(Appointment.id.in_(appt_ids)).all()

    for appt in appts:
        existing_fee = (
            db.session.query(FeeAccountingEntry)
            .filter(FeeAccountingEntry.appointment_id == appt.id)
            .first()
        )

        if not existing_fee:
            log.info(
                "Appointment has not started yet so it does not have a fee.",
                appt_id=appt.id,
            )
            continue

        log.info(
            f"Appointment ID: {appt.id}, Product ID: {appt.product_id}, Prac ID: {appt.practitioner.id}"
            f", Existing Fee Amount: {existing_fee.amount}"
        )

        amount_diff = correct_product_price - existing_fee.amount
        if amount_diff == 0:
            log.error("Appointment is already the expected price")
            continue
        if amount_diff < 0:
            log.error("Appointment was more than the expected price")
            continue

        # for fees this month, we just want to issue a separate fee to account for the difference to be paid at the end
        # of this month's cycle. for fees before this month, aggregate them into a single fee to be paid out now
        if existing_fee.created_at >= current_month_date:
            fae = FeeAccountingEntry(
                amount=amount_diff,
                practitioner_id=appt.practitioner.id,
                type=FeeAccountingEntryTypes.ONE_OFF,
            )
            log.info("Fee added: ", fae=fae)

            if not args["dry_run"]:
                db.session.add(fae)
                db.session.commit()
        else:
            by_practitioner[appt.practitioner.id] += amount_diff

    for prac_id, amount in by_practitioner.items():
        fae = FeeAccountingEntry(
            amount=amount,
            practitioner_id=prac_id,
            type=FeeAccountingEntryTypes.ONE_OFF,
            created_at=fee_backdate,
        )
        log.info("Fee added: ", fae=fae)

        if not args["dry_run"]:
            db.session.add(fae)
            db.session.commit()

            practitioner = User.query.get(prac_id)

            inv = Invoice()
            inv.recipient_id = practitioner.practitioner_profile.stripe_account_id
            inv.add_entry(fae)

            db.session.add(inv)
            db.session.commit()
            log.info("Invoice created: ", inv=inv)
