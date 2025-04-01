from flask import flash

from data_admin.maker_base import _MakerBase
from payer_accumulator.common import PayerName
from payer_accumulator.models.payer_list import Payer
from storage.connection import db


class PayerMaker(_MakerBase):
    def create_object(self, spec: dict, parent=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        required_params = [
            "name",
        ]
        missing_params = []
        for param in required_params:
            val = spec.get(param)
            if val is None:
                missing_params.append(param)

        if missing_params:
            raise ValueError(f"Missing param(s): {missing_params}")

        name = str(spec.get("name"))
        payer = Payer.query.filter(Payer.payer_name == PayerName(name)).one_or_none()
        if payer:
            flash(f"Payer {name} already existed.")
            return payer

        payer = Payer(payer_name=PayerName(name), payer_code=name.lower())

        db.session.add(payer)
        return payer
