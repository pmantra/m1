import contentful


def get_url(asset: contentful.Asset) -> str:
    url = asset.url()
    if url.startswith("//"):
        url = "https:" + url
    return url
