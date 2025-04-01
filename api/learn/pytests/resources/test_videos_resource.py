from unittest import mock

from learn.models.image import Image
from learn.models.video import Video


def test_get_videos_not_enterprise(factories, client, api_helpers):
    user = factories.DefaultUserFactory()
    response = client.get(
        "/api/v1/-/library/videos",
        headers=api_helpers.json_headers(user),
    )

    assert response.status_code == 403


def test_get_videos_no_slugs(factories, client, api_helpers):
    user = factories.EnterpriseUserFactory()
    response = client.get(
        "/api/v1/-/library/videos",
        headers=api_helpers.json_headers(user),
    )

    assert response.status_code == 400
    data = api_helpers.load_json(response)
    assert (
        data["errors"][0]["title"] == "{'slugs': ['Missing data for required field.']}"
    )


def test_get_videos_too_many_slugs(factories, client, api_helpers):
    user = factories.EnterpriseUserFactory()
    response = client.get(
        f"/api/v1/-/library/videos?slugs={','.join([f'slug-{i}' for i in range(53)])}",
        headers=api_helpers.json_headers(user),
    )

    assert response.status_code == 400
    data = api_helpers.load_json(response)
    assert (
        data["errors"][0]["title"]
        == "{'slugs': ['slugs must have between 1 and 52 values, inclusive.']}"
    )


@mock.patch("learn.resources.videos.VideoService")
def test_get_videos(mock_video_service, factories, client, api_helpers):
    user = factories.EnterpriseUserFactory()

    mock_video_service.return_value.get_values.return_value = {
        f"slug-{index}": Video(
            slug=f"slug-{index}",
            title=f"Title of video #{index}",
            image=Image(
                url=f"/link/to/image/{index}", description=f"Image alt text {index}"
            ),
            video_url=f"/link/to/video/{index}",
            captions_url=f"/link/to/video/{index}/captions",
        )
        for index in range(2)
    }
    response = client.get(
        "/api/v1/-/library/videos?slugs=slug-0,slug-1",
        headers=api_helpers.json_headers(user),
    )

    assert response.status_code == 200
    data = api_helpers.load_json(response)
    assert len(data["videos"]) == 2
    assert data["videos"][0]["slug"] == "slug-0"
    assert data["videos"][1]["slug"] == "slug-1"
