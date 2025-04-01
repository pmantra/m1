import flask_babel
import httpproblem
from flask import globals

from common.services import api
from learn.services.contentful import DEFAULT_CONTENTFUL_LOCALE
from learn.utils import contentful_event_handler
from utils import log, rotatable_token

log = log.logger(__name__)
from babel import Locale


class LearnContentfulWebhook(api.UnauthenticatedResource):
    CONTENTFUL_LEARN_WEBHOOK_SECRET = rotatable_token.RotatableToken(
        "CONTENTFUL_LEARN_WEBHOOK_SECRET"
    )

    def get(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        headers = globals.request.headers

        if not self.CONTENTFUL_LEARN_WEBHOOK_SECRET.check_token(
            headers.get("X-Maven-Contentful-Secret", "")
        ):
            raise httpproblem.Problem(403)

        # https://www.contentful.com/developers/docs/concepts/webhooks/#headers
        # The topic is of format ContentManagement.[Type].[Action]
        # The type is either "Asset" / "Entry" which we've also put in the Content-Type header below
        # The action will be "publish" or "unpublish"
        action = headers.get("X-Contentful-Topic", "").split(".")[-1]
        entity_type = headers.get("X-Contentful-Entity-Type", "")
        content_type = headers.get("X-Contentful-Content-Type", "")
        entity_id = headers.get("X-Contentful-Entity-ID", "")
        handler = contentful_event_handler.ContentfulEventHandler()
        with flask_babel.force_locale(Locale.parse(DEFAULT_CONTENTFUL_LOCALE, sep="-")):
            try:
                handler.handle_event(action, entity_type, content_type, entity_id)
            except Exception as e:
                log.error(  # type: ignore[attr-defined] # Module has no attribute "error"
                    "Unable to handle Contentful webhook event",
                    action=action,
                    type=entity_type,
                    id=entity_id,
                    error=e,
                    exc=True,
                )
                # Reraise so Contentful will retry in case this was a blip
                raise e

            return {"action": action, "type": entity_type, "entity_id": entity_id}
