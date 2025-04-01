from __future__ import annotations

from typing import List

from sqlalchemy.orm.scoping import scoped_session

from authn.models.user import User
from common import stats
from providers.models.need import Need
from providers.repository.need import NeedRepository
from providers.service.promoted_needs.get_needs_config import (
    get_config,
    get_member_active_track_name,
)
from storage import connection
from utils.log import logger

log = logger(__name__)


class NeedService:
    def __init__(
        self,
        session: scoped_session = None,  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "scoped_session")
    ):
        self.session = session or connection.db.session
        self.need_repository = NeedRepository(session=self.session)

    def get_needs_by_slugs(self, need_slugs: List[str]) -> List[Need]:
        return self.need_repository.get_needs_by_slugs(need_slugs=need_slugs)

    def get_need_slugs_by_member(self, user: User) -> List[str]:
        needs_configuration = get_config()
        # within the 'data' key consists a mapping between user track and need slugs
        data = needs_configuration.get("data")

        track_name = get_member_active_track_name(user)

        if not track_name:
            return []

        needs_by_track: List[str] = data.get(track_name, [])

        log.info(
            "Found needs based on member's track",
            user=user.id,
            domain="promoted_needs",
            pod=stats.PodNames.CARE_DISCOVERY,
            track_name=track_name,
            needs_by_track=needs_by_track,
        )

        return needs_by_track

    def sort_needs_by_need_slug_order(
        self, needs: List[Need], need_slugs: List[str]
    ) -> List[Need]:
        if len(needs) == 0 or len(need_slugs) == 0:
            return []

        ordered_needs = []
        slug_need_mapping = {need.slug: need for need in needs}
        for index, need_slug in enumerate(need_slugs):
            target_need = slug_need_mapping.get(need_slug)
            if target_need:
                ordered_needs.append(
                    Need(
                        id=target_need.id,
                        name=target_need.name,
                        description=target_need.description,
                        slug=target_need.slug,
                        display_order=index + 1,
                    )
                )

        return ordered_needs

    def get_needs_by_member(self, user: User) -> List[Need]:
        """
        Follows logic specified by promoted needs project
        TLDR, we return top 3 needs depending on member's track in priority order
        """
        need_slugs = self.get_need_slugs_by_member(user)
        needs = self.get_needs_by_slugs(need_slugs=need_slugs)
        return self.sort_needs_by_need_slug_order(needs=needs, need_slugs=need_slugs)

    def get_needs_by_ids(self, need_ids: List[int]) -> List[Need]:
        return self.need_repository.get_needs_by_ids(need_ids=need_ids)
