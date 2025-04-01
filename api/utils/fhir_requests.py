import enum
import json
import os
import traceback
from datetime import datetime, timezone
from typing import Iterator, Optional, Union
from urllib.parse import urlencode

from google.auth import default as default_auth
from google.auth.transport import Response, requests

from utils.gcp import safe_get_project_id
from utils.log import logger

log = logger(__name__)

CLOUD_REGION = os.environ.get("FHIR_GCH_REGION", None)
DATASET = os.environ.get("FHIR_DATASET", None)
STORE = os.environ.get("FHIR_STORE", None)

FHIRRequestParams = Union[list, tuple, set, str, int, float]


class FHIRActions:
    search_operation_failed = "search_operation_failed"
    search_request_failed = "search_request_failed"
    search_succeeded = "search_succeeded"
    export_operation_failed = "export_operation_failed"
    export_request_failed = "export_request_failed"
    export_succeeded = "export_succeeded"
    read_failed = "read_failed"
    read_succeeded = "read_succeeded"
    batch_failed = "batch_failed"
    batch_succeeded = "batch_succeeded"

    @classmethod
    def get_succeeded_status(cls, response, resource: str = None):  # type: ignore[no-untyped-def,assignment] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments #type: ignore[assignment] # Incompatible default for argument "resource" (default has type "None", argument has type "str")
        if not resource:
            return cls.batch_succeeded

        if resource.endswith("_search"):
            return cls.search_succeeded

        if response.request.method != "GET":
            return cls.export_succeeded

        return cls.read_succeeded

    @classmethod
    def get_failed_status(cls, response=None, resource: str = None) -> str:  # type: ignore[no-untyped-def,assignment] # Function is missing a type annotation for one or more arguments #type: ignore[assignment] # Incompatible default for argument "resource" (default has type "None", argument has type "str")
        if not resource:
            return cls.batch_failed

        if not response:
            if resource.endswith("_search"):
                return cls.search_request_failed
            return cls.export_request_failed

        if response.request.method != "GET":
            if resource.endswith("_search"):
                return cls.search_operation_failed
            return cls.export_operation_failed

        return cls.read_failed


def fhir_audit(
    action_type: str, target: str, user_id: int = None, data: dict = None  # type: ignore[assignment] # Incompatible default for argument "user_id" (default has type "None", argument has type "int") #type: ignore[assignment] # Incompatible default for argument "data" (default has type "None", argument has type "Dict[Any, Any]")
) -> None:

    # Extract user_id value from request payload if not given explicitly
    if not user_id and data and "request" in data:
        try:
            user_id = data["request"]["recorder"]["identifier"]["value"]
        except (KeyError, TypeError):
            pass

    log.info(
        "audit_log_events",
        audit_log_info={
            "user_id": user_id,
            "action_type": action_type,
            "action_target_type": target,
            "action_target_data": data,
        },
    )


def update_param_spec(**kwargs: FHIRRequestParams) -> dict:
    """Change list/tuple values such as `{k: [v1, v2]}` to `{k: "v1,v2"}`.

    Note that other iterables, like sets, will remain so that urlencode can use
    the `doseq=True` option to create multiple key=value pairs.
    """
    params = {
        k: (",".join(map(str, v)) if isinstance(v, (list, tuple)) else v)
        for k, v in kwargs.items()
    }
    if "_last_updated" in params:
        params["_lastUpdated"] = params.pop("_last_updated", "")
    return params


class OperationOutcomeException(Exception):
    pass


class FHIRClientValueError(ValueError):
    pass


class MonolithFHIRSources(enum.Enum):
    ASSESSMENT_PUT = "monolith:endpoint:userassessmentresource"
    ASSESSMENT_POST = "monolith:endpoint:userassessmentsresource"
    ASSESSMENT_CONDITION_MIGRATION = (
        "monolith:migration:fhir/condition_assessment_backfill.py"
    )
    ASSESSMENT_WEBHOOK = "monolith:endpoint:hdc_webhook"


