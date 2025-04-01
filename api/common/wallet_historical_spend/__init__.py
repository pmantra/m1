import os

from common.constants import current_web_origin

from .client import WalletHistoricalSpendClient  # noqa: F401
from .models import *  # noqa: F403, F401


def get_client(base_url: str = "") -> WalletHistoricalSpendClient:
    if not base_url:
        if not os.environ.get("ENVIRONMENT"):
            base_url = "http://host.docker.internal:8888/v1/"
        else:
            base_url = current_web_origin() + "/api/v1/whs/"

    return WalletHistoricalSpendClient(base_url=base_url)
