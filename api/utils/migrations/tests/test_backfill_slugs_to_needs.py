import csv

from providers.service.need import NeedService
from utils.migrations.backfill_slugs_on_needs import backfill_slugs_on_needs


def test_backfill_add_slugs_on_needs(factories):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    slugs = []
    ids = []
    with open("utils/migrations/tests/test_backfill_slugs_to_needs.csv") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            slugs.append(row["slug"])
            ids.append(int(row["id"]))

    # needs do not have slugs
    [factories.NeedFactory.create(id=need_id, slug=None) for need_id in ids]

    backfill_slugs_on_needs(
        "utils/migrations/tests/test_backfill_slugs_to_needs.csv", False
    )

    # and now they do after running backfill
    needs = NeedService().get_needs_by_ids(need_ids=ids)
    assert needs[0].slug == slugs[0]
    assert needs[1].slug == slugs[1]
