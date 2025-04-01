import logging
import os
import sys

PROD_ENV = "PROD"
STAGING_ENV = "STAGING"

ENV_NAME = os.getenv("ENVIRONMENT", "DEV")

logger = logging.getLogger(__file__)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] ~ %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

if ENV_NAME in (PROD_ENV, STAGING_ENV):
    logger.setLevel(logging.INFO)
