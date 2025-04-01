from os import environ


class HDCconfig:
    HDC_SERVICE_NAME = environ.get("HDC_SERVICE_NAME", "hdc-api-server-service")
    HDC_NAMESPACE = environ.get("HDC_NAMESPACE", "hdc")

    HDC_API_URL = (
        f"http://{HDC_SERVICE_NAME}.{HDC_NAMESPACE}.svc.cluster.local/api/hdc/v1"
    )
