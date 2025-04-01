from typing import Type

from admin.views.base import AdminCategory, AdminViewT, MavenAuditedView
from models.medications import Medication
from storage.connection import RoutingSQLAlchemy, db


class MedicationView(MavenAuditedView):
    read_permission = "read:medication"
    delete_permission = "delete:medication"
    create_permission = "create:medication"

    column_list = (
        "proprietary_name",
        "nonproprietary_name",
        "product_id",
        "product_ndc",
        "product_type_name",
        "proprietary_name_suffix",
        "dosage_form_name",
        "route_name",
        "labeler_name",
        "substance_name",
        "pharm_classes",
        "dea_schedule",
        "listing_record_certified_through",
    )

    @classmethod
    def factory(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        cls: Type[AdminViewT],
        *,
        session: RoutingSQLAlchemy = None,  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "RoutingSQLAlchemy")
        category: AdminCategory = None,  # type: ignore[assignment] # Incompatible default for argument "category" (default has type "None", argument has type "AdminCategory")
        name: str = None,  # type: ignore[assignment] # Incompatible default for argument "name" (default has type "None", argument has type "str")
        endpoint: str = None,  # type: ignore[assignment] # Incompatible default for argument "endpoint" (default has type "None", argument has type "str")
        **kwargs,
    ) -> AdminViewT:
        return cls(  # type: ignore[call-arg] # Too many arguments for "object" #type: ignore[call-arg] # Unexpected keyword argument "category" for "object" #type: ignore[call-arg] # Unexpected keyword argument "name" for "object" #type: ignore[call-arg] # Unexpected keyword argument "endpoint" for "object"
            Medication,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )
