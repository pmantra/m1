from models.enterprise import Organization, OrganizationEligibilityType
from storage.connection import db
from utils.log import logger

log = logger(__name__)

ELIGIBILITY_MAPPING = {
    "standard": OrganizationEligibilityType.STANDARD,
    "alternate": OrganizationEligibilityType.ALTERNATE,
    "saml": OrganizationEligibilityType.SAML,  # type: ignore[attr-defined] # "Type[OrganizationEligibilityType]" has no attribute "SAML"
    "healthplan": OrganizationEligibilityType.HEALTHPLAN,
    "fileless": OrganizationEligibilityType.FILELESS,
    "client_specific": OrganizationEligibilityType.CLIENT_SPECIFIC,
}

INITIAL_DATA = [
    {"id": "128", "name": "Microsoft", "eligibility_type": "client_specific"},
    {
        "id": "154",
        "name": "Maven Clinic MSFT test org",
        "eligibility_type": "client_specific",
    },
    {
        "id": "147",
        "name": "Maven Microsoft testing",
        "eligibility_type": "client_specific",
    },
    {"id": "212", "name": "VMG Partners", "eligibility_type": "fileless"},
    {"id": "207", "name": "James Beard Foundation", "eligibility_type": "fileless"},
    {"id": "197", "name": "Goldbelly", "eligibility_type": "fileless"},
    {"id": "195", "name": "Intersect Power", "eligibility_type": "fileless"},
    {"id": "186", "name": "BBR Partners", "eligibility_type": "fileless"},
    {"id": "177", "name": "Front", "eligibility_type": "fileless"},
    {"id": "163", "name": "Mailgun", "eligibility_type": "fileless"},
    {"id": "165", "name": "Foursquare", "eligibility_type": "fileless"},
    {"id": "158", "name": "Medix Staffing Solutions", "eligibility_type": "fileless"},
    {"id": "127", "name": "Zwift Inc", "eligibility_type": "fileless"},
    {"id": "124", "name": "Harvest", "eligibility_type": "fileless"},
    {"id": "116", "name": "LendingTree", "eligibility_type": "fileless"},
    {"id": "93", "name": "Kazoo", "eligibility_type": "fileless"},
    {"id": "74", "name": "Birdco", "eligibility_type": "fileless"},
    {"id": "65", "name": "Eldridge Industries", "eligibility_type": "fileless"},
    {"id": "56", "name": "Index Ventures", "eligibility_type": "fileless"},
    {"id": "48", "name": "Supercell", "eligibility_type": "fileless"},
    {"id": "43", "name": "Keystone Real Estate Group", "eligibility_type": "fileless"},
    {"id": "14", "name": "TransRe", "eligibility_type": "fileless"},
    {"id": "8", "name": "BTS USA Inc", "eligibility_type": "fileless"},
    {"id": "120", "name": "Kindred Healthcare", "eligibility_type": "alternative"},
    {"id": "98", "name": "Elbit Systems of America", "eligibility_type": "alternative"},
    {
        "id": "72",
        "name": "Southern Glazers Wine & Spirits",
        "eligibility_type": "alternative",
    },
    {"id": "90", "name": "Standard Motor", "eligibility_type": "alternative"},
    {"id": "66", "name": "Fast Retailing", "eligibility_type": "alternative"},
    {"id": "63", "name": "Precor", "eligibility_type": "alternative"},
    {"id": "64", "name": "Sana Benefits", "eligibility_type": "alternative"},
    {"id": "55", "name": "JCPenney", "eligibility_type": "alternative"},
    {
        "id": "42",
        "name": "VIP Test Accounts Secondary",
        "eligibility_type": "alternative",
    },
    {
        "id": "33",
        "name": "Maven Bank of America testing",
        "eligibility_type": "alternative",
    },
    {
        "id": "45",
        "name": "Maven Clinic internal boa test2",
        "eligibility_type": "alternative",
    },
    {"id": "104", "name": "Onboarding Test", "eligibility_type": "alternative"},
    {
        "id": "44",
        "name": "Maven Clinic boa testing internal",
        "eligibility_type": "alternative",
    },
]


def update_org_eligibility_type():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    """
    Updates organization.eligibility_type as part of migration: 20211111163839_b96ab53e7131_add_eligibility_type_to_org.py
    Allows us to determine what eligibility flow an organization is set up for so we can optimize onboarding
    """
    for org_data in INITIAL_DATA:
        # Grab organization object from db
        org = Organization.query.get(org_data["id"])
        if not org:
            log.warn(f"Org not found while updating eligibility type {org_data}")
            continue

        # Validate org id with name
        if org.name.lower() != org_data["name"].lower():
            log.warn(
                f"Mismatch for org name while updating eligibility type {org_data}"
            )
            continue

        # Update org row
        if (
            org_data.get("eligibility_type")
            and org_data["eligibility_type"] in ELIGIBILITY_MAPPING
        ):
            org.eligibility_type = ELIGIBILITY_MAPPING[org_data["eligibility_type"]]
            log.info(f"Updated org {org_data}")

    db.session.commit()
