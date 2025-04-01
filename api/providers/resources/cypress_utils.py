import random
from datetime import datetime

from ddtrace import tracer
from flask import abort, request
from werkzeug.exceptions import BadRequest

from appointments.models.cancellation_policy import (
    CancellationPolicy,
    CancellationPolicyName,
)
from appointments.models.schedule import Schedule
from authn.models.user import User
from common.constants import Environment
from common.services.api import AuthenticatedResource
from models.base import db
from models.products import Product
from models.profiles import State
from models.verticals_and_specialties import Vertical
from providers.domain.model import Provider
from providers.schemas.cypress_utils import PostTestProvidersSchema

FIRST_NAMES = [
    "Sheryl",
    "Shirley",
    "Sierra",
    "Sonia",
    "Sonya",
    "Sophia",
    "Stacey",
    "Stacie",
    "Stacy",
    "Stefanie",
    "Stephanie",
    "Sue",
    "Summer",
    "Susan",
    "Suzanne",
    "Sydney",
    "Sylvia",
    "Tabitha",
    "Tamara",
    "Tami",
    "Tammie",
    "Tammy",
    "Tanya",
    "Tara",
    "Tasha",
    "Taylor",
    "Teresa",
    "Terri",
    "Terry",
    "Douglas",
    "Drew",
    "Duane",
    "Dustin",
    "Dwayne",
    "Dylan",
    "Earl",
    "Eddie",
    "Edgar",
    "Eduardo",
    "Edward",
    "Edwin",
    "Elijah",
    "Eric",
    "Erik",
    "Ernest",
    "Ethan",
    "Eugene",
    "Evan",
    "Fernando",
    "Francis",
]

LAST_NAMES = [
    "Smith",
    "Johnson",
    "Williams",
    "Brown",
    "Jones",
    "Miller",
    "Rodriguez",
    "Wilson",
    "Martinez",
    "Anderson",
    "Taylor",
    "Thomas",
    "Hernandez",
    "Moore",
    "Martin",
    "Jackson",
    "Thompson",
    "White",
    "Lopez",
    "Lee",
    "Gonzalez",
    "Harris",
    "Clark",
    "Lewis",
    "Robinson",
    "Walker",
    "Perez",
    "Hall",
    "Young",
    "Allen",
    "Sanchez",
    "Wright",
    "King",
    "Scott",
    "Green",
    "Baker",
    "Adams",
    "Nelson",
    "Hill",
    "Ramirez",
    "Campbell",
    "Mitchell",
    "Roberts",
    "Carter",
    "Phillips",
    "Evans",
    "Turner",
    "Torres",
    "Parker",
    "Collins",
    "Edwards",
    "Stewart",
    "Flores",
    "Morris",
    "Nguyen",
    "Murphy",
    "Rivera",
    "Cook",
    "Rogers",
    "Morgan",
    "Peterson",
    "Cooper",
    "Reed",
    "Bailey",
    "Bell",
    "Gomez",
    "Kelly",
    "Howard",
    "Ward",
    "Cox",
    "Diaz",
    "Richardson",
    "Wood",
    "Watson",
    "Brooks",
    "Bennett",
    "Gray",
    "James",
    "Reyes",
    "Cruz",
    "Hughes",
    "Price",
    "Myers",
    "Long",
    "Foster",
    "Sanders",
    "Ross",
    "Morales",
    "Powell",
    "Sullivan",
    "Russell",
    "Ortiz",
    "Jenkins",
    "Gutierrez",
    "Perry",
    "Butler",
    "Barnes",
    "Fisher",
    "Henderson",
    "Coleman",
    "Simmons",
    "Patterson",
    "Jordan",
    "Reynolds",
    "Hamilton",
    "Graham",
    "Kim",
    "Gonzales",
    "Alexander",
    "Ramos",
    "Wallace",
    "Griffin",
    "West",
    "Cole",
    "Hayes",
    "Chavez",
    "Gibson",
    "Bryant",
    "Ellis",
    "Stevens",
    "Murray",
]


class CypressProvidersResource(AuthenticatedResource):
    """
    This resource is intended for cypress testing only.

    All endpoints should only able to be used in non-production environments
    """

    @tracer.wrap()
    def post(self) -> dict:
        """
        Creates a provider to be used in cypress testing

        @param state_name: the name of the state that the provider is both in and certified in
        @param vertical_name: the name of the provider's vertical
        @param timezone: the name of the provider's timezone
        """
        if Environment.current() == Environment.PRODUCTION:
            abort(404)

        try:
            request_json = request.json if request.is_json else {}
        except BadRequest:
            request_json = {}
        post_request = PostTestProvidersSchema().load(request_json)

        state_name = post_request["state_name"]
        state = db.session.query(State).filter(State.name == state_name).one_or_none()
        if not state:
            abort(400, f"No state found with name {state_name}")

        vertical_name = post_request["vertical_name"]
        vertical = (
            db.session.query(Vertical)
            .filter(Vertical.name == vertical_name)
            .one_or_none()
        )
        if not vertical:
            abort(400, f"No vertical found with name {vertical_name}")

        try:
            request_json = request.json if request.is_json else None
        except BadRequest:
            request_json = None
        post_request = PostTestProvidersSchema().load(request_json)

        # Create user profile
        first_name = random.choices(FIRST_NAMES)[0]
        last_name = random.choices(LAST_NAMES)[0]
        password = "simpleisawesome1*"
        username = f"{first_name}_{last_name}"
        user = User(
            username=username,
            first_name=first_name,
            last_name=last_name,
            email=f"test+cypress_provider+{first_name}_{last_name}+{datetime.utcnow().isoformat()}@mavenclinic.com",
            password=password,
            roles=[],
            timezone=post_request["timezone"],
        )
        schedule = Schedule(
            name=f"schedule for {user.id}",
            user_id=user.id,
        )
        user.schedule = schedule

        cancellation_policy_name = CancellationPolicyName.MODERATE
        cancellation_policy = (
            db.session.query(CancellationPolicy)
            .filter(CancellationPolicy.name == cancellation_policy_name)
            .one_or_none()
        )
        if not cancellation_policy:
            abort(
                400,
                f"No cancellation_policy found with name {cancellation_policy_name}",
            )

        Product(
            vertical=vertical,
            description="test product",
            minutes=10,
            price=10,
            user_id=user.id,
            practitioner=user,
            prep_buffer=10,
        )
        Provider(
            user_id=user.id,
            user=user,
            username=username,
            show_in_enterprise=True,
            show_in_marketplace=True,
            first_name=first_name,
            last_name=last_name,
            show_when_unavailable=True,
            anonymous_allowed=True,
            messaging_enabled=True,
            booking_buffer=10,
            state=state,
            timezone=post_request["timezone"],
            certified_states=[state],
            default_cancellation_policy=cancellation_policy,
            verticals=[vertical],
        )

        db.session.commit()
        return {
            "id": user.id,
            "email": user.email,
            "password": user.password,
        }


class CypressProviderResource(AuthenticatedResource):
    """
    This resource is intended for cypress testing only.

    All endpoints should only able to be used in non-production environments
    """

    @tracer.wrap()
    def delete(self, provider_id: int) -> None:
        """
        Deletes a given test provider
        """
        if Environment.current() == Environment.PRODUCTION:
            abort(404)

        # Deleting the user will delete the practitioner profile along with other relations
        user = db.session.query(User).filter_by(id=provider_id).one()
        db.session.delete(user)
        db.session.commit()
