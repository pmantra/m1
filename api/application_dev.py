from flask_failsafe import failsafe

# We use the hot reload system built into flask. It is auto-enabled when using
# debug mode (FLASK_DEBUG). If the python application exits due to a syntax
# error the process has to be restarted manually. In the docker development env
# this creates an additional burden as the api container must be up to execute
# tests. The flask_failsafe package catches these failures and allows hot reload
# to function as expected. To ensure this functionality is kept isolated from
# production we have placed it into a separate file called only by the
# development docker-compose.yml
# https://pypi.org/project/Flask-Failsafe/


@failsafe
def create_app() -> None:
    # note that the import is *inside* this function so that we can catch
    # errors that happen at import time
    from app import create_app

    return create_app()


if __name__ == "__main__":
    create_app().run(host="0.0.0.0")
