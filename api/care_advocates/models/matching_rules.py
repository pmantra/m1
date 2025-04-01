from __future__ import annotations

import enum
from typing import List, Tuple

from ddtrace import tracer
from sqlalchemy import Boolean, Column, Enum, ForeignKey, Integer, String
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm import Query, backref, relationship

from audit_log.utils import emit_bulk_audit_log_create, emit_bulk_audit_log_delete
from authn.models.user import User
from common import stats
from models import base
from models.programs import Module
from models.tracks import TrackName
from storage.connection import db
from utils.log import logger

log = logger(__name__)

RISK_FACTOR_TRACKS = [TrackName.PREGNANCY.value, TrackName.FERTILITY.value]


class MatchingRuleType(enum.Enum):
    INCLUDE = "include"
    EXCLUDE = "exclude"


class MatchingRuleEntityType(enum.Enum):
    COUNTRY = "country"
    ORGANIZATION = "organization"
    MODULE = "module"
    USER_FLAG = "user_flag"


class MatchingRuleEntity(base.ModelBase):
    __tablename__ = "matching_rule_entity"

    matching_rule_id = Column(Integer, ForeignKey("matching_rule.id"), primary_key=True)

    entity_identifier = Column(String(120), primary_key=True)

    matching_rule = relationship(
        "MatchingRule", single_parent=True, cascade="all, delete-orphan"
    )


