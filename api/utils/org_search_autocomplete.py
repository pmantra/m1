import datetime

from sqlalchemy import or_

from models.enterprise import Organization, OrganizationType
from storage.connection import db
from utils.cache import redis_client


class OrganizationSearchAutocomplete:
    """
    A redis based system to provide autocomplete for organization names when users are onboarding
    """

    REDIS_KEY = "org_autocomplete"

    def get_autocomplete_results(self, query):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        results = []
        # return up to 10 suggestions
        count = 10
        # org names are capped at 50 char, and we want to allow some overlap with prefixes
        lookup_entries = 100
        r = redis_client(
            decode_responses=True,
            skip_on_fatal_exceptions=True,
            default_tags=["caller:org_search"],
        )
        if not r.exists(self.REDIS_KEY):
            self.load_orgs_autocomplete()
        start = r.zrank(self.REDIS_KEY, query)
        if start:
            while len(results) != count:
                range = r.zrange(self.REDIS_KEY, start, start + lookup_entries - 1)
                start += lookup_entries
                if not range or len(range) == 0:
                    break
                for entry in range:
                    minlen = min(len(entry), len(query))
                    if entry[0:minlen] != query[0:minlen]:
                        count = len(results)
                        break
                    if entry[-1] == "%" and len(results) != count:
                        split_entry = entry.split(":")
                        org_name = split_entry[1]
                        org_id = split_entry[-1][:-1]
                        results.append({"id": org_id, "name": org_name})
        return results

    def load_orgs_autocomplete(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        r = redis_client(
            skip_on_fatal_exceptions=True, default_tags=["caller:org_search"]
        )
        orgs = (
            db.session.query(
                Organization.display_name, Organization.name, Organization.id
            )
            .filter(
                Organization.internal_type.in_(
                    [OrganizationType.REAL, OrganizationType.MAVEN_FOR_MAVEN]
                ),
                Organization.activated_at.isnot(None),
                Organization.activated_at <= datetime.datetime.utcnow(),
                or_(
                    Organization.terminated_at.is_(None),
                    Organization.terminated_at >= datetime.datetime.utcnow(),
                ),
            )
            .all()
        )

        pipeline = r.pipeline()
        for org in orgs:
            name = org.display_name or org.name
            name = name.replace("_", " ")
            formatted_name = f"{name.lower()}:{name}:{org.id}"
            for l in range(1, len(name)):
                prefix = formatted_name[0:l]
                pipeline.zadd(self.REDIS_KEY, {prefix: 0})
            pipeline.zadd(self.REDIS_KEY, {formatted_name + "%": 0})
        pipeline.execute()

    def reload_orgs(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        r = redis_client(
            skip_on_fatal_exceptions=True, default_tags=["caller:org_search"]
        )
        r.delete(self.REDIS_KEY)
        self.load_orgs_autocomplete()
