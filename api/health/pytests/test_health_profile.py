import datetime
from unittest.mock import ANY

import pytest

from health.data_models.risk_flag import RiskFlag, RiskFlagSeverity


@pytest.fixture
def hp(default_user, db):
    # clear the default generated content
    default_user.health_profile.json = {}
    return default_user.health_profile


class TestHealthProfile:
    def test_add_a_child(self, hp):
        assert hp.children == []

        today = str(datetime.datetime.utcnow().date())
        hp.add_a_child(today, name="Alpha")
        assert hp.children == [{"id": ANY, "name": "Alpha", "birthday": today}]

    def test_search_children_by_birthday_range(self, hp):
        hp.json = {
            "children": [
                {"id": "uuid-1", "name": "child1", "birthday": "2000-01-02"},
                {"id": "uuid-2", "name": "child2", "birthday": "1998-12-21"},
                {"id": "uuid-3", "name": "child3", "birthday": "1995-07-06"},
                {"id": "uuid-4", "name": "child4", "birthday": "1995-07-06"},
            ]
        }
        result = hp.search_children_by_birthday_range(
            datetime.date(2000, 1, 2), datetime.date(2000, 1, 3)
        )
        assert result == [{"name": "child1", "birthday": "2000-01-02", "id": "uuid-1"}]

        result = hp.search_children_by_birthday_range(
            datetime.date(1995, 7, 1), datetime.date(1995, 7, 31)
        )
        assert result == [
            {"name": "child3", "birthday": "1995-07-06", "id": "uuid-3"},
            {"name": "child4", "birthday": "1995-07-06", "id": "uuid-4"},
        ]

        result = hp.search_children_by_birthday_range(
            datetime.date(1998, 12, 1), datetime.date(1998, 12, 21)
        )
        assert result == [{"name": "child2", "birthday": "1998-12-21", "id": "uuid-2"}]

        result = hp.search_children_by_birthday_range(
            datetime.date(2001, 12, 31), datetime.date(2017, 1, 1)
        )
        assert result == []

    def test_set_user_age_flag(self, hp, db):
        assert hp.user.current_risk_flags() == []
        db.session.add(
            RiskFlag(name="Advanced Maternal Age", severity=RiskFlagSeverity.HIGH_RISK)
        )
        db.session.commit()
        today = datetime.datetime.utcnow().date()
        hp.birthday = today - datetime.timedelta(days=(36 * 365.25))  # Age >= 35
        db.session.add(hp)
        db.session.commit()
        db.session.refresh(hp.user)
        assert len(hp.user.current_risk_flags()) == 1
        # risk flag should be added
        assert hp.user.current_risk_flags()[0].name == "Advanced Maternal Age"
        member_risk_flags = hp.user.get_member_risks()
        assert member_risk_flags[0].end is None
        # risk flag should be ended
        hp.birthday = today - datetime.timedelta(days=(34 * 365.25))  # Age < 35
        db.session.add(hp)
        db.session.commit()
        db.session.refresh(hp.user)
        assert len(hp.user.current_risk_flags()) == 0
