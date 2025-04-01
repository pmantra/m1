import enum
import os


class Environment(str, enum.Enum):
    QA1 = enum.auto()
    QA2 = enum.auto()
    QA3 = enum.auto()
    PRODUCTION = enum.auto()
    SANDBOX = enum.auto()
    STAGING = enum.auto()
    LOCAL = enum.auto()

    @classmethod
    def current(cls):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return cls(_mapping[ENVIRONMENT])


_mapping = {
    "maven-clinic-sandbox": Environment.SANDBOX,
    "qa1-maven-clinic-qa": Environment.QA1,
    "maven-clinic-qa1": Environment.QA1,
    "qa2-maven-clinic-qa": Environment.QA2,
    "maven-clinic-qa2": Environment.QA2,
    "maven-clinic-qa3": Environment.QA3,
    "maven-clinic": Environment.PRODUCTION,
    "maven-clinic-prod": Environment.PRODUCTION,
    "maven-clinic-staging": Environment.STAGING,
    "local": Environment.LOCAL,
}

ENVIRONMENT = os.environ.get("ENVIRONMENT", "qa1-maven-clinic-qa")

maven_web_origin = {
    Environment.QA1: "https://www.qa1.mvnapp.net",
    Environment.QA2: "https://www.qa2.mvnapp.net",
    Environment.PRODUCTION: "https://www.mavenclinic.com",
    Environment.STAGING: "https://www.staging.mvnapp.net",
    Environment.LOCAL: "https://www.qa1.mvnapp.net",
}


def current_web_origin():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    return maven_web_origin.get(Environment.current())
