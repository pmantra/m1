import csv

from models.medications import Medication
from storage.connection import db


def seed_medications():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    with open("utils/migrations/seed_medications_ndc_list.csv") as csv_file:
        reader = csv.DictReader(csv_file)
        count = 0
        failures = []
        for row in reader:
            print(row["PROPRIETARYNAME"])
            try:
                args = {
                    "product_id": row["PRODUCTID"],
                    "product_ndc": row["PRODUCTNDC"],
                    "product_type_name": row["PRODUCTTYPENAME"],
                    "proprietary_name": row["PROPRIETARYNAME"],
                    "proprietary_name_suffix": row["PROPRIETARYNAMESUFFIX"],
                    "nonproprietary_name": row["NONPROPRIETARYNAME"],
                    "dosage_form_name": row["DOSAGEFORMNAME"],
                    "route_name": row["ROUTENAME"],
                    "labeler_name": row["LABELERNAME"],
                    "substance_name": row["SUBSTANCENAME"],
                    "pharm_classes": row["PHARM_CLASSES"],
                    "dea_schedule": row["DEASCHEDULE"],
                    "listing_record_certified_through": row[
                        "LISTING_RECORD_CERTIFIED_THROUGH"
                    ],
                }
                db.session.add(Medication(**args))
                db.session.commit()
                count += 1
            except Exception:
                failures.append(row["PROPRIETARYNAME"])
        print(f"added {count} medications!")
        if failures:
            print(f"failed to add: {failures}")
