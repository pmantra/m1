import datetime
import json
import os

from eligibility.e9y import model


class EligibilityMemberJSONEncoder(json.JSONEncoder):
    """
    Custom JSON encoder for serializing eligibility member objects.

    This encoder extends the functionality of the standard JSONEncoder to handle
    serialization of datetime objects, date objects, DateRange objects, and
    model.EligibilityMember objects. Other types are skipped during encoding.

    Args:
        json.JSONEncoder: The standard JSON encoder.

    Returns:
        str: JSON representation of the serialized object.
    """

    def default(self, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """
        Serialize the input object into a JSON-compatible format.

        Args:
            obj: The object to be serialized.

        Returns:
            Union[str, None]: JSON-compatible representation of the input object,
            or None if the object type is not supported.
        """
        if isinstance(obj, datetime.datetime):
            return obj.isoformat()
        elif isinstance(obj, datetime.date):
            return obj.strftime("%Y-%m-%d")
        elif isinstance(obj, model.DateRange):
            # Assuming DateRange has a suitable __dict__ representation
            return obj.__dict__
        elif isinstance(obj, model.EligibilityMember):
            # Serialize EligibilityMember attributes
            return {
                "id": obj.id,
                "organization_id": obj.organization_id,
                "file_id": obj.file_id,
                "first_name": obj.first_name,
                "last_name": obj.last_name,
                "date_of_birth": obj.date_of_birth,
                "created_at": obj.created_at,
                "updated_at": obj.updated_at,
                "record": obj.record,
                "custom_attributes": obj.custom_attributes,
                "work_state": obj.work_state,
                "work_country": obj.work_country,
                "email": obj.email,
                "unique_corp_id": obj.unique_corp_id,
                "dependent_id": obj.dependent_id,
                "employer_assigned_id": obj.employer_assigned_id,
                "effective_range": obj.effective_range,
            }
        # skip other types
        else:
            return None


def is_non_prod() -> bool:
    """
    Check if the current environment is non-production.

    Returns:
        bool: True if the environment is non-production, False otherwise.
    """
    env_key = "ENVIRONMENT"
    default_env = (
        "local"  # Set a default environment if 'ENVIRONMENT' variable is not found
    )
    prod_env = ["prod", "production"]

    # Extract the environment from os.environ
    environment = os.environ.get(env_key, default_env)

    return all(substring not in environment for substring in prod_env)
