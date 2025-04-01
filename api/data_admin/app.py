from data_admin.factory import create_data_admin_app

app = create_data_admin_app()


@app.route("/healthz")
def healthcheck() -> dict:
    return {"status": "OK"}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8888, debug=True)
