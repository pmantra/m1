from unittest.mock import patch


def test_get_asset_download_url(client, api_helpers, factories):
    user = factories.EnterpriseUserFactory.create()
    asset = factories.UserAssetFactory.create(user=user)
    with patch(
        "views.assets.UserAsset.direct_download_url", return_value=""
    ) as mock_download_url:
        res = client.get(
            f"/api/v1/assets/{asset.id}/url",
            headers=api_helpers.json_headers(user),
        )
        mock_download_url.assert_called_once()
        assert res.status_code == 200
        assert list(res.json.keys()) == ["download_url", "content_type"]
        assert res.json["download_url"] == mock_download_url.return_value
        assert res.json["content_type"] == asset.content_type


def test_get_asset_download__not_authenticated(client, factories):
    # Given enterprise user and asset
    user = factories.EnterpriseUserFactory.create()
    asset = factories.UserAssetFactory.create(user=user)
    with patch(
        "views.assets.UserAsset.direct_download_url", return_value=""
    ) as mock_download_url:
        # When we call /download unauthenticated (no user in header)
        res = client.get(
            f"/api/v1/assets/{asset.id}/download",
        )
        # Then we should default to /view and not to asset's URL
        mock_download_url.assert_not_called()
        assert res.status_code == 302
        assert (
            res.headers["Location"]
            == f"https://www.mavenclinic.com/app/assets/{asset.id}/view"
        )
        assert res.headers["Content-Type"] == "application/json"


def test_get_asset_download__authenticated(client, api_helpers, factories):
    # Given enterprise user and asset
    user = factories.EnterpriseUserFactory.create()
    asset = factories.UserAssetFactory.create(user=user)
    with patch(
        "views.assets.UserAsset.direct_download_url", return_value="thumbor-url"
    ) as mock_download_url:
        # When we call /download authenticated (user in header)
        res = client.get(
            f"/api/v1/assets/{asset.id}/download",
            headers=api_helpers.json_headers(user),
        )
        # Then we should pass through the asset's URL
        mock_download_url.assert_called_once()
        assert res.status_code == 302
        assert res.headers["Location"] == mock_download_url.return_value
        assert res.headers["Content-Type"] == "application/json"
