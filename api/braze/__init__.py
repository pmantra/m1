# flake8: noqa
# TODO: move braze related files into this directory as part of Feature Based Organization initiative
import pathlib

from .client import *

CUR_DIR = pathlib.Path(__file__).resolve().parent
WHITELIST = CUR_DIR / "braze_whitelisted_ips.yml"
