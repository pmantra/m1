import base64
import datetime
import hashlib
import hmac
import os
import urllib

_CDN_DOMAIN = os.getenv("CDN_DOMAIN")
_CDN_KEY_NAME = os.getenv("CDN_KEY_NAME")
_CDN_BASE64_KEY = os.getenv("CDN_BASE64_KEY")


def signed_cdn_url(path, expires_in):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if _CDN_DOMAIN is None or _CDN_KEY_NAME is None or _CDN_BASE64_KEY is None:
        raise RuntimeError(
            "Missing environment variables for signing cdn urls: "
            "CDN_DOMAIN, CDN_KEY_NAME, CDN_BASE64_KEY."
        )
    expiration_time = datetime.datetime.utcnow() + datetime.timedelta(
        seconds=expires_in
    )
    return _sign_url(
        f"https://{_CDN_DOMAIN}{path}", _CDN_KEY_NAME, _CDN_BASE64_KEY, expiration_time
    )


# https://cloud.google.com/cdn/docs/using-signed-urls#programmatically_creating_signed_urls
def _sign_url(url, key_name, base64_key, expiration_time):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """Gets the Signed URL string for the specified URL and configuration.

    Args:
        url: URL to sign as a string.
        key_name: name of the signing key as a string.
        base64_key: signing key as a base64 encoded string.
        expiration_time: expiration time as a UTC datetime object.

    Returns:
        Returns the Signed URL appended with the query parameters based on the
        specified configuration.
    """
    stripped_url = url.strip()
    parsed_url = urllib.parse.urlsplit(stripped_url)
    query_params = urllib.parse.parse_qs(parsed_url.query, keep_blank_values=True)
    epoch = datetime.datetime.utcfromtimestamp(0)
    expiration_timestamp = int((expiration_time - epoch).total_seconds())
    decoded_key = base64.b64decode(base64_key)

    url_pattern = "{url}{separator}Expires={expires}&KeyName={key_name}"

    url_to_sign = url_pattern.format(
        url=stripped_url,
        separator="&" if query_params else "?",
        expires=expiration_timestamp,
        key_name=key_name,
    )

    digest = hmac.new(decoded_key, url_to_sign.encode("utf-8"), hashlib.sha1).digest()
    signature = base64.urlsafe_b64encode(digest).decode("utf-8")

    signed_url = f"{url_to_sign}&Signature={signature}"

    return signed_url