class MatchingRuleSet(base.TimeLoggedModelBase):
    from care_advocates.models.assignable_advocates import AssignableAdvocate

    __tablename__ = "matching_rule_set"

    id = Column(Integer, primary_key=True)
    assignable_advocate_id = Column(
        Integer, ForeignKey("assignable_advocate.practitioner_id", ondelete="CASCADE")
    )

    assignable_advocate = relationship(
        AssignableAdvocate, backref=backref("matching_rule_sets", cascade="all,delete")
    )
    matching_rules = relationship("MatchingRule", cascade="all")

    def replace_matching_rules(self, new_rules: List["MatchingRule"]):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        old_rules = self.matching_rules
        for mr in old_rules:
            db.session.delete(mr)

        db.session.add_all(new_rules)
        db.session.commit()
        emit_bulk_audit_log_delete(old_rules)
        emit_bulk_audit_log_create(new_rules)

        return new_rules

    @staticmethod
    def extract_ids(ids: List[Tuple[int]]) -> List[int]:
        return [id for (id,) in ids]

    @staticmethod
    def matching_rule_query_builder(
        q: Query,
        entity_type: MatchingRuleEntityType,
        rule_type: MatchingRuleType,
        entity_identifiers: List[str] = None,  # type: ignore[assignment] # Incompatible default for argument "entity_identifiers" (default has type "None", argument has type "List[str]")
        all: bool = False,
        previous_results: List[int] = None,  # type: ignore[assignment] # Incompatible default for argument "previous_results" (default has type "None", argument has type "List[int]")
    ) -> Query:
        q = q.filter(
            MatchingRule.entity == entity_type.value,
            MatchingRule.type == rule_type.value,
        )

        # If previous results is an empty list we need that to be honored.
        if previous_results is not None:
            q = q.filter(MatchingRule.matching_rule_set_id.in_(previous_results))

        if all:
            q = q.filter(MatchingRule.all == all)
        else:
            q = q.filter(MatchingRuleEntity.entity_identifier.in_(entity_identifiers))  # type: ignore[arg-type] # Argument 1 to "in_" of "ColumnOperators" has incompatible type "Optional[List[str]]"; expected "Union[Iterable[Any], BindParameter[Any], Select, Alias]"

        return q

    @classmethod
    def get_advocate_ids(cls, results: List[int]) -> List[int]:
        return (
            MatchingRuleSet.query.filter(
                MatchingRuleSet.id.in_(cls.extract_ids(results))  # type: ignore[arg-type] # Argument 1 to "extract_ids" of "MatchingRuleSet" has incompatible type "List[int]"; expected "List[Tuple[int]]"
            )
            .with_entities(MatchingRuleSet.assignable_advocate_id)
            .all()
        )

    @classmethod
    @tracer.wrap()
    def find_matches_for(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        cls,
        user: User,
        available_advocate_ids: List[int] | None = None,
        risk_factors=None,  # type: ignore[assignment] # Incompatible default for argument "available_advocate_ids" (default has type "None", argument has type "List[int]"),
        logs_to_emit_with_matched_ca: List[str] | None = None,
    ) -> List[AssignableAdvocate]:
        """
        Matching logic is inherently complex. We have implemented it as cleanly as we could for future mavens.
        The logic matching cascades down from country, to organization, to track, and finally user flags. In each
        case we collect the ids of the assignable advocates who have matching rules specified for those entities.
        In the case of country and organization we also have this concept of all. All means that the assignable
        advocate has the ability to serve all countries or all organizations. In addition to all, we have exclusions
        in organizations. Organization exclusions are used in addition to the organization “all: true” setting.
        If an assignable advocate can serve all organizations, we may want to exclude some specific organizations from
        their roster. User flags are intentionally nested under tracks as only the Pregnancy track will have high
        risk members.

        Risk factor user flags that override the users flags are used in this function

        logs_to_emit_with_matched_ca is an optional param that can be passed in to collect
        logs for later emission, so that our alerts can append information about the CA
        who is eventually matched to this user at the end of the process.
        """
        from care_advocates.models.assignable_advocates import AssignableAdvocate
        from tracks.service import TrackSelectionService

        if logs_to_emit_with_matched_ca is None:
            # In this case, these will just get dropped later, but this simplifies the code later on
            logs_to_emit_with_matched_ca = []

        country_code = user.country and user.country.alpha_2
        organization = user.organization
        track_service = TrackSelectionService()
        highest_priority_track = track_service.get_highest_priority_track(
            user.active_tracks
        )
        track_name = highest_priority_track.name  # type: ignore[union-attr] # Item "None" of "Optional[MemberTrack]" has no attribute "name"
        log.info(
            "Found highest priority track for user", user_id=user.id, track=track_name
        )

        # TODO: Replace Module for tracks in Matching Rules.
        # The Module model is deprecated. We would eventually like to use track names instead.
        # Nonetheless, making this change is not trivial given that Matching Rules are currently saved
        # using references to Modules ids. Hence, we would need to first migrate that data to use track names before
        # changing any matching rules logic, and before removing Module from the codebase.
        module = Module.query.filter_by(name=track_name).one_or_none()
        track_id = None
        if module:
            track_id = module.id
        else:
            # DD monitor: https://app.datadoghq.com/monitors/127857883
            log.warning("Could not find Module for track name", track_name=track_name)

        user_flags = risk_factors if risk_factors else user.current_risk_flags()

        if not organization and not track_name:
            raise ValueError(
                "track and organization are required for matching a member to an care advocate"
            )

        if not available_advocate_ids:
            return []

        aa_mrs_ids = (
            MatchingRuleSet.query.filter(
                MatchingRuleSet.assignable_advocate_id.in_(available_advocate_ids)
            )
            .with_entities(MatchingRuleSet.id)
            .subquery()
        )

        # Only grab matching rule sets with advocate ids from list.
        matched = (
            db.session.query(MatchingRule.matching_rule_set_id)
            .filter(MatchingRule.matching_rule_set_id.in_(aa_mrs_ids))
            .outerjoin(MatchingRuleEntity)
        )

        results = None

        log.info(
            "ca member matching - attempting to find matches",
            user_id=user.id,
            country=country_code,
            organization=organization,
            track=track_name,
            user_flags=user_flags,
            in_advocate_ids=available_advocate_ids,
        )

        if country_code:
            results = cls.matching_rule_query_builder(
                q=matched,
                entity_type=MatchingRuleEntityType.COUNTRY,
                rule_type=MatchingRuleType.INCLUDE,
                entity_identifiers=[country_code],
            ).all()

            if not results:
                log.info(
                    "ca member matching - attempting to find matches -- user had no country match, checking advocates with any country",
                    user_id=user.id,
                    country=country_code,
                    organization=organization,
                    track=track_name,
                    user_flags=user_flags,
                )
                results = cls.matching_rule_query_builder(
                    q=matched,
                    entity_type=MatchingRuleEntityType.COUNTRY,
                    rule_type=MatchingRuleType.INCLUDE,
                    all=True,
                ).all()

        # Members who do not have a country defined will be matched with assignable advocates that have country: Any.
        if not country_code:
            log.info(
                "ca member matching - attempting to find matches -- user had no country",
                user_id=user.id,
                country=country_code,
                organization=organization,
                track=track_name,
                user_flags=user_flags,
            )
            results = cls.matching_rule_query_builder(
                q=matched,
                entity_type=MatchingRuleEntityType.COUNTRY,
                rule_type=MatchingRuleType.INCLUDE,
                all=True,
            ).all()

        log.info(
            "ca member matching - attempting to find matches -- advocates with country",
            user_id=user.id,
            country=country_code,
            organization=organization,
            track=track_name,
            user_flags=user_flags,
            in_advocate_ids=cls.get_advocate_ids(results),  # type: ignore[arg-type] # Argument 1 to "get_advocate_ids" of "MatchingRuleSet" has incompatible type "Optional[List[Any]]"; expected "List[int]"
        )

        if organization:
            ids = cls.extract_ids(results)  # type: ignore[arg-type] # Argument 1 to "extract_ids" of "MatchingRuleSet" has incompatible type "Optional[List[Any]]"; expected "List[Tuple[int]]"
            results = cls.matching_rule_query_builder(
                q=matched,
                entity_type=MatchingRuleEntityType.ORGANIZATION,
                rule_type=MatchingRuleType.INCLUDE,
                entity_identifiers=[str(organization.id)],
                previous_results=ids,
            ).all()

            if not results:
                log.info(
                    "ca member matching - attempting to find matches -- user had no org match, checking advocates with any org",
                    user_id=user.id,
                    country=country_code,
                    organization=organization,
                    track=track_name,
                    user_flags=user_flags,
                )
                excluded = cls.matching_rule_query_builder(
                    q=matched,
                    entity_type=MatchingRuleEntityType.ORGANIZATION,
                    rule_type=MatchingRuleType.EXCLUDE,
                    entity_identifiers=[str(organization.id)],
                    previous_results=ids,
                ).subquery()

                results = (
                    cls.matching_rule_query_builder(
                        q=matched,
                        entity_type=MatchingRuleEntityType.ORGANIZATION,
                        rule_type=MatchingRuleType.INCLUDE,
                        all=True,
                        previous_results=ids,
                    )
                    .filter(~MatchingRule.matching_rule_set_id.in_(excluded))
                    .all()
                )

            log.info(
                "ca member matching - attempting to find matches -- advocates with org",
                user_id=user.id,
                country=country_code,
                organization=organization,
                track=track_name,
                user_flags=user_flags,
                in_advocate_ids=cls.get_advocate_ids(results),
            )

        if track_id:
            ids = cls.extract_ids(results)  # type: ignore[arg-type] # Argument 1 to "extract_ids" of "MatchingRuleSet" has incompatible type "Optional[List[Any]]"; expected "List[Tuple[int]]"

            results = cls.matching_rule_query_builder(
                q=matched,
                entity_type=MatchingRuleEntityType.MODULE,
                rule_type=MatchingRuleType.INCLUDE,
                entity_identifiers=[str(track_id)],
                previous_results=ids,
            ).all()

            log.info(
                "ca member matching - attempting to find matches -- advocates with track",
                user_id=user.id,
                country=country_code,
                organization=organization,
                track=track_name,
                user_flags=user_flags,
                in_advocate_ids=cls.get_advocate_ids(results),
            )

            if results:
                # There are 3 cases for user flags, none, any, some
                if track_name in RISK_FACTOR_TRACKS:
                    if user_flags:
                        ids = cls.extract_ids(results)
                        # some
                        results = cls.matching_rule_query_builder(
                            q=matched,
                            entity_type=MatchingRuleEntityType.USER_FLAG,
                            rule_type=MatchingRuleType.INCLUDE,
                            entity_identifiers=[str(u.id) for u in user_flags],
                            previous_results=ids,
                        ).all()

                        # any
                        if not results:
                            log.info(
                                "ca member matching - attempting to find matches -- user had no risk factor match, checking advocates with any risk factor",
                                user_id=user.id,
                                country=country_code,
                                organization=organization,
                                track=track_name,
                                user_flags=user_flags,
                            )
                            logs_to_emit_with_matched_ca.append(
                                "ca member matching - attempting to find matches -- user had no risk factor match, checking advocates with any risk factor"
                            )
                            results = cls.matching_rule_query_builder(
                                q=matched,
                                entity_type=MatchingRuleEntityType.USER_FLAG,
                                rule_type=MatchingRuleType.INCLUDE,
                                all=True,
                                previous_results=ids,
                            ).all()

                    # none
                    if not user_flags:
                        log.info(
                            "ca member matching - attempting to find matches -- user had no risk factors, checking advocates with no risk factors",
                            user_id=user.id,
                            country=country_code,
                            organization=organization,
                            track=track_name,
                            user_flags=user_flags,
                        )
                        ids = cls.extract_ids(results)
                        results = cls.matching_rule_query_builder(
                            q=matched,
                            entity_type=MatchingRuleEntityType.USER_FLAG,
                            rule_type=MatchingRuleType.EXCLUDE,
                            all=True,
                            previous_results=ids,
                        ).all()

                    log.info(
                        "ca member matching - attempting to find matches -- advocates with risk factors",
                        user_id=user.id,
                        country=country_code,
                        organization=organization,
                        track=track_name,
                        user_flags=user_flags,
                        in_advocate_ids=cls.get_advocate_ids(results),
                    )

        if not results:
            stats.increment(
                metric_name="api.care_advocate_matching.models.matching_rules.find_matches_for",
                pod_name=stats.PodNames.CARE_DISCOVERY,
                tags=["error:true", "error_cause:no_match"],
            )
            log.info(
                "ca member matching - no assignable_advocates matching given criteria",
                user_id=user.id,
                country=country_code,
                organization=organization,
                track=track_name,
                user_flags=user_flags,
            )
            return []

        matching_rule_sets_query = MatchingRuleSet.query.filter(
            MatchingRuleSet.id.in_(cls.extract_ids(results))
        )

        return AssignableAdvocate.query.filter(
            AssignableAdvocate.practitioner_id.in_(
                matching_rule_sets_query.with_entities(
                    MatchingRuleSet.assignable_advocate_id
                ).subquery()
            )
        ).all()

    @classmethod
    @tracer.wrap()
    def find_matches_for_catch_all(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        cls, user: User, available_advocate_ids: List[int] = None, risk_factors=None  # type: ignore[assignment] # Incompatible default for argument "available_advocate_ids" (default has type "None", argument has type "List[int]")
    ) -> List[AssignableAdvocate]:
        """
        This is intended as a secondary option to the find_matches_for member matching. If no matches are found, we want
        to reconsider the "catch all" advocates -- defined here as `any country, any org, no exceptions, and any OR
        specific track matches`. We match on track here because we still want to prioritize track if possible since
        there exists few advocates who can handle any track. The reason these advocates are missed initially is because
        the cascading algorithm in find_matches_for does not allow for advocates with `any` in a certain rule to be
        captured with those who have a specific rule match. For example, an advocate can match on country India which
        then ignores those with country any. This can possibly lead to a "dead end" if the India advocate match does not
        then match on org or track.
        """
        from care_advocates.models.assignable_advocates import AssignableAdvocate

        country_code = user.country and user.country.alpha_2
        organization = user.organization
        track_name = user.current_member_track.name
        module = Module.query.filter_by(name=track_name).one_or_none()
        track_id = None
        if module:
            track_id = module.id
        user_flags = risk_factors if risk_factors else user.current_risk_flags()

        if not organization and not track_name:
            raise ValueError(
                "track and organization are required for matching a member to an care advocate"
            )

        if not available_advocate_ids:
            return []

        aa_mrs_ids = (
            MatchingRuleSet.query.filter(
                MatchingRuleSet.assignable_advocate_id.in_(available_advocate_ids)
            )
            .with_entities(MatchingRuleSet.id)
            .subquery()
        )

        # Only grab matching rule sets with advocate ids from list.
        matched = (
            db.session.query(MatchingRule.matching_rule_set_id)
            .filter(MatchingRule.matching_rule_set_id.in_(aa_mrs_ids))
            .outerjoin(MatchingRuleEntity)
        )

        log.info(
            "catch all ca member matching - attempting to find matches",
            user_id=user.id,
            country=country_code,
            organization=organization,
            track=track_name,
            user_flags=user_flags,
            in_advocate_ids=available_advocate_ids,
        )

        results = cls.matching_rule_query_builder(
            q=matched,
            entity_type=MatchingRuleEntityType.COUNTRY,
            rule_type=MatchingRuleType.INCLUDE,
            all=True,
        ).all()

        if organization:
            ids = cls.extract_ids(results)

            excluded = cls.matching_rule_query_builder(
                q=matched,
                entity_type=MatchingRuleEntityType.ORGANIZATION,
                rule_type=MatchingRuleType.EXCLUDE,
                entity_identifiers=[str(organization.id)],
                previous_results=ids,
            ).subquery()

            results = (
                cls.matching_rule_query_builder(
                    q=matched,
                    entity_type=MatchingRuleEntityType.ORGANIZATION,
                    rule_type=MatchingRuleType.INCLUDE,
                    all=True,
                    previous_results=ids,
                )
                .filter(~MatchingRule.matching_rule_set_id.in_(excluded))
                .all()
            )

        if track_id:
            ids = cls.extract_ids(results)

            results = cls.matching_rule_query_builder(
                q=matched,
                entity_type=MatchingRuleEntityType.MODULE,
                rule_type=MatchingRuleType.INCLUDE,
                entity_identifiers=[str(track_id)],
                previous_results=ids,
            ).all()

            # User flags for catch all CAs is any OR none
            # theoretically we can remove this but leaving it here for now for clarity
            if track_name in RISK_FACTOR_TRACKS:
                ids = cls.extract_ids(results)

                # any
                results = cls.matching_rule_query_builder(
                    q=matched,
                    entity_type=MatchingRuleEntityType.USER_FLAG,
                    rule_type=MatchingRuleType.INCLUDE,
                    all=True,
                    previous_results=ids,
                ).all()

                # none
                results += cls.matching_rule_query_builder(
                    q=matched,
                    entity_type=MatchingRuleEntityType.USER_FLAG,
                    rule_type=MatchingRuleType.EXCLUDE,
                    all=True,
                    previous_results=ids,
                ).all()

        if not results:
            stats.increment(
                metric_name="api.care_advocate_matching.models.matching_rules.find_matches_for",
                pod_name=stats.PodNames.CARE_DISCOVERY,
                tags=["error:true", "error_cause:no_match"],
            )
            log.info(
                "catch all ca member matching - no assignable_advocates matching given criteria",
                user_id=user.id,
                country=country_code,
                organization=organization,
                track=track_name,
                user_flags=user_flags,
            )
            return []

        matching_rule_sets_query = MatchingRuleSet.query.filter(
            MatchingRuleSet.id.in_(cls.extract_ids(results))
        )

        return AssignableAdvocate.query.filter(
            AssignableAdvocate.practitioner_id.in_(
                matching_rule_sets_query.with_entities(
                    MatchingRuleSet.assignable_advocate_id
                ).subquery()
            )
        ).all()


class MatchingRule(base.TimeLoggedModelBase):
    __tablename__ = "matching_rule"

    id = Column(Integer, primary_key=True)
    type = Column(
        Enum(MatchingRuleType, values_callable=lambda _enum: [e.value for e in _enum])
    )
    matching_rule_set_id = Column(
        Integer, ForeignKey("matching_rule_set.id", ondelete="CASCADE")
    )

    entity = Column(
        Enum(
            MatchingRuleEntityType,
            values_callable=lambda _enum: [e.value for e in _enum],
        )
    )
    all = Column(Boolean, default=False)

    matching_rule_set = relationship(MatchingRuleSet)
    matching_rule_entities = relationship(MatchingRuleEntity, cascade="all")

    identifiers = association_proxy(
        "matching_rule_entities",
        "entity_identifier",
        creator=lambda identifier: MatchingRuleEntity(entity_identifier=identifier),
    )

    def update(self, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if "identifiers" in kwargs:
            db.session.query(MatchingRuleEntity).filter(
                MatchingRuleEntity.matching_rule_id == self.id
            ).delete()
            identifiers = kwargs.pop("identifiers")
            for identifier in identifiers:
                self.identifiers.append(identifier)

        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
