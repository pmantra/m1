from flask import request
from flask_restful import abort
from sqlalchemy import func, or_

from authn.domain.service import UserService
from common.services.api import AuthenticatedResource
from members.models.search import MemberSearchResult
from members.schemas.search import (
    MemberSearchResultsSchema,
    MemberSearchResultsSchemaV3,
)
from members.utils.member_access import get_member_access_by_practitioner
from models.profiles import MemberProfile
from providers.repository.provider import ProviderRepository
from storage.connection import db
from utils.marshmallow_experiment import marshmallow_experiment_enabled
from views.schemas.common import PaginableArgsSchema, PaginationInfoSchema
from views.schemas.common_v3 import PaginableArgsSchemaV3, PaginationInfoSchemaV3


class MemberSearchResource(AuthenticatedResource):
    """
    Search for members.

    A query param of `q` is the single term used to perform the search.

    If the `q` param is a number, it will be used to look up the member by their user_id.

    If the `q` param is not a number, the query will check the following fields using a `starts with` type query:
      * first_name
      * last_name
      * email

    The result of this function is a list of member info matching the provided `q` value, `data` along with `pagination` and `meta` objects.
    If no value for `q` is provided, an empty list is returned for the data list
    """

    def get(self):  # type: ignore[no-untyped-def]

        # launch darkly flag
        experiment_enabled = marshmallow_experiment_enabled(
            "experiment-marshmallow-member-search-resource",
            self.user.esp_id if self.user else None,
            self.user.email if self.user else None,
            default=False,
        )

        provider = ProviderRepository().get_by_user_id(user_id=self.user.id)
        results = []
        total_count = 0
        q = request.args.get("q")
        paginable_schema = (
            PaginableArgsSchemaV3() if experiment_enabled else PaginableArgsSchema()
        )
        args = (
            paginable_schema.load(request.args)  # type: ignore[attr-defined]
            if experiment_enabled
            else paginable_schema.load(request.args).data  # type: ignore[attr-defined]
        )
        limit = int(args.get("limit", 10))
        offset = int(args.get("offset", 0))
        order_asc = args.get("order_direction", "asc") == "asc"

        if provider and q and len(q) > 0:
            query = db.session.query(MemberProfile)
            if q.isdigit():
                query = query.filter(MemberProfile.user_id == int(q))
            else:
                formatted_string = q.replace(" ", "%").replace("-", "%")
                user_ids = self._get_user_ids_by_search_term(q)
                query = query.filter(
                    or_(
                        func.concat(
                            MemberProfile.first_name, MemberProfile.last_name
                        ).like(f"%{formatted_string}%"),
                        MemberProfile.user_id.in_(user_ids),
                    )
                )
            if not provider.is_cx:
                query = query.filter(
                    MemberProfile.user_id.in_(
                        get_member_access_by_practitioner(provider.user_id)
                    )
                )
            total_count = query.count()
            # don't execute a query that will take too long
            if total_count > 20000:
                abort(413, message="The results set would be too large")

            if order_asc:
                query = query.order_by(
                    MemberProfile.first_name, MemberProfile.last_name
                )
            else:
                query = query.order_by(
                    MemberProfile.first_name.desc(), MemberProfile.last_name.desc()
                )

            query = query.limit(limit)
            query = query.offset(offset)
            results = query.all()

        pagination_schema = (
            PaginationInfoSchemaV3() if experiment_enabled else PaginationInfoSchema()
        )
        pagination_schema.limit = limit  # type: ignore[assignment, attr-defined] # Incompatible types in assignment (expression has type "int", variable has type "Integer")
        pagination_schema.offset = offset  # type: ignore[assignment, attr-defined] # Incompatible types in assignment (expression has type "int", variable has type "Integer")
        pagination_schema.order_direction = "asc" if order_asc else "desc"  # type: ignore[assignment, attr-defined] # Incompatible types in assignment (expression has type "str", variable has type "OrderDirectionField")
        pagination_schema.total = total_count  # type: ignore[assignment, attr-defined] # Incompatible types in assignment (expression has type "int", variable has type "Integer")

        schema = (
            MemberSearchResultsSchemaV3()
            if experiment_enabled
            else MemberSearchResultsSchema()
        )
        schema.pagination = pagination_schema  # type: ignore[attr-defined]
        schema.context["user"] = self.user  # type: ignore[attr-defined]

        full_results = {
            "data": [MemberSearchResult(member_profile=m) for m in results],
            "pagination": pagination_schema,
        }
        return schema.dump(full_results)  # type: ignore[attr-defined]

    def _get_user_ids_by_search_term(self, q: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        """
        In order to search on email, we have to ask the UserService.
        Returns the user_ids for users that have an email that startswith the search term.
        """
        user_service = UserService()
        users = user_service.fetch_users(filters={"email_like": f"{q}%"})
        return [u.id for u in users]
