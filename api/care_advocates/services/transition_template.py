from __future__ import annotations

from typing import Dict

import ddtrace

from care_advocates.repository.transition_template import (
    CareAdvocateMemberTransitionTemplateRepository,
)
from storage.unit_of_work import SQLAlchemyUnitOfWork

__all__ = ("CareAdvocateMemberTransitionTemplateService",)


class CareAdvocateMemberTransitionTemplateService:
    @staticmethod
    def uow() -> SQLAlchemyUnitOfWork[CareAdvocateMemberTransitionTemplateRepository]:
        return SQLAlchemyUnitOfWork(CareAdvocateMemberTransitionTemplateRepository)

    @ddtrace.tracer.wrap()
    def get_all_message_types(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        with self.uow() as uow:
            transition_templates = uow.get_repo(
                CareAdvocateMemberTransitionTemplateRepository
            ).all()
            message_types = [tt.message_type for tt in transition_templates]
            return message_types

    def get_message_templates_dict(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        with self.uow() as uow:
            templates = uow.get_repo(
                CareAdvocateMemberTransitionTemplateRepository
            ).all()
            message_templates = {
                message_template.message_type: message_template
                for message_template in templates
            }
            return message_templates

    def _get_paragraph_preview(  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self, paragraph, min_preview_length=150, max_preview_length=160
    ):
        # If the paragraph is too short, return the whole thing
        if len(paragraph) <= min_preview_length:
            return paragraph

        # Else, cut it in next space found after min_preview_length
        space_pos = paragraph.find(" ", min_preview_length)
        if space_pos != -1:
            # If we found a space, we need to check if it's before or after max_preview_length
            if space_pos < max_preview_length:
                return paragraph[:space_pos] + "..."
            else:
                return paragraph[:max_preview_length] + "..."
        else:
            # If we didn't find a space, we return either the whole paragraph or up to max_preview_length
            if max_preview_length < len(paragraph):
                return paragraph[:max_preview_length] + "..."
            else:
                return paragraph

    @ddtrace.tracer.wrap()
    def get_transition_templates_data(
        self,
        sort_column: str,
        transition_templates_edit_url: str,
    ) -> list[Dict]:

        """
        Params:
            sort_column: used to sort transition templates
            transition_templates_edit_url: template url to edit transition_templates, url should be something like "/admin/ca_member_transition_templates/edit/?id=_id_", so we should replace _id_ by each transition templates id
        """

        with self.uow() as uow:
            transition_templates = uow.get_repo(
                CareAdvocateMemberTransitionTemplateRepository
            ).all(sort_column)

            transition_templates_data = [
                {
                    "id": tt.id,
                    "message_type": tt.message_type,
                    "message_description": tt.message_description,
                    "message_body": self._get_paragraph_preview(tt.message_body),
                    "EditURL": transition_templates_edit_url.replace(
                        "_id_", str(tt.id)
                    ),
                }
                for tt in transition_templates
            ]
            return transition_templates_data