class FHIRClient:
    """Client for connections to a Google Cloud Healthcare FHIR dataset.

    Initializing without arguments is possible when the environment is configured
    in QA or production.  Credentials are represented in the machine's
    `~/.config/gcloud/application_default_credentials.json` file.

    `use_batches` will change the behavior of the underlying request handler
    to instead add the json payloads to a buffer, only to be sent when the caller
    uses `execute_batch()`.

    A client configured for batches will still issue isolated requests when using
    search methods.
    """

    def __init__(
        self,
        cloud_region: str = CLOUD_REGION,  # type: ignore[assignment] # Incompatible default for argument "cloud_region" (default has type "Optional[str]", argument has type "str")
        dataset: str = DATASET,  # type: ignore[assignment] # Incompatible default for argument "dataset" (default has type "Optional[str]", argument has type "str")
        fhir_store: str = STORE,  # type: ignore[assignment] # Incompatible default for argument "fhir_store" (default has type "Optional[str]", argument has type "str")
        project: str = safe_get_project_id(),  # noqa  B008  TODO:  Do not perform function calls in argument defaults.  The call is performed only once at function definition time. All calls to your function will reuse the result of that definition-time function call.  If this is intended, assign the function call to a module-level variable and use that variable as a default value.
        use_batches: bool = False,
    ):
        if any(not param for param in (cloud_region, dataset, fhir_store, project)):
            raise FHIRClientValueError("Missing parameters for FHIR Client creation.")
        self.project = project
        self.cloud_region = cloud_region
        self.dataset = dataset
        self.fhir_store = fhir_store
        self.gch_credentials, _ = default_auth()
        self.use_batches = use_batches
        if self.use_batches:
            self._batch_requests = []
            self._batch_counter = 1

    def __getattr__(self, k):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """Return a resource manipulator for specific resource name `k`."""
        if k[0] == k[0].upper():
            return FHIRResource(self, k)

        return self.__getattribute__(k)

    @property
    def base_url(self) -> str:
        return (
            "https://healthcare.googleapis.com/v1/"
            f"projects/{self.project}/"
            f"locations/{self.cloud_region}/"
            f"datasets/{self.dataset}/"
            f"fhirStores/{self.fhir_store}/"
            "fhir"
        )

    @property
    def default_headers(self) -> dict:
        return {"Content-Type": "application/fhir+json;charset=utf-8"}

    def get_session(self) -> requests.AuthorizedSession:
        """Return contextmanager-compatible authorized session."""
        return requests.AuthorizedSession(self.gch_credentials)

    def handle_response(self, response, resources: Union[list, None]) -> dict:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        """Create an audit record based on the response characteristics.

        Batch responses consist of several records with embedded response info.
        Non-batch responses are wrapped as if they are a single part of a batch.
        """
        content = response.json()
        audit_context = {
            "body": json.loads(response.request.body or "null"),
            "response": response,
            "content": content,
        }

        if content.get("type") == "batch-response":
            parts = content["entry"]
        else:
            parts = [
                {"resource": content, "response": {"status": f"{response.status_code}"}}
            ]

        for resource, part in zip(resources, parts):  # type: ignore[arg-type] # Argument 1 to "zip" has incompatible type "Optional[List[Any]]"; expected "Iterable[Any]"
            part_context = {
                **audit_context,
                "content": part["resource"],
                "resource": resource,
            }
            status_code = int(part["response"]["status"].split()[0])
            # Handle FHIR errors: https://www.hl7.org/fhir/operationoutcome.html
            if (
                400 <= status_code < 600
                or part.get("resource", {}).get("resourceType") == "OperationOutcome"
            ):
                self.record_operation_failure(status_code=status_code, **part_context)  # type: ignore[arg-type] # Argument "status_code" to "record_operation_failure" of "FHIRClient" has incompatible type "int"; expected "str"
            else:
                self.record_operation_success(**part_context)

        return content

    def record_http_failure(
        self,
        url: str,
        resource: Union[str, None],
        exception: str,
    ) -> None:
        fhir_audit(
            action_type=FHIRActions.get_failed_status(response=None, resource=resource),  # type: ignore[arg-type] # Argument "resource" to "get_failed_status" of "FHIRActions" has incompatible type "Optional[str]"; expected "str"
            target=url,
            data={
                "resource": resource,
                "request_exception": exception,
            },
        )

    def record_operation_failure(
        self,
        body: dict,
        content: dict,
        response: Response,
        resource: Union[str, None],
        status_code: str,
    ) -> None:
        fhir_audit(
            action_type=FHIRActions.get_failed_status(response, resource=resource),  # type: ignore[arg-type] # Argument "resource" to "get_failed_status" of "FHIRActions" has incompatible type "Optional[str]"; expected "str"
            target=response.url,
            data={
                "resource": resource or content["resource"]["resourceType"],
                "request": body,
                "response": content,
                "status_code": status_code,
            },
        )

    def record_operation_success(
        self,
        body: dict,
        content: dict,
        response: Response,
        resource: Union[str, None],
    ) -> None:
        fhir_audit(
            action_type=FHIRActions.get_succeeded_status(response, resource=resource),  # type: ignore[arg-type] # Argument "resource" to "get_succeeded_status" of "FHIRActions" has incompatible type "Optional[str]"; expected "str"
            target=response.url,
            data={"resource": resource, "request": body},
        )

    # Internal request handlers
    def _request(
        self,
        method: str,
        resource: str,
        params: dict = None,  # type: ignore[assignment] # Incompatible default for argument "params" (default has type "None", argument has type "Dict[Any, Any]")
        data: dict = None,  # type: ignore[assignment] # Incompatible default for argument "data" (default has type "None", argument has type "Dict[Any, Any]")
        force: bool = False,
    ) -> dict:
        """Generate request with given `method` to a `resource` path appended to the base api url.
        Returns the response content json as a dict.
        """
        if data and not isinstance(data, dict):
            raise ValueError(
                f"FHIR resource data must be a dictionary, if present. Received {type(data)}."
            )

        if self.use_batches:
            if not force:
                return self._add_batch_request(resource, method, data)  # type: ignore[func-returns-value] # "_add_batch_request" of "FHIRClient" does not return a value (it only ever returns None)
            log.info(
                "Issuing immediate request during batch mode [force=True]",
                resource=resource,
                method=method,
            )

        url = f"{self.base_url}/{resource}"
        if params:
            params = update_param_spec(**params)
            url += (
                # api query syntax considered safe
                f"?{urlencode(params, safe=':,|/', doseq=True)}"
            )
        return self._single_request(resource, method, url, data)

    def _single_request(
        self, resource: str, method: str, url: str, data: Optional[dict] = None
    ) -> dict:
        log.debug(f"FHIR {method}", url=url, use_batches=self.use_batches)
        with self.get_session() as session:
            methods = {
                "GET": session.get,
                "POST": session.post,
                "PUT": session.put,
                "PATCH": session.patch,
                "DELETE": session.delete,
            }
            if method not in methods:
                raise ValueError(
                    f"Invalid request method {method!r}. Must be one of {', '.join(list(methods.keys()))}."
                )
            try:
                response = methods[method](
                    url,
                    headers=self.default_headers,
                    data=json.dumps(data) if data else None,
                )
            except requests.exceptions.TransportError:
                self.record_http_failure(
                    url, resource, exception=traceback.format_exc()
                )
                raise
            else:
                # Handle response(s) alongside the input resource name(s).
                if data and data.get("resourceType") == "Bundle":
                    resource = [  # type: ignore[assignment] # Incompatible types in assignment (expression has type "List[Any]", variable has type "str")
                        entry["request"]["url"].split("/", 1)[0]
                        for entry in data["entry"]
                    ]
                elif resource:
                    resource = [resource]  # type: ignore[assignment] # Incompatible types in assignment (expression has type "List[str]", variable has type "str")
                return self.handle_response(response, resources=resource)  # type: ignore[arg-type] # Argument "resources" to "handle_response" of "FHIRClient" has incompatible type "str"; expected "Optional[List[Any]]"

    # Batch handlers
    def _add_batch_request(
        self, resource: str, method: str, data: Optional[dict] = None
    ) -> None:
        """Add a request to the batch to be sent later.
        `resource` is the short resource name, e.g. "Patient", "Patient/123".
        `method` is the HTTP method for the request.
        `data` is the FHIR-ready payload of the item to be submitted at the url.
        """
        if not self.use_batches:
            raise ValueError("Batch execution was not configured for this client.")
        payload = {
            "request": {
                "method": method,
                "url": resource,
            },
        }
        if data is not None:
            payload["resource"] = data
        self._batch_requests.append(payload)

    def execute_batch(self, batch_type: str = "batch") -> dict:
        """Executes the batch of requests called by the client so far.
        Returns the response content json as a dict.
        """
        if not self.use_batches:
            raise ValueError("Batch execution was not configured for this client.")
        elif not self._batch_requests:
            raise ValueError("No batch requests to execute.")
        payload = {
            "resourceType": "Bundle",
            "id": f"bundle-batch-{self._batch_counter}",
            "meta": {
                "lastUpdated": datetime.now(timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                ),
            },
            "type": batch_type,
            "entry": self._batch_requests,
        }
        response = self._single_request(
            resource=None, method="POST", url=self.base_url, data=payload  # type: ignore[arg-type] # Argument "resource" to "_single_request" of "FHIRClient" has incompatible type "None"; expected "str"
        )
        self._batch_requests = []
        self._batch_counter += 1
        return response

    # Primary operation handlers
    def get(self, resource: str, params: dict = None, force: bool = False) -> dict:  # type: ignore[assignment] # Incompatible default for argument "params" (default has type "None", argument has type "Dict[Any, Any]")
        return self._request("GET", resource, params=params, force=force)

    def post(
        self, resource: str, params: dict = None, data: dict = None, force: bool = False  # type: ignore[assignment] # Incompatible default for argument "params" (default has type "None", argument has type "Dict[Any, Any]") #type: ignore[assignment] # Incompatible default for argument "data" (default has type "None", argument has type "Dict[Any, Any]")
    ) -> dict:
        return self._request("POST", resource, params=params, data=data, force=force)

    def put(self, resource: str, data: dict = None, force: bool = False) -> dict:  # type: ignore[assignment] # Incompatible default for argument "data" (default has type "None", argument has type "Dict[Any, Any]")
        return self._request("PUT", resource, data=data, force=force)

    def patch(self, resource: str, data: dict, force: bool = False) -> dict:
        return self._request("PATCH", resource, data=data, force=force)

    def delete(self, resource: str, force: bool = False) -> dict:
        return self._request("DELETE", resource, force=force)

    # Generic actions
    def search(self, **kwargs) -> dict:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        """Search all resource types for field values.  All parameters are AND filters.
        List values perform an OR query within that single key name's values.
        """
        # force to ignore batch mode
        return self.post("_search", params=kwargs, force=True)

    # Generic operations on response payloads
    def iterate_entries(self, bundle: dict) -> Iterator[dict]:
        """Iterate over the entries in a bundle response."""
        page_number = 1
        while bundle:
            for entry in bundle.get("entry", []):
                yield entry

            next_url = self.get_links(bundle).get("next")
            if next_url:
                page_number += 1
                bundle = self._single_request(
                    f"[walking page {page_number}]", "GET", next_url
                )
            else:
                bundle = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "Dict[Any, Any]")

    @classmethod
    def get_links(cls, bundle: dict) -> dict:
        """Return dict-formatted links by their name in the bundle."""
        return {link["relation"]: link["url"] for link in bundle["link"]}

    @classmethod
    def get_identifiers(cls, resource: dict) -> dict:
        """Return a dict of all identifiers for a resource."""
        return {
            identifier["type"]["text"]: identifier["value"]
            for identifier in resource.get("identifier", [])
        }


