import copy
import json
from typing import Dict, Union
from unittest import mock

import pytest

from learn.services import banner_service

__SLUG = "🐌"
__KEY = f"banner:{__SLUG}"


@pytest.fixture()
def mock_banner_entry():
    banner_entry = mock.Mock(slug=__SLUG)
    mock_asset = mock.Mock()
    mock_asset.url.return_value = "/image.png"
    banner_entry.fields.return_value = {
        "title": "title",
        "body": "body",
        "image": mock_asset,
        "cta_text": "cta text",
        "cta_url": "/cta",
        "secondary_cta_text": "secondary cta text",
        "secondary_cta_url": "/secondary-cta",
    }
    return banner_entry


@pytest.fixture()
def banner_dict() -> Dict[str, Union[str, Dict[str, str]]]:
    return {
        "title": "title",
        "body": "body",
        "image": "/image.png",
        "cta": {"text": "cta text", "url": "/cta"},
        "secondary_cta": {"text": "secondary cta text", "url": "/secondary-cta"},
    }


@mock.patch("learn.services.contentful.LibraryContentfulClient")
@mock.patch("learn.services.caching_service.redis_client")
def test_get_value_error_initializing_redis_client(
    mock_redis_client_method,
    mock_contentful_client_constructor,
    mock_banner_entry,
    banner_dict,
):
    mock_redis_client_method.side_effect = Exception
    mock_contentful_client_constructor.return_value.get_banners_by_slug.return_value = [
        mock_banner_entry
    ]

    assert banner_service.BannerService().get_value(__SLUG) == banner_dict

    mock_contentful_client_constructor.assert_called_once_with(
        preview=False, user_facing=True
    )
    mock_contentful_client_constructor.return_value.get_banners_by_slug.assert_called_once_with(
        [__SLUG]
    )


@mock.patch("learn.services.contentful.LibraryContentfulClient")
@mock.patch("learn.services.caching_service.redis_client")
def test_get_value_already_in_cache(
    mock_redis_client_method,
    _,
    banner_dict,
):
    mock_redis_client_method.return_value.pipeline.return_value.execute.return_value = [
        json.dumps(banner_dict)
    ]

    assert banner_service.BannerService().get_value(__SLUG) == banner_dict

    mock_redis_client_method.return_value.pipeline.return_value.get.assert_called_once_with(
        __KEY
    )
    mock_redis_client_method.return_value.pipeline.return_value.execute.assert_called_once_with()


@mock.patch("learn.services.contentful.LibraryContentfulClient")
@mock.patch("learn.services.caching_service.redis_client")
def test_get_value_not_in_cache(
    mock_redis_client_method,
    mock_contentful_client_constructor,
    mock_banner_entry,
    banner_dict,
):
    mock_redis_client_method.return_value.pipeline.return_value.execute.return_value = [
        None
    ]
    mock_contentful_client_constructor.return_value.get_banners_by_slug.return_value = [
        mock_banner_entry
    ]

    assert banner_service.BannerService().get_value(__SLUG) == banner_dict

    mock_redis_client_method.return_value.pipeline.return_value.get.assert_called_once_with(
        __KEY
    )
    mock_redis_client_method.return_value.pipeline.return_value.execute.assert_has_calls(
        [mock.call(), mock.call()]
    )
    mock_contentful_client_constructor.assert_called_once_with(
        preview=False, user_facing=True
    )
    mock_contentful_client_constructor.return_value.get_banners_by_slug.assert_called_once_with(
        [__SLUG]
    )
    set_args = (
        mock_redis_client_method.return_value.pipeline.return_value.set.call_args.args
    )
    assert set_args[0] == __KEY
    assert json.loads(set_args[1]) == banner_dict


@mock.patch("learn.services.contentful.LibraryContentfulClient")
@mock.patch("learn.services.caching_service.redis_client")
def test_get_value_banner_not_found(
    mock_redis_client_method,
    mock_contentful_client_constructor,
    banner_dict,
):
    mock_redis_client_method.return_value.pipeline.return_value.execute.return_value = [
        None
    ]
    mock_contentful_client_constructor.return_value.get_banners_by_slug.return_value = [
        None
    ]

    assert banner_service.BannerService().get_value(__SLUG) is None

    mock_redis_client_method.return_value.pipeline.return_value.get.assert_called_once_with(
        __KEY
    )
    mock_redis_client_method.return_value.pipeline.return_value.execute.assert_called_once_with()
    mock_contentful_client_constructor.assert_called_once_with(
        preview=False, user_facing=True
    )
    mock_contentful_client_constructor.return_value.get_banners_by_slug.assert_called_once_with(
        [__SLUG]
    )
    mock_redis_client_method.return_value.set.assert_not_called()


