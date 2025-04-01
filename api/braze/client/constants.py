import os
from urllib.parse import urljoin

# https://www.braze.com/docs/developer_guide/rest_api/basics/#endpoints
API_ENDPOINT = "https://rest.iad-02.braze.com"
SDK_ENDPOINT = "sdk.iad-02.braze.com"

# Below is a list of pre-defined endpoints for the Braze API.
# Any other endpoints that are needed should be added to this list,
# with care being taken to not use dynamic information due to how
# it is being used for custom metrics tags.
#
# If such dynamic data is required in the future, the custom metrics
# should be revisited to find a way to ensure that the tags are from
# a static, limited set of values.
EMAIL_SUBSCRIBE_ENDPOINT = urljoin(API_ENDPOINT, "/email/status")
MESSAGE_SEND_ENDPOINT = urljoin(API_ENDPOINT, "/messages/send")
USER_TRACK_ENDPOINT = urljoin(API_ENDPOINT, "/users/track")
USER_DELETE_ENDPOINT = urljoin(API_ENDPOINT, "/users/delete")
USER_EXPORT_ENDPOINT = urljoin(API_ENDPOINT, "/users/export/ids")
UNSUBSCRIBES_ENDPOINT = urljoin(API_ENDPOINT, "/email/unsubscribes")
DAU_ENDPOINT = urljoin(API_ENDPOINT, "/kpi/dau/data_series")
MAU_ENDPOINT = urljoin(API_ENDPOINT, "/kpi/mau/data_series")

# This should remain a secret
BRAZE_API_KEY = os.environ.get("BRAZE_API_KEY")

# These are app identifiers
BRAZE_WEB_APP_ID = os.environ.get("BRAZE_WEB_APP_ID")
BRAZE_IOS_API_KEY = os.environ.get("BRAZE_IOS_API_KEY")
BRAZE_ANDROID_API_KEY = os.environ.get("BRAZE_ANDROID_API_KEY")
BRAZE_IOS_MPRACTICE_API_KEY = os.environ.get("BRAZE_IOS_MPRACTICE_API_KEY")

# API key specific to mPractice Providers
BRAZE_MPRACTICE_API_KEY = os.environ.get("BRAZE_MPRACTICE_API_KEY")

# API key for fertility portal app group
BRAZE_FERTILITY_CLINIC_PORTAL_API_KEY = os.environ.get(
    "BRAZE_FERTILITY_CLINIC_PORTAL_API_KEY"
)

REQUEST_TIMEOUT = 15
UNSUBSCRIBES_ENDPOINT_LIMIT = 500

TRACK_USER_ENDPOINT_LIMIT = 75
