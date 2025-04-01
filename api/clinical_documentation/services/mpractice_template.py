from __future__ import annotations

from typing import List, Optional, Tuple

from sqlalchemy.orm.scoping import ScopedSession

from authn.models.user import User
from clinical_documentation.error import DuplicateTitleError
from clinical_documentation.models.mpractice_template import (
    MPracticeTemplate,
    MPracticeTemplateLitePagination,
    PostMPracticeTemplate,
)
from clinical_documentation.repository.mpractice_template import (
    MPracticeTemplateRepository,
)
from storage.connection import db
from utils.log import logger

log = logger(__name__)


class MPracticeTemplateService:
    def __init__(
        self,
        session: ScopedSession | None = None,
        mpractice_template_repo: MPracticeTemplateRepository | None = None,
    ):
        self.session = session or db.session

        self.mpractice_template_repo = (
            mpractice_template_repo or MPracticeTemplateRepository(session=self.session)
        )

    def get_sorted_mpractice_templates(
        self, user: User
    ) -> Tuple[List[MPracticeTemplate], MPracticeTemplateLitePagination]:
        templates = self.mpractice_template_repo.get_mpractice_templates_by_owner(
            owner_id=user.id
        )
        count = len(templates)
        pagination = MPracticeTemplateLitePagination(
            order_direction="asc",
            total=count,
        )
        if not templates or not count:
            log.warn(f"User {user.id} has no templates")
            return [], pagination

        return templates, pagination

    def create_mpractice_template(
        self, user: User, template_args: PostMPracticeTemplate
    ) -> MPracticeTemplate | None:
        template_with_same_name = (
            self.mpractice_template_repo.get_mpractice_templates_by_title(
                owner_id=user.id,
                title=template_args.title,
            )
        )

        if template_with_same_name:
            raise DuplicateTitleError(
                f"Template with title {template_args.title} already exists, belonging to user {template_with_same_name.owner_id} and marked as is_global {template_with_same_name.is_global}"
            )

        template = self.mpractice_template_repo.create_mpractice_template(
            owner_id=user.id,
            title=template_args.title,
            text=template_args.text,
            sort_order=template_args.sort_order,
            is_global=template_args.is_global,
        )

        if not template:
            log.warn(f"Could not create template for user {user.id}")
            return None

        self.session.commit()
        return template

    def edit_mpractice_template_by_id(
        self,
        user: User,
        template_id: int,
        title: Optional[str],
        text: Optional[str],
        # sort_order: int,
        # is_global: bool,
    ) -> MPracticeTemplate | None:
        if title:
            template_with_same_name = (
                self.mpractice_template_repo.get_mpractice_templates_by_title(
                    owner_id=user.id,
                    title=title,
                )
            )

            if template_with_same_name:
                raise DuplicateTitleError(
                    f"Template with title {title} already exists, belonging to user {template_with_same_name.owner_id} and marked as is_global {template_with_same_name.is_global}"
                )

        template = self.mpractice_template_repo.edit_mpractice_template_by_id(
            owner_id=user.id,
            template_id=template_id,
            title=title or None,
            text=text or None,
            # sort_order=sort_order or None,
            # is_global=is_global or None,
        )

        if not template:
            log.warn(
                f"Could not edit mpractice template {template_id} for user {user.id}"
            )
            return None
        else:
            self.session.commit()

        return template

    def delete_mpractice_template_by_id(self, user: User, template_id: int) -> bool:
        success = self.mpractice_template_repo.delete_mpractice_template_by_id(
            owner_id=user.id,
            template_id=template_id,
        )

        if not success:
            log.warn(
                f"Could not delete mpractice template {template_id} for user {user.id}"
            )
        else:
            self.session.commit()

        return success