@mock.patch("learn.services.contentful.LibraryContentfulClient")
@mock.patch("learn.services.caching_service.redis_client")
def test_get_value_error_reading_from_cache(
    mock_redis_client_method,
    mock_contentful_client_constructor,
    mock_banner_entry,
    banner_dict,
):
    mock_redis_client_method.return_value.pipeline.return_value.execute.side_effect = (
        Exception
    )
    mock_contentful_client_constructor.return_value.get_banners_by_slug.return_value = [
        mock_banner_entry
    ]

    assert banner_service.BannerService().get_value(__SLUG) == banner_dict

    mock_redis_client_method.return_value.pipeline.return_value.get.assert_called_once_with(
        __KEY
    )
    mock_redis_client_method.return_value.pipeline.return_value.execute.assert_has_calls(
        [mock.call(), mock.call()]
    )
    mock_contentful_client_constructor.assert_called_once_with(
        preview=False, user_facing=True
    )
    mock_contentful_client_constructor.return_value.get_banners_by_slug.assert_called_once_with(
        [__SLUG]
    )
    set_args = (
        mock_redis_client_method.return_value.pipeline.return_value.set.call_args.args
    )
    assert set_args[0] == __KEY
    assert json.loads(set_args[1]) == banner_dict


@mock.patch("learn.services.contentful.LibraryContentfulClient")
@mock.patch("learn.services.caching_service.redis_client")
def test_get_value_old_model_in_cache(
    mock_redis_client_method,
    mock_contentful_client_constructor,
    mock_banner_entry,
    banner_dict,
):
    bad_banner_dict = copy.deepcopy(banner_dict)
    del bad_banner_dict["title"]

    mock_redis_client_method.return_value.pipeline.return_value.execute.return_value = [
        json.dumps(bad_banner_dict)
    ]
    mock_contentful_client_constructor.return_value.get_banners_by_slug.return_value = [
        mock_banner_entry
    ]

    assert banner_service.BannerService().get_value(__SLUG) == banner_dict

    mock_redis_client_method.return_value.pipeline.return_value.get.assert_called_once_with(
        __KEY
    )
    mock_redis_client_method.return_value.pipeline.return_value.execute.assert_has_calls(
        [mock.call(), mock.call()]
    )
    mock_redis_client_method.return_value.delete.assert_called_once_with(__KEY)
    mock_contentful_client_constructor.assert_called_once_with(
        preview=False, user_facing=True
    )
    mock_contentful_client_constructor.return_value.get_banners_by_slug.assert_called_once_with(
        [__SLUG]
    )
    set_args = (
        mock_redis_client_method.return_value.pipeline.return_value.set.call_args.args
    )
    assert set_args[0] == __KEY
    assert json.loads(set_args[1]) == banner_dict


@mock.patch("learn.services.contentful.LibraryContentfulClient")
@mock.patch("learn.services.caching_service.redis_client")
def test_get_value_error_from_contentful(
    mock_redis_client_method,
    mock_contentful_client_constructor,
):
    mock_redis_client_method.return_value.pipeline.return_value.execute.return_value = [
        None
    ]
    mock_contentful_client_constructor.return_value.get_banners_by_slug.side_effect = (
        Exception
    )

    assert banner_service.BannerService().get_value(__SLUG) is None

    mock_redis_client_method.return_value.pipeline.return_value.get.assert_called_once_with(
        __KEY
    )
    mock_redis_client_method.return_value.pipeline.return_value.execute.assert_called_once_with()
    mock_contentful_client_constructor.assert_called_once_with(
        preview=False, user_facing=True
    )
    mock_contentful_client_constructor.return_value.get_banners_by_slug.assert_called_once_with(
        [__SLUG]
    )
    mock_redis_client_method.return_value.set.assert_not_called()


