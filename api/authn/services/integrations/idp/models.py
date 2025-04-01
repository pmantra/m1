from __future__ import annotations

import dataclasses


@dataclasses.dataclass
class IDPIdentity:
    user_id: str = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "str")
    provider: str = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "str")
    connection: str = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "str")


@dataclasses.dataclass
class AppMetadata:
    maven_user_id: str = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "str")
    company_enforce_mfa: bool = False
    maven_user_identities: list[str] = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "List[str]")
    enforce_mfa: bool = False
    original_email: str = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "str")
    original_first_name: str = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "str")
    original_last_name: str = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "str")


@dataclasses.dataclass
class IDPUser:
    """A dataclass representing the user stored in the IDP"""

    user_id: str = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "str")
    email: str = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "str")
    name: str = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "str")
    first_name: str = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "str")
    last_name: str = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "str")
    organization_external_id: str = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "str")
    rewards_id: str = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "str")
    employee_id: str = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "str")
    identities: list[IDPIdentity] = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "List[IDPIdentity]")
    external_user_id: str = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "str")
    phone_number: str = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "str")
    app_metadata: AppMetadata = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "AppMetadata")
