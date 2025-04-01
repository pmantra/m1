from payments.resources.stripe_webhook import StripeWebHooksResource


def add_routes(api):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    api.add_resource(StripeWebHooksResource, "/v1/vendor/stripe/webhooks")

    return api
