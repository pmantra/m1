import pytest

from care_advocates.models.matching_rules import (
    MatchingRule,
    MatchingRuleEntityType,
    MatchingRuleSet,
    MatchingRuleType,
)
from health.services.member_risk_service import MemberRiskService
from models.tracks import TrackName
from storage.connection import db


@pytest.fixture
def catch_all_ca(factories):
    practitioner = factories.PractitionerUserFactory.create()
    module_adoption = factories.WeeklyModuleFactory.create(name=TrackName.ADOPTION)
    module_parenting = factories.WeeklyModuleFactory.create(
        name=TrackName.PARENTING_AND_PEDIATRICS
    )
    module_pregnancy = factories.WeeklyModuleFactory.create(name=TrackName.PREGNANCY)

    db.session.add_all([module_adoption, module_parenting, module_pregnancy])
    db.session.commit()

    aa = factories.AssignableAdvocateFactory.create_with_practitioner(
        practitioner=practitioner
    )

    mrs = MatchingRuleSet(assignable_advocate=aa)

    country_mr = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.COUNTRY.value,
        matching_rule_set=mrs,
        all=True,
    )

    org_mr = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.ORGANIZATION.value,
        matching_rule_set=mrs,
        all=True,
    )

    track_mr = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.MODULE.value,
        matching_rule_set=mrs,
    )

    track_mr.identifiers.append(str(module_adoption.id))
    track_mr.identifiers.append(str(module_parenting.id))
    track_mr.identifiers.append(str(module_pregnancy.id))

    user_flag_mr = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.USER_FLAG.value,
        matching_rule_set=mrs,
        all=True,
    )

    user_flag_none_mr = MatchingRule(
        type=MatchingRuleType.EXCLUDE.value,
        entity=MatchingRuleEntityType.USER_FLAG.value,
        matching_rule_set=mrs,
        all=True,
    )

    db.session.add_all(
        [country_mr, org_mr, track_mr, mrs, user_flag_mr, user_flag_none_mr]
    )
    db.session.commit()

    return aa


def test_find_matches_for_catch_all(factories, catch_all_ca):
    user = factories.DefaultUserFactory.create()
    factories.MemberProfileFactory.create(user=user, country_code="AR")
    factories.MemberTrackFactory.create(
        name=TrackName.PARENTING_AND_PEDIATRICS,
        user=user,
    )

    user_2 = factories.DefaultUserFactory.create()
    factories.MemberProfileFactory.create(user=user_2, country_code="CL")
    factories.MemberTrackFactory.create(
        name=TrackName.ADOPTION,
        user=user_2,
    )

    user_3 = factories.DefaultUserFactory.create()
    factories.MemberProfileFactory.create(user=user_3, country_code="CL")
    factories.MemberTrackFactory.create(
        name=TrackName.ADOPTION,
        user=user_3,
    )

    assert MatchingRuleSet.find_matches_for_catch_all(
        user,
        [catch_all_ca.practitioner_id],
    ) == [catch_all_ca]
    assert MatchingRuleSet.find_matches_for_catch_all(
        user_2,
        [catch_all_ca.practitioner_id],
    ) == [catch_all_ca]
    assert MatchingRuleSet.find_matches_for_catch_all(
        user_3,
        [catch_all_ca.practitioner_id],
    ) == [catch_all_ca]


def test_find_matches_for_catch_all_vs_country_org_all_tracks(factories, catch_all_ca):
    user = factories.DefaultUserFactory.create()
    factories.MemberProfileFactory.create(user=user, country_code="AR")
    factories.MemberTrackFactory.create(
        name=TrackName.PARENTING_AND_PEDIATRICS,
        user=user,
    )

    module_adoption = factories.WeeklyModuleFactory.create(name=TrackName.ADOPTION)
    module_parenting = factories.WeeklyModuleFactory.create(
        name=TrackName.PARENTING_AND_PEDIATRICS
    )
    module_pregnancy = factories.WeeklyModuleFactory.create(name=TrackName.PREGNANCY)

    practitioner = factories.PractitionerUserFactory.create()

    aa = factories.AssignableAdvocateFactory.create_with_practitioner(
        practitioner=practitioner
    )

    mrs = MatchingRuleSet(assignable_advocate=aa)

    country_mr = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.COUNTRY.value,
        matching_rule_set=mrs,
    )
    country_mr.identifiers.append("AR")

    org_mr = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.ORGANIZATION.value,
        matching_rule_set=mrs,
        all=True,
    )

    track_mr = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.MODULE.value,
        matching_rule_set=mrs,
    )
    track_mr.identifiers.append(str(module_adoption.id))
    track_mr.identifiers.append(str(module_parenting.id))
    track_mr.identifiers.append(str(module_pregnancy.id))

    db.session.add_all([country_mr, org_mr, track_mr, mrs])
    db.session.commit()

    practitioner2 = factories.PractitionerUserFactory.create()

    aa2 = factories.AssignableAdvocateFactory.create_with_practitioner(
        practitioner=practitioner2
    )

    mrs2 = MatchingRuleSet(assignable_advocate=aa2)

    country_mr2 = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.COUNTRY.value,
        matching_rule_set=mrs2,
        all=True,
    )

    org_mr2 = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.ORGANIZATION.value,
        matching_rule_set=mrs2,
    )
    org_mr2.identifiers.append(str(user.organization.id))

    track_mr2 = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.MODULE.value,
        matching_rule_set=mrs2,
    )
    track_mr2.identifiers.append(str(module_adoption.id))
    track_mr2.identifiers.append(str(module_parenting.id))
    track_mr2.identifiers.append(str(module_pregnancy.id))

    db.session.add_all([country_mr2, org_mr2, track_mr2, mrs2])
    db.session.commit()

    assert MatchingRuleSet.find_matches_for_catch_all(
        user,
        [catch_all_ca.practitioner_id, aa.practitioner_id, aa2.practitioner_id],
    ) == [catch_all_ca]


