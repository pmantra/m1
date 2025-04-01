import os

import redis

from utils import log

log = log.logger(__name__)

MEMORYSTORE_LEARN_CMS_HOST = os.environ.get("MEMORYSTORE_LEARN_CMS_HOST")
MEMORYSTORE_LEARN_CMS_PORT = os.environ.get("MEMORYSTORE_LEARN_CMS_PORT")
MEMORYSTORE_LEARN_CMS_AUTH_STRING = os.environ.get("MEMORYSTORE_LEARN_CMS_AUTH_STRING")
MEMORY_STORE_LEARN_CMS_SERVER_CA_PATH = (
    "/learn-cms/certs/memorystore_learn_cms_server_ca.pem"
)


def redis_client() -> redis.Redis:
    log.debug("Initializing learn redis client")  # type: ignore[attr-defined] # Module has no attribute "debug"
    return redis.Redis(  # type: ignore[call-overload] # No overload variant of "Redis" matches argument types "Optional[str]", "int", "Optional[str]", "str", "int", "bool", "bool"
        host=MEMORYSTORE_LEARN_CMS_HOST,
        port=int(MEMORYSTORE_LEARN_CMS_PORT),  # type: ignore[arg-type] # Argument 1 to "int" has incompatible type "Optional[str]"; expected "Union[str, Buffer, SupportsInt, SupportsIndex, SupportsTrunc]"
        password=MEMORYSTORE_LEARN_CMS_AUTH_STRING,
        ssl_ca_certs=MEMORY_STORE_LEARN_CMS_SERVER_CA_PATH,
        db=0,
        decode_responses=True,
        ssl=True,
    )


class CachingService:
    def __init__(self) -> None:
        self.redis_client = None

        try:
            self.redis_client = redis_client()
        except Exception as e:
            log.error(  # type: ignore[attr-defined] # Module has no attribute "error"
                "Failed to initialize redis client",
                error=e,
                class_name=self.__class__.__name__,
            )
