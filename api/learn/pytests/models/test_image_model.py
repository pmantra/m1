from learn.models import image


def test_asset_url_with_width_and_height():
    url = "https://i.mg/img.url"
    img = image.Image(url=url)
    result = img.asset_url(90, 120, smart=False)

    assert result == "https://i.mg/img.url?w=120&h=90&fit=fill"


def test_asset_url_without_width_or_height():
    url = "https://i.mg/img.url"
    img = image.Image(url=url)

    assert img.asset_url() == url