def test_find_matches_for_catch_all_vs_any_country_any_org_track(
    factories, catch_all_ca
):
    user_parenting = factories.DefaultUserFactory.create()
    factories.MemberProfileFactory.create(user=user_parenting, country_code="AR")
    factories.MemberTrackFactory.create(
        name=TrackName.PARENTING_AND_PEDIATRICS,
        user=user_parenting,
    )

    user_adoption = factories.DefaultUserFactory.create()
    factories.MemberProfileFactory.create(user=user_adoption, country_code="AR")
    factories.MemberTrackFactory.create(
        name=TrackName.ADOPTION,
        user=user_adoption,
    )
    factories.WeeklyModuleFactory.create(name=TrackName.ADOPTION)
    module_parenting = factories.WeeklyModuleFactory.create(
        name=TrackName.PARENTING_AND_PEDIATRICS
    )

    practitioner = factories.PractitionerUserFactory.create()

    aa = factories.AssignableAdvocateFactory.create_with_practitioner(
        practitioner=practitioner
    )

    mrs = MatchingRuleSet(assignable_advocate=aa)

    country_mr = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.COUNTRY.value,
        matching_rule_set=mrs,
        all=True,
    )

    org_mr = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.ORGANIZATION.value,
        matching_rule_set=mrs,
        all=True,
    )

    track_mr = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.MODULE.value,
        matching_rule_set=mrs,
    )
    track_mr.identifiers.append(str(module_parenting.id))

    db.session.add_all([country_mr, org_mr, track_mr, mrs])
    db.session.commit()

    assert set(
        MatchingRuleSet.find_matches_for_catch_all(
            user_parenting,
            [catch_all_ca.practitioner_id, aa.practitioner_id],
        )
    ) == {aa, catch_all_ca}
    assert MatchingRuleSet.find_matches_for_catch_all(
        user_adoption,
        [catch_all_ca.practitioner_id, aa.practitioner_id],
    ) == [catch_all_ca]


def test_find_matches_for_catch_all_vs_country_any_org_track(factories, catch_all_ca):
    user_parenting = factories.DefaultUserFactory.create()
    factories.MemberProfileFactory.create(user=user_parenting, country_code="JP")
    factories.MemberTrackFactory.create(
        name=TrackName.PARENTING_AND_PEDIATRICS,
        user=user_parenting,
    )

    user_adoption = factories.DefaultUserFactory.create()
    factories.MemberProfileFactory.create(user=user_adoption, country_code="JP")
    factories.MemberTrackFactory.create(
        name=TrackName.PARENTING_AND_PEDIATRICS,
        user=user_adoption,
    )
    factories.WeeklyModuleFactory.create(name=TrackName.ADOPTION)
    module_parenting = factories.WeeklyModuleFactory.create(
        name=TrackName.PARENTING_AND_PEDIATRICS
    )

    practitioner = factories.PractitionerUserFactory.create()

    aa = factories.AssignableAdvocateFactory.create_with_practitioner(
        practitioner=practitioner
    )

    mrs = MatchingRuleSet(assignable_advocate=aa)

    country_mr = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.COUNTRY.value,
        matching_rule_set=mrs,
    )
    country_mr.identifiers.append("JP")

    org_mr = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.ORGANIZATION.value,
        matching_rule_set=mrs,
        all=True,
    )

    track_mr = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.MODULE.value,
        matching_rule_set=mrs,
    )
    track_mr.identifiers.append(str(module_parenting.id))

    db.session.add_all([country_mr, org_mr, track_mr, mrs])
    db.session.commit()

    assert MatchingRuleSet.find_matches_for_catch_all(
        user_adoption,
        [catch_all_ca.practitioner_id, aa.practitioner_id],
    ) == [catch_all_ca]
    assert MatchingRuleSet.find_matches_for_catch_all(
        user_parenting,
        [catch_all_ca.practitioner_id, aa.practitioner_id],
    ) == [catch_all_ca]


