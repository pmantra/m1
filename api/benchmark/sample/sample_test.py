from json import JSONDecodeError

import locust.contrib.fasthttp
from maven.benchmarking.base_user_with_auth import BaseUserWithAuth
from requests import exceptions


class SampleAuthTest(BaseUserWithAuth):
    @locust.task
    def get_me(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        with self.client.get(
            "/api/v1/me",
            catch_response=True,
        ) as response:
            try:
                if response.json()["email"] != self.client.email:
                    response.failure("Did not get expected value in email")
            except JSONDecodeError:
                response.failure("Response could not be decoded as JSON")
            except exceptions.JSONDecodeError:
                response.failure("Response JSON parse error")
            except KeyError:
                response.failure("Response did not contain expected key 'email'")

    @locust.task(weight=2)
    def get_metadata(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        with self.client.get(
            "/api/v1/_/metadata",
            json={"email": self.client.email, "password": self.client.password},
            catch_response=True,
        ) as response:
            try:
                if "platform_data" not in response.json():
                    response.failure("Did not have platform_data in response")
            except JSONDecodeError:
                response.failure("Response could not be decoded as JSON")
            except exceptions.JSONDecodeError:
                response.failure("Response JSON parse error")
            except KeyError:
                response.failure("Response did not contain expected key 'email'")
