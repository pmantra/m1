import flask
import flask_restful


def add_saml(app: flask.Flask):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    # Circular dependency on app.Config (┛ಠ_ಠ)┛彡┻━┻
    from authn.resources import sso

    # SAMLConsumerResource is a Flask Restful resource,
    # which can only be added to a Flask Restful Api.
    # But that just does wonky magic to put the url routes in correctly.
    # So we temporarily create a new Api instance
    # to attach the route to the underlying flask.Flask instance.
    # (ಠ_ಠ)
    api = flask_restful.Api(app)
    api.add_resource(sso.SAMLConsumerResource, "/saml/consume/")
    api.add_resource(sso.SAMLRedirectResource, "/saml/consume/begin")
    api.add_resource(sso.SAMLCompleteResource, "/saml/consume/complete")
    return api
