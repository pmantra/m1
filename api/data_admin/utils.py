"""Utility functions for data admin."""
import json
from typing import Any, Dict, List

from payer_accumulator.constants import ACCUMULATION_FILE_BUCKET
from payer_accumulator.models.payer_accumulation_reporting import (
    PayerAccumulationReports,
)


def extract_fixture_metadata(
    content: str,
    name: str,
    parameterizable_fixtures: Dict[str, Any],
    subdirectory: str = "",
) -> None:
    """Extract fixture name and parameters from fixture data, updating parameterizable_fixtures if needed.

    Args:
        content: The raw JSON content from the fixture file
        name: The base name of the fixture file (without extension)
        parameterizable_fixtures: Dictionary to store fixtures that have parameters
        subdirectory: Optional subdirectory path where the fixture is located
    """
    data = json.loads(content)
    if isinstance(data, dict) and "parameters" in data:
        parameters = data.get("parameters", [])
        if parameters:  # Only store if there are actually parameters
            fixture_key = (
                (subdirectory + "__" + name).lstrip("/") if subdirectory else name
            )
            # Store the parameters list directly to preserve order
            parameterizable_fixtures[fixture_key] = parameters


def substitute_parameters(obj: Any, parameters: Dict[str, str]) -> Any:
    """Recursively substitute parameters in string values while preserving data structure.

    Args:
        obj: The object to perform substitution on. Can be a dict, list, string or other type.
        parameters: Dictionary of parameter names to their values.

    Returns:
        The object with all string values having parameters substituted.
        Non-string values are returned as-is.
    """
    if isinstance(obj, dict):
        return {k: substitute_parameters(v, parameters) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [substitute_parameters(v, parameters) for v in obj]
    elif isinstance(obj, str):
        return obj.format(**parameters)
    return obj


def extract_parameters_from_form(
    form_data: Dict[str, str], fixture_data: Dict[str, Any]
) -> Dict[str, str]:
    """Extract and validate parameters from form data, applying defaults where needed.

    Args:
        form_data: The form data containing parameter values with 'param_' prefix
        fixture_data: The fixture data containing parameter definitions and defaults

    Returns:
        Dictionary of parameter names to their values, with defaults applied

    Raises:
        KeyError: If a required parameter is missing and has no default
    """
    # Extract parameters from form data
    parameters = {}
    for key, value in form_data.items():
        if key.startswith("param_"):
            param_name = key[6:]  # Remove 'param_' prefix
            if value:  # Only include non-empty parameters
                parameters[param_name] = value

    # Add default values for missing parameters
    if "parameters" in fixture_data:
        param_list = fixture_data["parameters"]
        for param in param_list:
            param_name = param["name"]
            if param_name not in parameters and "default" in param:
                parameters[param_name] = param["default"]

    return parameters


def get_accumulation_report_details(created: List) -> str:
    """Generate HTML for accumulation report details including download buttons.

    Args:
        created: List of created objects to check for PayerAccumulationReports

    Returns:
        HTML string containing report details and download buttons, or empty string if no reports
    """
    reports = [m for m in created if isinstance(m, PayerAccumulationReports)]
    if not reports:
        return ""

    report_details = "".join(
        [
            f"<li>Report: {r.filename} "
            f'<button class="btn btn-xs btn-default download-report" '
            f'data-filename="{r.file_path()}" data-bucket="{ACCUMULATION_FILE_BUCKET or "_"}">Download</button></li>'
            for r in reports
        ]
    )
    return f"<br><br>Accumulation Reports created:<ul>{report_details}</ul>"