def test_find_matches_for_catch_all_vs_any_country_excluded_org_all_tracks(
    factories, catch_all_ca
):
    user = factories.DefaultUserFactory.create()
    factories.MemberProfileFactory.create(user=user, country_code="AR")
    factories.MemberTrackFactory.create(
        name=TrackName.PARENTING_AND_PEDIATRICS,
        user=user,
    )

    excluded_user = factories.DefaultUserFactory.create()
    factories.MemberTrackFactory.create(
        name=TrackName.PARENTING_AND_PEDIATRICS,
        user=excluded_user,
    )

    module_adoption = factories.WeeklyModuleFactory.create(name=TrackName.ADOPTION)
    module_parenting = factories.WeeklyModuleFactory.create(
        name=TrackName.PARENTING_AND_PEDIATRICS
    )
    module_pregnancy = factories.WeeklyModuleFactory.create(name=TrackName.PREGNANCY)

    practitioner = factories.PractitionerUserFactory.create()

    aa = factories.AssignableAdvocateFactory.create_with_practitioner(
        practitioner=practitioner
    )

    mrs = MatchingRuleSet(assignable_advocate=aa)

    country_mr = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.COUNTRY.value,
        matching_rule_set=mrs,
        all=True,
    )

    org_mr = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.ORGANIZATION.value,
        matching_rule_set=mrs,
        all=True,
    )

    org_exclude_mr = MatchingRule(
        type=MatchingRuleType.EXCLUDE.value,
        entity=MatchingRuleEntityType.ORGANIZATION.value,
        matching_rule_set=mrs,
    )
    org_exclude_mr.identifiers.append(str(excluded_user.organization.id))

    track_mr = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.MODULE.value,
        matching_rule_set=mrs,
    )
    track_mr.identifiers.append(str(module_adoption.id))
    track_mr.identifiers.append(str(module_parenting.id))
    track_mr.identifiers.append(str(module_pregnancy.id))

    db.session.add_all([country_mr, org_mr, org_exclude_mr, track_mr, mrs])
    db.session.commit()

    assert set(
        MatchingRuleSet.find_matches_for_catch_all(
            user,
            [catch_all_ca.practitioner_id, aa.practitioner_id],
        )
    ) == {aa, catch_all_ca}
    assert MatchingRuleSet.find_matches_for_catch_all(
        excluded_user,
        [catch_all_ca.practitioner_id, aa.practitioner_id],
    ) == [catch_all_ca]


def test_find_matches_for_catch_all_vs_any_country_any_org_track_risk_factors(
    factories, catch_all_ca, risk_flags
):
    user_1 = factories.DefaultUserFactory.create(
        email="abc.xyz1@mavenclinic.com",
        password="",
    )
    factories.MemberProfileFactory.create(user=user_1, country_code="JP")
    factories.MemberTrackFactory.create(name=TrackName.PREGNANCY, user=user_1)
    MemberRiskService(user_1.id).set_risk("High")

    user_2 = factories.DefaultUserFactory.create(
        email="abc.xyz2@mavenclinic.com",
        password="",
    )
    factories.MemberProfileFactory.create(user=user_2, country_code="JP")
    factories.MemberTrackFactory.create(name=TrackName.PREGNANCY, user=user_2)
    MemberRiskService(user_1.id).set_risk("High2")

    user_3 = factories.DefaultUserFactory.create()
    factories.MemberProfileFactory.create(user=user_3, country_code="JP")
    factories.MemberTrackFactory.create(name=TrackName.PREGNANCY, user=user_3)

    factories.WeeklyModuleFactory.create(name=TrackName.ADOPTION)
    factories.WeeklyModuleFactory.create(name=TrackName.PARENTING_AND_PEDIATRICS)
    module_pregnancy = factories.WeeklyModuleFactory.create(name=TrackName.PREGNANCY)

    practitioner = factories.PractitionerUserFactory.create()

    aa = factories.AssignableAdvocateFactory.create_with_practitioner(
        practitioner=practitioner
    )

    mrs = MatchingRuleSet(assignable_advocate=aa)

    country_mr = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.COUNTRY.value,
        matching_rule_set=mrs,
        all=True,
    )

    org_mr = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.ORGANIZATION.value,
        matching_rule_set=mrs,
        all=True,
    )

    track_mr = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.MODULE.value,
        matching_rule_set=mrs,
    )
    track_mr.identifiers.append(str(module_pregnancy.id))

    user_flag_mr = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.USER_FLAG.value,
        matching_rule_set=mrs,
    )
    user_flag_mr.identifiers.append(str(risk_flags["High"].id))

    db.session.add_all([country_mr, org_mr, track_mr, user_flag_mr, mrs])
    db.session.commit()

    assert MatchingRuleSet.find_matches_for_catch_all(
        user_1,
        [catch_all_ca.practitioner_id, aa.practitioner_id],
    ) == [catch_all_ca]
    assert MatchingRuleSet.find_matches_for_catch_all(
        user_2,
        [catch_all_ca.practitioner_id, aa.practitioner_id],
    ) == [catch_all_ca]
    assert MatchingRuleSet.find_matches_for_catch_all(
        user_3,
        [catch_all_ca.practitioner_id, aa.practitioner_id],
    ) == [catch_all_ca]