class FHIRResource:
    """Provide resource methods for a specific resource name.

    The `use_batches` behavior on the resource's client will control whether batching
    will occur.  The api at this resource level is the same in either case, with
    the caveat that search methods will generate a lone request even if batching is
    enabled.
    """

    def __init__(self, client: FHIRClient, resource: str):
        self.client = client
        self.resource = resource

    def search(self, **kwargs) -> dict:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        """Search specific resource type for field values.  All parameters are AND filters.
        List values perform an OR query within that single key name's values.
        """
        return self.client.post(f"{self.resource}/_search", params=kwargs, force=True)

    def search_by_identifiers(self, _last_updated=None, **kwargs) -> dict:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        """Search by Maven-specific system identifiers given as keywords."""
        params = {"identifier": set("|".join(map(str, (v,))) for v in kwargs.values())}
        if _last_updated:
            params["_last_updated"] = _last_updated
        return self.search(**params)

    def read(self, resource_id: str) -> dict:
        """Resource retrieval GET request."""
        return self.client.get(f"{self.resource}/{resource_id}")

    def create(self, data: dict) -> dict:
        """Resource creation POST request."""
        return self.client.post(self.resource, data=data)

    def update(self, resource_id: str, data: dict) -> dict:
        """Resource update PUT request."""
        return self.client.put(f"{self.resource}/{resource_id}", data=data)

    def update_partial(self, resource_id: str, data: dict) -> dict:
        """Resource partial update PATCH request."""
        return self.client.patch(f"{self.resource}/{resource_id}", data=data)

    def destroy(self, resource_id: str) -> dict:
        """Resource removal DELETE request."""
        return self.client.delete(f"{self.resource}/{resource_id}")

    def validate(self, data: dict) -> dict:
        """Validate resource schema."""
        return self.client.post(f"{self.resource}/$validate", data=data)
