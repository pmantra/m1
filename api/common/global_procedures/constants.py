import os

from common.constants import current_web_origin

PROCEDURE_SERVICE_NAME = os.environ.get(
    "PROCEDURE_SERVICE_NAME", "procedures-server-service"
)
PROCEDURE_NAMESPACE = os.environ.get("PROCEDURE_NAMESPACE", "dps")
PROCEDURE_SERVICE_HOST = os.environ.get(
    "PROCEDURE_SERVICE_HOST",
    f"https://{PROCEDURE_SERVICE_NAME}.{PROCEDURE_NAMESPACE}.svc.cluster.local",
)
PROCEDURE_SERVICE_PATH = os.environ.get("PROCEDURE_SERVICE_PATH", "/api/v1/procedures")
PROCEDURE_SERVICE_INTERNAL_PATH = os.environ.get(
    "PROCEDURE_SERVICE_INTERNAL_PATH", "/api/v1/_/procedures"
)
PROCEDURE_SERVICE_URL = os.environ.get(
    "PROCEDURE_SERVICE_URL", f"{PROCEDURE_SERVICE_HOST}{PROCEDURE_SERVICE_PATH}"
)
BASE_URL = os.environ.get("BASE_URL", "https://www.mavenclinic.com")
PROCEDURE_ADMIN_PATH = os.environ.get(
    "PROCEDURE_ADMIN_PATH", f"{BASE_URL}/admin/direct-payments"
)
UNAUTHENTICATED_PROCEDURE_SERVICE_URL = f"{current_web_origin()}/api/v1/_/procedures"
