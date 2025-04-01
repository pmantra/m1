from typing import Type

from flask_admin.form import rules
from sqlalchemy import func

from admin.views.base import AdminCategory, AdminViewT, MavenAuditedView
from models.profiles import State
from models.verticals_and_specialties import Vertical
from provider_matching.models.in_state_matching import VerticalInStateMatching
from storage.connection import db
from storage.connector import RoutingSQLAlchemy
from utils.log import logger

log = logger(__name__)


class InStateMatchingView(MavenAuditedView):
    read_permission = "read:in-state-match"
    create_permission = "create:in-state-match"
    edit_permission = "edit:in-state-match"

    column_list = (
        "name",
        "in_state_matching_states",
    )

    column_labels = {
        "name": "Vertical",
        "in_state_matching_states": "States with In-State Match",
    }

    column_default_sort = "name"

    column_searchable_list = ["name"]

    form_rules = [
        rules.Field("name"),
        rules.Field("in_state_matching_states"),
    ]

    form_widget_args = {
        "name": {
            "readonly": True,
        }
    }

    form_args = {
        "in_state_matching_states": {
            # This allows us to define the ordering that is used by the multi-select widget
            # on the edit page. By default, State.id would be used if we didn't do this.
            "query_factory": lambda: (State.query.order_by(State.abbreviation)),
        }
    }

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
            Vertical,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )

    def get_query(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return Vertical.query.filter_by(filter_by_state=True)

    def get_count_query(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        # As per Flask admin documentation:
        #
        #   A ``query(self.model).count()`` approach produces an excessive
        #   subquery, so ``query(func.count('*'))`` should be used instead.
        return (
            self.session.query(func.count("*"))
            .select_from(self.model)
            .filter_by(filter_by_state=True)
        )

    def get_list(self, page, sort_field, sort_desc, search, filters, page_size=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        vertical_list = super().get_list(
            page, sort_field, sort_desc, search, filters, page_size
        )
        count, verticals = vertical_list

        # We could sort the states via `column_sortable_list`, but that would give the user
        # the option to toggle sort/reverse sort for this column on the fly. We want the
        # states to always appear alphabetically, so we'll manually sort.
        for vertical in verticals:
            vertical.in_state_matching_states = sorted(
                vertical.in_state_matching_states, key=lambda state: state.abbreviation
            )

        return count, verticals

    def on_model_change(self, form, model, is_created: bool):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        super().on_model_change(form, model, is_created)
        if in_state_matching_states := form.in_state_matching_states.data:
            # Make sure there is a VerticalInStateMatching for each of the selected VerticalInStateMatchingState
            for in_state_matching_state in in_state_matching_states:
                visms = VerticalInStateMatching.query.filter_by(
                    vertical_id=model.id,
                    subdivision_code=f"US-{in_state_matching_state.abbreviation}",
                ).one_or_none()

                if not visms:
                    model.in_state_matching_subdivisions.append(
                        f"US-{in_state_matching_state.abbreviation}"
                    )

            subdivision_codes = {
                f"US-{isms.abbreviation}" for isms in in_state_matching_states
            }
            for in_state_matching_subdivision in model.in_state_matching:
                if (
                    in_state_matching_subdivision.subdivision_code
                    not in subdivision_codes
                ):
                    db.session.delete(in_state_matching_subdivision)

        else:
            # Delete all VerticalInStateMatching if there are none selected when saving
            for vism in model.in_state_matching:
                db.session.delete(vism)
