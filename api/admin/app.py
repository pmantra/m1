from werkzeug.utils import redirect

from admin.factory import create_app

app = create_app()


@app.route("/")
def landing_redirect():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    return redirect("/admin")


@app.route("/healthz")
def healthcheck():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    return {"status": "OK"}


# ---- Main Runner for Dev

if __name__ == "__main__":
    import os

    os.environ["DEBUG"] = "True"
    app.run(host="0.0.0.0", port=8888, debug=True)  # no proxies in local dev...
