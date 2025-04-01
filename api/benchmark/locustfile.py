import os

import locust.contrib.fasthttp


class MonoAPIUser(locust.FastHttpUser):
    abstract = True
    host = os.getenv("LOCUST_TARGET_HOST")
    email = os.getenv("LOCUST_USER_EMAIL")
    password = os.getenv("LOCUST_USER_PASSWORD")

    def on_start(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        with self.rest(
            "POST", "/api_key", json={"email": self.email, "password": self.password}
        ) as resp:
            if not resp.js:
                return
            api_key = resp.js["api_key"]
            user_id = resp.js["id"]
            self.client.client.default_headers["Api-Key"] = api_key
            self.client.client.default_headers["X-Maven-User-ID"] = user_id


class GetProfileUser(MonoAPIUser):
    @locust.task
    def t(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        resp: locust.contrib.fasthttp.RestResponseContextManager
        with self.rest("GET", "/me") as resp:
            if resp.status_code != 200:
                resp.failure(f"Got a non-200 response: {resp.status_code}.")
