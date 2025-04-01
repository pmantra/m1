from unittest import mock


def create_contentful_asset_mock(asset_fields: dict) -> mock.Mock:
    asset = mock.Mock(**asset_fields)
    asset.fields.return_value = asset_fields
    asset.url.return_value = asset.file["url"]

    return asset
