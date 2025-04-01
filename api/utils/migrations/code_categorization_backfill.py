import csv

from models.referrals import ReferralCode, ReferralCodeSubCategory
from storage.connection import db


def backfill_code_categorization():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    with open("utils/migrations/code_categorization_backfill.csv") as csvfile:
        errors = []
        reader = csv.DictReader(csvfile)
        for row in reader:
            code = (
                db.session.query(ReferralCode)
                .filter(ReferralCode.code == row["code"])
                .one_or_none()
            )
            if code is None:
                message = f"Code {row['code']} not found! Skipping..."
                print(message)
                errors.append(message)
                continue

            subcategory = (
                db.session.query(ReferralCodeSubCategory)
                .filter(
                    ReferralCodeSubCategory.category_name == row["category"],
                    ReferralCodeSubCategory.name == row["subcategory"],
                )
                .one_or_none()
            )
            if subcategory is None:
                message = "Subcategory not found: {},{}".format(
                    row["category"], row["subcategory"]
                )
                print(message)
                errors.append(message)
                continue

            if len(code.values) != 1:
                for v in code.values:
                    if v.for_user_type == "member":
                        value = v
                        break
                else:
                    message = f"Could not determine value for code: {code}"
                    print(message)
                    errors.append(message)
                    continue
            else:
                value = code.values[0]

            if row["activity"]:
                code.activity = row["activity"]

            if row["payment_rep"]:
                value.payment_rep = row["payment_rep"]

            if row["payment_user"]:
                value.payment_user = row["payment_user"]

            if row["rep_email"]:
                value.rep_email_address = row["rep_email"]

            if row["user_payment_type"]:
                value.user_payment_type = row["user_payment_type"]

            if row["total_code_cost"]:
                code.total_code_cost = row["total_code_cost"]

            code.subcategory = subcategory
            db.session.commit()

        if errors:
            print("Done, with errors: {}".format("\n".join(errors)))
        else:
            print("Done! No errors")
