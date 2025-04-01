from typing import Type

from sqlalchemy import func

from admin.views.base import AdminCategory, AdminViewT, ContainsFilter, MavenAuditedView
from models.phone import BlockedPhoneNumber
from storage.connection import RoutingSQLAlchemy, db


class PhoneNumberFilter(ContainsFilter):
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        # We're going to strip the tel number of visual separators
        #   { "-" / "." / "(" / ")" },
        #   and see if that value contains the query,
        #   also stripped of visual separators.
        visual_separators = ["-", ".", "(", ")"]
        column = self.get_column(alias)
        value = value.replace(" ", "")  # ignore spaces in the query
        for sep in visual_separators:
            column = func.replace(column, sep, "")
            value = value.replace(sep, "")
        return query.filter(column.contains(value))


class BlockedPhoneNumberView(MavenAuditedView):
    read_permission = "read:blocked-phone-number"
    delete_permission = "delete:blocked-phone-number"
    create_permission = "create:blocked-phone-number"
    edit_permission = "edit:blocked-phone-number"
    column_searchable_list = (BlockedPhoneNumber.digits,)

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
            BlockedPhoneNumber,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )
