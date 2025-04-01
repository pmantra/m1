from authn.models.user import User
from models.profiles import Address
from storage.connection import db
from utils.geography import us_states
from utils.log import logger

log = logger(__name__)

state_timezones = {
    "Alabama": "America/Chicago",
    "Alaska": "America/Anchorage",
    "Arizona": "America/Phoenix",
    "Arkansas": "America/Chicago",
    "California": "America/Los_Angeles",
    "Colorado": "America/Denver",
    "Connecticut": "America/New_York",
    "Delaware": "America/New_York",
    "District of Columbia": "America/New_York",
    "Florida": "America/New_York",
    "Georgia": "America/New_York",
    "Hawaii": "Pacific/Honolulu",
    "Idaho": "America/Boise",
    "Illinois": "America/Chicago",
    "Indiana": "America/Indiana/Indianapolis",
    "Iowa": "America/Chicago",
    "Kansas": "America/Chicago",
    "Kentucky": "America/New_York",
    "Louisiana": "America/Chicago",
    "Maine": "America/New_York",
    "Maryland": "America/New_York",
    "Massachusetts": "America/New_York",
    "Michigan": "America/Detroit",
    "Minnesota": "America/Chicago",
    "Mississippi": "America/Chicago",
    "Missouri": "America/Chicago",
    "Montana": "America/Denver",
    "Nebraska": "America/Chicago",
    "Nevada": "America/Los_Angeles",
    "New Hampshire": "America/New_York",
    "New Jersey": "America/New_York",
    "New Mexico": "America/Denver",
    "New York": "America/New_York",
    "North Carolina": "America/New_York",
    "North Dakota": "America/Chicago",
    "Ohio": "America/New_York",
    "Oklahoma": "America/Chicago",
    "Oregon": "America/Los_Angeles",
    "Pennsylvania": "America/New_York",
    "Rhode Island": "America/New_York",
    "South Carolina": "America/New_York",
    "South Dakota": "America/Chicago",
    "Tennessee": "America/Chicago",
    "Texas": "America/Chicago",
    "Utah": "America/Denver",
    "Vermont": "America/New_York",
    "Virginia": "America/New_York",
    "Washington": "America/Los_Angeles",
    "West Virginia": "America/New_York",
    "Wisconsin": "America/Chicago",
    "Wyoming": "America/Denver",
}

other_timezones = {
    "Bavaria": "Europe/Berlin",
    "Beckenham": "Europe/London",
    "British Columbia": "America/Vancouver",
    "Cambridgeshire": "Europe/London",
    "Illinois/USA": "America/Chicago",
    "Japan": "Asia/Tokyo",
    "London": "Europe/London",
    "london": "Europe/London",
    "London, City of": "Europe/London",
    "Dublin": "Europe/Dublin",
    "East Sussex": "Europe/London",
    "Essex": "Europe/London",
    "Hessen": "Europe/Berlin",
    "Hong Kong": "Asia/Hong_Kong",
    "Lazio": "Europe/Rome",
    "New South Wales": "Australia/Sydney",
    "NRW": "Europe/Berlin",
    "ON": "America/Toronto",
    "Ontario": "America/Toronto",
    "Surrey": "Europe/London",
    "Uusimaa": "Europe/Helsinki",
}


def populate_user_timezones():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    log.info("Populating user timezones")

    users = User.query.join(User.addresses).filter(
        User.timezone == "UTC", Address.state != ""
    )
    num_users_updated = 0

    log.info(f"{users.count()} users with UTC timezone")

    for user in users:
        country = user.addresses[0].country
        state = user.addresses[0].state
        if state in us_states and country in ("US", "USA", "United States"):
            state = us_states[state]

        if state in state_timezones:
            user.timezone = state_timezones[state]
        elif state in other_timezones:
            user.timezone = other_timezones[state]

        if user.timezone == "UTC":
            log.info(
                f"Could not get timezone for {state}, defaulting to UTC",
                user_id=user.id,
            )
        else:
            db.session.commit()
            num_users_updated += 1

    log.info(f"Updated timezone for {num_users_updated} users")