@mock.patch("learn.services.contentful.LibraryContentfulClient")
@mock.patch("learn.services.caching_service.redis_client")
def test_get_value_error_writing_to_cache(
    mock_redis_client_method,
    mock_contentful_client_constructor,
    mock_banner_entry,
    banner_dict,
):
    mock_redis_client_method.return_value.pipeline.return_value.execute.return_value = [
        None
    ]
    mock_contentful_client_constructor.return_value.get_banners_by_slug.return_value = [
        mock_banner_entry
    ]
    mock_redis_client_method.return_value.set.side_effect = Exception

    assert banner_service.BannerService().get_value(__SLUG) == banner_dict

    mock_redis_client_method.return_value.pipeline.return_value.get.assert_called_once_with(
        __KEY
    )
    mock_redis_client_method.return_value.pipeline.return_value.execute.assert_has_calls(
        [mock.call(), mock.call()]
    )
    mock_contentful_client_constructor.assert_called_once_with(
        preview=False, user_facing=True
    )
    mock_contentful_client_constructor.return_value.get_banners_by_slug.assert_called_once_with(
        [__SLUG]
    )
    set_args = (
        mock_redis_client_method.return_value.pipeline.return_value.set.call_args.args
    )
    assert set_args[0] == __KEY
    assert json.loads(set_args[1]) == banner_dict


@mock.patch("learn.services.contentful.LibraryContentfulClient")
@mock.patch("learn.services.caching_service.redis_client")
def test_get_values(
    mock_redis_client_method,
    mock_contentful_client_constructor,
    mock_banner_entry,
    banner_dict,
):
    mock_redis_client_method.return_value.pipeline.return_value.execute.return_value = [
        json.dumps(banner_dict),
        None,
    ]
    mock_contentful_client_constructor.return_value.get_banners_by_slug.return_value = [
        mock_banner_entry
    ]

    assert banner_service.BannerService().get_values(
        ["slug-1", mock_banner_entry.slug]
    ) == {
        "slug-1": banner_dict,
        mock_banner_entry.slug: banner_dict,
    }

    mock_redis_client_method.return_value.pipeline.return_value.get.assert_has_calls(
        [mock.call("banner:slug-1"), mock.call(f"banner:{mock_banner_entry.slug}")]
    )
    mock_redis_client_method.return_value.pipeline.return_value.execute.assert_has_calls(
        [mock.call(), mock.call()]
    )
    mock_contentful_client_constructor.assert_called_once_with(
        preview=False, user_facing=True
    )
    mock_contentful_client_constructor.return_value.get_banners_by_slug.assert_called_once_with(
        [mock_banner_entry.slug]
    )
    set_args = (
        mock_redis_client_method.return_value.pipeline.return_value.set.call_args.args
    )
    assert set_args[0] == f"banner:{mock_banner_entry.slug}"
    assert json.loads(set_args[1]) == banner_dict


@mock.patch("learn.services.contentful.LibraryContentfulClient")
@mock.patch("learn.services.caching_service.redis_client")
def test_save_value_in_cache_error_initializing_redis_client(
    mock_redis_client_method, _, banner_dict
):
    mock_redis_client_method.side_effect = Exception
    with pytest.raises(RuntimeError):
        banner_service.BannerService().save_value_in_cache(__SLUG, banner_dict)


@mock.patch("learn.services.contentful.LibraryContentfulClient")
@mock.patch("learn.services.caching_service.redis_client")
def test_save_value_in_cache(mock_redis_client_method, _, banner_dict):
    banner_service.BannerService().save_value_in_cache(__SLUG, banner_dict)

    set_args = mock_redis_client_method.return_value.set.call_args.args
    assert set_args[0] == __KEY
    assert json.loads(set_args[1]) == banner_dict


@mock.patch("learn.services.contentful.LibraryContentfulClient")
@mock.patch("learn.services.caching_service.redis_client")
def test_remove_value_from_cache(
    mock_redis_client_method, mock_contentful_client_constructor
):
    entry_id = "12345abcde"
    mock_contentful_client_constructor.return_value.get_entry_by_id.return_value.slug = (
        __SLUG
    )

    banner_service.BannerService().remove_value_from_cache(entry_id)

    mock_contentful_client_constructor.assert_has_calls(
        [
            mock.call(preview=False, user_facing=True),
            mock.call(preview=True, user_facing=False),
        ]
    )
    mock_contentful_client_constructor.return_value.get_entry_by_id.assert_called_once_with(
        entry_id
    )
    mock_redis_client_method.return_value.delete.assert_called_once_with(__KEY)
