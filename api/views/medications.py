from flask import request
from flask_restful import abort

from common.services.api import AuthenticatedResource
from models.medications import Medication


class MedicationsResource(AuthenticatedResource):
    def get(self) -> dict:  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if not request.args.get("query_string"):
            abort(400, message="Missing query string")

        matches = (
            Medication.query.with_entities(Medication.proprietary_name)
            .filter(
                Medication.proprietary_name.ilike(request.args["query_string"] + "%")
            )
            .all()
        )

        return {"data": [m.proprietary_name for m in matches]}
