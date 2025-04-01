from models.marketing import IosNonDeeplinkUrl
from storage.connection import db
from utils.log import logger

log = logger(__name__)

URLS = [
    "reset_password",
    "avawomen.com/maven",
    "givelegacy.com/order",
    "get.mavenclinic.com/",
    "docs.google.com/forms/",
    "support.mavenclinic.com/",
    "info.mavenclinic.com",
    "join.mavenclinic.com",
    "thomsonfertility.com",
    "thefertilitypartners.com/",
    "mavenclinic.com/hlth",
    "mavenclinic.com/lp/",
    "mavenclinic.com/post/",
    "mavenclinic.com/my-bp",
    "mavenclinic.com/content/",
    "mavenclinic.com/for-employers",
    "mavenclinic.com/for-health-plans",
    "mavenclinic.com/for-consultants",
    "mavenclinic.com/resource-center",
    "mavenclinic.com/blog",
    "mavenclinic.com/for-individuals",
    "mavenclinic.com/about",
    "mavenclinic.com/press",
    "mavenclinic.com/careers",
    "mavenclinic.com/contact",
    "mavenclinic.com/contact/",
    "mavenclinic.com/covid-19",
    "mavenclinic.com/mo/refer-your-company/",
]


def seed_em():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    for url in URLS:
        log.info(f"Creating non-deeplink URL record for {url}")
        db.session.add(IosNonDeeplinkUrl(url=url))
        db.session.commit()
    log.info("Done creating non-deeplink URLs 🥥")
