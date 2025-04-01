from datetime import date, timedelta

from sqlalchemy.orm import Session

from authn.models.user import User
from health.models.health_profile import HealthProfile


class TestHealthProfileChildren:
    def test_replace_auto_child(self, default_user: User, session: Session):
        birthday = date.today()
        user = default_user
        hp: HealthProfile = user.health_profile
        hp.json.clear()
        hp.due_date = birthday - timedelta(weeks=4)
        hp.add_child_using_due_date()
        session.add(hp)
        session.commit()

        hp.add_a_child(birthday)
        session.add(hp)
        session.commit()

        assert len(hp.children) == 1
        assert hp.children[0]["name"] != "Automatically Added"
        assert hp.children[0]["birthday"] == birthday.isoformat()

    def test_dont_replace_auto_child(self, default_user: User, session: Session):
        birthday = date.today()
        user = default_user
        hp: HealthProfile = user.health_profile
        hp.json.clear()
        hp.due_date = birthday - timedelta(weeks=52)
        hp.add_child_using_due_date()
        session.add(hp)
        session.commit()

        hp.add_a_child(birthday)
        session.add(hp)
        session.commit()

        assert len(hp.children) == 2
        assert hp.children[0]["name"] == "Automatically Added"
        assert hp.children[0]["birthday"] == hp.due_date.isoformat()
        assert hp.children[1]["name"] != "Automatically Added"
        assert hp.children[1]["birthday"] == birthday.isoformat()

    def test_dont_replace_child(self, default_user: User, session: Session):
        birthday = date.today()
        user = default_user
        hp: HealthProfile = user.health_profile
        hp.json.clear()
        hp.due_date = birthday - timedelta(weeks=47)
        hp.add_a_child(hp.due_date)
        session.add(hp)
        session.commit()

        hp.add_a_child(birthday)
        session.add(hp)
        session.commit()

        assert len(hp.children) == 2
        assert hp.children[0]["name"] != "Automatically Added"
        assert hp.children[0]["birthday"] == hp.due_date.isoformat()
        assert hp.children[1]["name"] != "Automatically Added"
        assert hp.children[1]["birthday"] == birthday.isoformat()
