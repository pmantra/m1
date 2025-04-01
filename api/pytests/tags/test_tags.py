from dateutil import parser

from pytests.factories import EnterpriseUserFactory, ResourceFactory, TagFactory


class TestTagsResource:
    def test_get_tags(self, factories, client, api_helpers):
        tag = TagFactory.create()
        ResourceFactory.create(tracks=["pregnancy"], tags=[tag])
        user = EnterpriseUserFactory.create(
            tracks__name="pregnancy", tracks__current_phase="week-2"
        )
        res = client.get("/api/v1/tags", headers=api_helpers.json_headers(user=user))
        data = api_helpers.load_json(res)
        assert data[0].get("name") == tag.name
        assert data[0].get("display_name") == tag.display_name

    def test_get_tags_default_order(self, factories, client, api_helpers):
        older_tag = TagFactory.create(modified_at=parser.parse("2023-01-01T00:00:00"))
        newer_tag = TagFactory.create(modified_at=parser.parse("2024-01-01T00:00:00"))
        ResourceFactory.create(tracks=["pregnancy"], tags=[newer_tag, older_tag])
        user = EnterpriseUserFactory.create(
            tracks__name="pregnancy", tracks__current_phase="week-2"
        )
        res = client.get("/api/v1/tags", headers=api_helpers.json_headers(user=user))
        data = api_helpers.load_json(res)
        assert data[0].get("name") == newer_tag.name
        assert data[1].get("name") == older_tag.name

    def test_get_tags_order_asc(self, factories, client, api_helpers):
        older_tag = TagFactory.create(modified_at=parser.parse("2023-01-01T00:00:00"))
        newer_tag = TagFactory.create(modified_at=parser.parse("2024-01-01T00:00:00"))
        ResourceFactory.create(tracks=["pregnancy"], tags=[newer_tag, older_tag])
        user = EnterpriseUserFactory.create(
            tracks__name="pregnancy", tracks__current_phase="week-2"
        )
        res = client.get(
            "/api/v1/tags?order_direction=asc",
            headers=api_helpers.json_headers(user=user),
        )
        data = api_helpers.load_json(res)
        assert data[0].get("name") == older_tag.name
        assert data[1].get("name") == newer_tag.name
