from care_advocates.models.matching_rules import (
    MatchingRule,
    MatchingRuleEntityType,
    MatchingRuleSet,
    MatchingRuleType,
)
from health.services.member_risk_service import MemberRiskService
from models.tracks import TrackName


def test_find_matches_for(factories, session):
    user_1 = factories.DefaultUserFactory.create()
    factories.MemberProfileFactory.create(user=user_1, country_code="AR")

    factories.MemberTrackFactory.create(
        name=TrackName.PARENTING_AND_PEDIATRICS,
        user=user_1,
    )
    user_2 = factories.DefaultUserFactory.create()
    factories.MemberProfileFactory.create(user=user_2, country_code="CL")
    factories.MemberTrackFactory.create(
        name=TrackName.PARENTING_AND_PEDIATRICS,
        user=user_2,
    )

    module = factories.WeeklyModuleFactory.create(
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
    country_mr.identifiers.append("AR")

    org_mr = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.ORGANIZATION.value,
        matching_rule_set=mrs,
    )
    org_mr.identifiers.append(str(user_1.organization.id))
    org_mr.identifiers.append(str(user_2.organization.id))

    track_mr = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.MODULE.value,
        matching_rule_set=mrs,
    )
    track_mr.identifiers.append(str(module.id))

    session.add_all([country_mr, org_mr, track_mr, mrs])
    session.commit()

    assert MatchingRuleSet.find_matches_for(user_1, [aa.practitioner_id]) == [aa]
    assert MatchingRuleSet.find_matches_for(user_2, [aa.practitioner_id]) == []


def test_find_matches_for_available_advocates(factories, session):
    user = factories.DefaultUserFactory.create()
    factories.MemberProfileFactory.create(user=user, country_code="AR")
    factories.MemberTrackFactory.create(
        name=TrackName.PARENTING_AND_PEDIATRICS,
        user=user,
    )
    module = factories.WeeklyModuleFactory.create(
        name=TrackName.PARENTING_AND_PEDIATRICS
    )

    practitioner = factories.PractitionerUserFactory.create()
    other_practitioner = factories.PractitionerUserFactory.create()

    aa = factories.AssignableAdvocateFactory.create_with_practitioner(
        practitioner=practitioner
    )

    other_aa = factories.AssignableAdvocateFactory.create_with_practitioner(
        practitioner=other_practitioner
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
    )
    org_mr.identifiers.append(str(user.organization.id))

    track_mr = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.MODULE.value,
        matching_rule_set=mrs,
    )
    track_mr.identifiers.append(str(module.id))

    other_mrs = MatchingRuleSet(assignable_advocate=other_aa)

    other_country_mr = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.COUNTRY.value,
        matching_rule_set=other_mrs,
    )
    other_country_mr.identifiers.append("AR")

    other_org_mr = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.ORGANIZATION.value,
        matching_rule_set=other_mrs,
        all=True,
    )

    other_track_mr = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.MODULE.value,
        matching_rule_set=other_mrs,
    )

    other_user = factories.DefaultUserFactory.create()
    factories.MemberProfileFactory.create(user=other_user, country_code="AR")
    factories.MemberTrackFactory.create(name=TrackName.POSTPARTUM, user=other_user)

    other_module = factories.WeeklyModuleFactory.create(name=TrackName.POSTPARTUM)
    other_track_mr.identifiers.append(str(other_module.id))

    session.add_all([country_mr, org_mr, track_mr, other_track_mr, mrs])
    session.add_all([other_country_mr, other_org_mr, other_mrs])
    session.commit()

    assert MatchingRuleSet.find_matches_for(
        user=user,
        available_advocate_ids=[aa.practitioner_id],
    ) == [aa]
    assert (
        MatchingRuleSet.find_matches_for(
            user=user,
            available_advocate_ids=[],
        )
        == []
    )
    assert MatchingRuleSet.find_matches_for(
        user=other_user,
        available_advocate_ids=[other_aa.practitioner_id],
    ) == [other_aa]


def test_find_matches_for_country_any_org_and_track(factories, session):
    user = factories.DefaultUserFactory.create()
    factories.MemberProfileFactory.create(user=user, country_code="CL")
    factories.MemberTrackFactory.create(name=TrackName.ADOPTION, user=user)

    other_user = factories.DefaultUserFactory.create()
    factories.MemberProfileFactory.create(user=other_user, country_code="AR")
    factories.MemberTrackFactory.create(name=TrackName.EGG_FREEZING, user=other_user)
    module = factories.WeeklyModuleFactory.create(name=TrackName.ADOPTION)
    other_module = factories.WeeklyModuleFactory.create(name=TrackName.EGG_FREEZING)

    practitioner = factories.PractitionerUserFactory.create()

    aa = factories.AssignableAdvocateFactory.create_with_practitioner(
        practitioner=practitioner
    )

    practitioner2 = factories.PractitionerUserFactory.create()
    factories.AssignableAdvocateFactory.create_with_practitioner(
        practitioner=practitioner2
    )

    mrs = MatchingRuleSet(assignable_advocate=aa)

    country_mr = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.COUNTRY.value,
        matching_rule_set=mrs,
    )
    country_mr.identifiers.append("AR")
    country_mr.identifiers.append("CL")

    org_mr = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.ORGANIZATION.value,
        all=True,
        matching_rule_set=mrs,
    )

    track_mr = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.MODULE.value,
        matching_rule_set=mrs,
    )
    track_mr.identifiers.append(str(module.id))
    track_mr.identifiers.append(str(other_module.id))

    session.add_all([country_mr, org_mr, track_mr, mrs])
    session.commit()

    assert MatchingRuleSet.find_matches_for(user, [aa.practitioner_id]) == [aa]
    assert MatchingRuleSet.find_matches_for(
        other_user,
        [aa.practitioner_id],
    ) == [aa]


def test_find_matches_for_organization_and_module(factories, session):

    user = factories.DefaultUserFactory.create()
    factories.MemberTrackFactory.create(name=TrackName.ADOPTION, user=user)

    other_user = factories.DefaultUserFactory.create()
    factories.MemberTrackFactory.create(name=TrackName.EGG_FREEZING, user=other_user)
    module = factories.WeeklyModuleFactory.create(name=TrackName.ADOPTION)
    factories.WeeklyModuleFactory.create(name=TrackName.EGG_FREEZING)

    practitioner = factories.PractitionerUserFactory.create()

    aa = factories.AssignableAdvocateFactory.create_with_practitioner(
        practitioner=practitioner
    )

    mrs = MatchingRuleSet(assignable_advocate=aa)
    country_mr = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.COUNTRY.value,
        all=True,
        matching_rule_set=mrs,
    )
    org_mr = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.ORGANIZATION.value,
        matching_rule_set=mrs,
    )
    org_mr.identifiers.append(str(user.organization.id))

    track_mr = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.MODULE.value,
        matching_rule_set=mrs,
    )
    track_mr.identifiers.append(str(module.id))

    session.add_all([country_mr, org_mr, track_mr, mrs])
    session.commit()

    assert MatchingRuleSet.find_matches_for(user, [aa.practitioner_id]) == [aa]
    assert (
        MatchingRuleSet.find_matches_for(
            other_user,
            [aa.practitioner_id],
        )
        == []
    )


def test_find_matches_for_any_country_any_org_and_track(factories, session):

    user = factories.DefaultUserFactory.create()
    factories.MemberTrackFactory.create(name=TrackName.ADOPTION, user=user)

    other_user = factories.DefaultUserFactory.create()
    factories.MemberTrackFactory.create(name=TrackName.EGG_FREEZING, user=other_user)
    module = factories.WeeklyModuleFactory.create(name=TrackName.ADOPTION)
    other_module = factories.WeeklyModuleFactory.create(name=TrackName.EGG_FREEZING)

    practitioner = factories.PractitionerUserFactory.create()

    aa = factories.AssignableAdvocateFactory.create_with_practitioner(
        practitioner=practitioner
    )

    practitioner2 = factories.PractitionerUserFactory.create()
    factories.AssignableAdvocateFactory.create_with_practitioner(
        practitioner=practitioner2
    )

    mrs = MatchingRuleSet(assignable_advocate=aa)
    country_mr = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.COUNTRY.value,
        all=True,
        matching_rule_set=mrs,
    )

    org_mr = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.ORGANIZATION.value,
        all=True,
        matching_rule_set=mrs,
    )

    track_mr = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.MODULE.value,
        matching_rule_set=mrs,
    )
    track_mr.identifiers.append(str(module.id))
    track_mr.identifiers.append(str(other_module.id))

    session.add_all([country_mr, org_mr, track_mr])
    session.commit()

    assert MatchingRuleSet.find_matches_for(user, [aa.practitioner_id]) == [aa]
    assert MatchingRuleSet.find_matches_for(
        other_user,
        [aa.practitioner_id],
    ) == [aa]


def test_find_matches_for_country_any_org_and_track_and_risk_factors(
    factories, session, risk_flags
):
    user = factories.DefaultUserFactory.create()

    factories.MemberProfileFactory.create(user=user, country_code="IN")
    factories.MemberTrackFactory.create(name=TrackName.PREGNANCY, user=user)
    module = factories.WeeklyModuleFactory.create(name=TrackName.PREGNANCY)
    other_module = factories.WeeklyModuleFactory.create(name=TrackName.EGG_FREEZING)

    member_risks = MemberRiskService(user.id)
    member_risks.set_risk("High")

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
    country_mr.identifiers.append("US")
    country_mr.identifiers.append("IN")

    org_mr = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.ORGANIZATION.value,
        all=True,
        matching_rule_set=mrs,
    )

    track_mr = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.MODULE.value,
        matching_rule_set=mrs,
    )
    track_mr.identifiers.append(str(module.id))
    track_mr.identifiers.append(str(other_module.id))

    user_flag_mr = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.USER_FLAG.value,
        matching_rule_set=mrs,
    )
    user_flag_mr.identifiers.append(risk_flags["High"].id)

    session.add_all([country_mr, org_mr, track_mr, user_flag_mr])
    session.commit()

    assert MatchingRuleSet.find_matches_for(
        user,
        [aa.practitioner_id],
    ) == [aa]

    user.email = "abc.xyz2@mavenclinic.com"
    member_risks.set_risk("High")
    assert MatchingRuleSet.find_matches_for(
        user,
        [aa.practitioner_id],
    ) == [aa]

    user.email = "abc.xyz3@mavenclinic.com"

    member_risks.clear_risk("High")
    member_risks.set_risk("High2")
    assert (
        MatchingRuleSet.find_matches_for(
            user,
            [aa.practitioner_id],
        )
        == []
    )
    member_risks.clear_risk("High2")

    user.email = "abc.xyz4@mavenclinic.com"
    assert (
        MatchingRuleSet.find_matches_for(
            user,
            [aa.practitioner_id],
        )
        == []
    )


def test_find_matches_for_country_any_org_and_non_pregnancy_track_and_risk_factors(
    factories, risk_flags, session
):
    user_1 = factories.DefaultUserFactory.create()
    MemberRiskService(user_1.id).set_risk("High")

    factories.MemberProfileFactory.create(user=user_1, country_code="IN")
    track_1 = factories.MemberTrackFactory.create(name=TrackName.ADOPTION, user=user_1)
    user_1.active_tracks.append(track_1)

    user_2 = factories.DefaultUserFactory.create()
    factories.MemberProfileFactory.create(user=user_2, country_code="US")
    track_2 = factories.MemberTrackFactory.create(
        name=TrackName.EGG_FREEZING, user=user_2
    )
    user_2.active_tracks.append(track_2)

    user_3 = factories.DefaultUserFactory.create()
    MemberRiskService(user_3.id).set_risk("High")
    MemberRiskService(user_3.id).set_risk("High2")
    factories.MemberProfileFactory.create(user=user_3, country_code="US")
    track_3 = factories.MemberTrackFactory.create(name=TrackName.ADOPTION, user=user_3)
    user_3.active_tracks.append(track_3)

    module = factories.WeeklyModuleFactory.create(name=TrackName.ADOPTION)
    other_module = factories.WeeklyModuleFactory.create(name=TrackName.EGG_FREEZING)

    practitioner = factories.PractitionerUserFactory.create()

    aa = factories.AssignableAdvocateFactory.create_with_practitioner(
        practitioner=practitioner
    )

    practitioner2 = factories.PractitionerUserFactory.create()
    factories.AssignableAdvocateFactory.create_with_practitioner(
        practitioner=practitioner2
    )

    mrs = MatchingRuleSet(assignable_advocate=aa)
    country_mr = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.COUNTRY.value,
        matching_rule_set=mrs,
    )
    country_mr.identifiers.append("US")
    country_mr.identifiers.append("IN")

    org_mr = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.ORGANIZATION.value,
        all=True,
        matching_rule_set=mrs,
    )

    track_mr = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.MODULE.value,
        matching_rule_set=mrs,
    )
    track_mr.identifiers.append(str(module.id))
    track_mr.identifiers.append(str(other_module.id))

    user_flag_mr = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.USER_FLAG.value,
        matching_rule_set=mrs,
    )
    user_flag_mr.identifiers.append(risk_flags["High"].id)
    user_flag_mr.identifiers.append(risk_flags["High2"].id)

    session.add_all([country_mr, org_mr, track_mr, user_flag_mr])
    session.commit()

    assert MatchingRuleSet.find_matches_for(
        user_1,
        [aa.practitioner_id],
    ) == [aa]
    assert MatchingRuleSet.find_matches_for(
        user_2,
        [aa.practitioner_id],
    ) == [aa]
    assert MatchingRuleSet.find_matches_for(
        user_3,
        [aa.practitioner_id],
    ) == [aa]


def test_find_matches_for_country_any_org_and_track_and_any_risk_factors(
    factories, session, risk_flags
):
    user_1 = factories.DefaultUserFactory.create()
    MemberRiskService(user_1.id).set_risk("High")
    factories.MemberProfileFactory.create(user=user_1, country_code="IN")
    track_1 = factories.MemberTrackFactory.create(name=TrackName.PREGNANCY, user=user_1)
    user_1.active_tracks.append(track_1)

    user_2 = factories.DefaultUserFactory.create()
    MemberRiskService(user_2.id).set_risk("High2")
    factories.MemberProfileFactory.create(user=user_2, country_code="IN")
    track_2 = factories.MemberTrackFactory.create(name=TrackName.PREGNANCY, user=user_2)
    user_2.active_tracks.append(track_2)

    user_3 = factories.DefaultUserFactory.create()
    MemberRiskService(user_3.id).set_risk("High")
    factories.MemberProfileFactory.create(user=user_3, country_code="US")
    track_3 = factories.MemberTrackFactory.create(name=TrackName.PREGNANCY, user=user_3)
    user_3.active_tracks.append(track_3)

    user_4 = factories.DefaultUserFactory.create()
    factories.MemberProfileFactory.create(user=user_4, country_code="US")
    factories.MemberTrackFactory.create(name=TrackName.EGG_FREEZING, user=user_4)

    user_5 = factories.DefaultUserFactory.create()
    factories.MemberProfileFactory.create(user=user_5, country_code="US")
    factories.MemberTrackFactory.create(name=TrackName.PREGNANCY, user=user_5)

    module = factories.WeeklyModuleFactory.create(name=TrackName.PREGNANCY)
    other_module = factories.WeeklyModuleFactory.create(name=TrackName.EGG_FREEZING)

    practitioner = factories.PractitionerUserFactory.create()

    aa = factories.AssignableAdvocateFactory.create_with_practitioner(
        practitioner=practitioner
    )

    practitioner2 = factories.PractitionerUserFactory.create()
    factories.AssignableAdvocateFactory.create_with_practitioner(
        practitioner=practitioner2
    )

    mrs = MatchingRuleSet(assignable_advocate=aa)
    country_mr = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.COUNTRY.value,
        matching_rule_set=mrs,
    )
    country_mr.identifiers.append("US")
    country_mr.identifiers.append("IN")

    org_mr = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.ORGANIZATION.value,
        all=True,
        matching_rule_set=mrs,
    )

    track_mr = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.MODULE.value,
        matching_rule_set=mrs,
    )
    track_mr.identifiers.append(str(module.id))
    track_mr.identifiers.append(str(other_module.id))

    user_flag_mr = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.USER_FLAG.value,
        all=True,
        matching_rule_set=mrs,
    )

    session.add_all([country_mr, org_mr, track_mr, user_flag_mr])
    session.commit()

    assert MatchingRuleSet.find_matches_for(
        user_1,
        [aa.practitioner_id],
    ) == [aa]
    assert MatchingRuleSet.find_matches_for(
        user_2,
        [aa.practitioner_id],
    ) == [aa]
    assert MatchingRuleSet.find_matches_for(
        user_3,
        [aa.practitioner_id],
    ) == [aa]
    assert MatchingRuleSet.find_matches_for(
        user_4,
        [aa.practitioner_id],
    ) == [aa]
    assert (
        MatchingRuleSet.find_matches_for(
            user_5,
            [aa.practitioner_id],
        )
        == []
    )


def test_find_matches_for_country_any_org_and_track_and_no_risk_factors(
    factories, session, risk_flags
):
    user = factories.DefaultUserFactory.create()
    factories.MemberProfileFactory.create(user=user)
    factories.MemberTrackFactory.create(name=TrackName.PREGNANCY, user=user)
    module = factories.WeeklyModuleFactory.create(name=TrackName.PREGNANCY)
    other_module = factories.WeeklyModuleFactory.create(name=TrackName.EGG_FREEZING)

    practitioner = factories.PractitionerUserFactory.create()

    aa = factories.AssignableAdvocateFactory.create_with_practitioner(
        practitioner=practitioner
    )

    practitioner2 = factories.PractitionerUserFactory.create()
    factories.AssignableAdvocateFactory.create_with_practitioner(
        practitioner=practitioner2
    )

    mrs = MatchingRuleSet(assignable_advocate=aa)
    country_mr = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.COUNTRY.value,
        matching_rule_set=mrs,
    )
    country_mr.identifiers.append("US")
    country_mr.identifiers.append("IN")

    org_mr = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.ORGANIZATION.value,
        all=True,
        matching_rule_set=mrs,
    )

    track_mr = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.MODULE.value,
        matching_rule_set=mrs,
    )
    track_mr.identifiers.append(str(module.id))
    track_mr.identifiers.append(str(other_module.id))

    user_flag_mr = MatchingRule(
        type=MatchingRuleType.EXCLUDE.value,
        all=True,
        entity=MatchingRuleEntityType.USER_FLAG.value,
        matching_rule_set=mrs,
    )

    session.add_all([country_mr, org_mr, track_mr, user_flag_mr])
    session.commit()

    user.profile.country_code = "IN"
    MemberRiskService(user.id).set_risk("High")
    assert (
        MatchingRuleSet.find_matches_for(
            user,
            [aa.practitioner_id],
        )
        == []
    )

    user.profile.country_code = "US"
    assert (
        MatchingRuleSet.find_matches_for(
            user,
            [aa.practitioner_id],
        )
        == []
    )

    user.profile.country_code = "US"
    MemberRiskService(user.id).clear_risk("High")
    assert MatchingRuleSet.find_matches_for(
        user,
        [aa.practitioner_id],
    ) == [aa]


def test_find_matches_for_country_any_org_excluding_org_and_track_and_no_risk_factors(
    factories, session, risk_flags
):
    user_1 = factories.DefaultUserFactory.create()
    factories.MemberProfileFactory.create(user=user_1, country_code="US")
    factories.MemberTrackFactory.create(
        name=TrackName.PREGNANCY,
        user=user_1,
    )
    excluded_org_module = factories.WeeklyModuleFactory.create(name=TrackName.PREGNANCY)

    user_2 = factories.DefaultUserFactory.create()
    factories.MemberProfileFactory.create(user=user_2, country_code="US")
    factories.MemberTrackFactory.create(
        name=TrackName.EGG_FREEZING,
        user=user_2,
    )
    other_org_module = factories.WeeklyModuleFactory.create(name=TrackName.EGG_FREEZING)

    practitioner = factories.PractitionerUserFactory.create()

    aa = factories.AssignableAdvocateFactory.create_with_practitioner(
        practitioner=practitioner
    )

    practitioner2 = factories.PractitionerUserFactory.create()
    factories.AssignableAdvocateFactory.create_with_practitioner(
        practitioner=practitioner2
    )

    mrs = MatchingRuleSet(assignable_advocate=aa)
    country_mr = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.COUNTRY.value,
        matching_rule_set=mrs,
    )
    country_mr.identifiers.append("US")

    org_mr = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.ORGANIZATION.value,
        all=True,
        matching_rule_set=mrs,
    )

    org_exclude_mr = MatchingRule(
        type=MatchingRuleType.EXCLUDE.value,
        entity=MatchingRuleEntityType.ORGANIZATION.value,
        matching_rule_set=mrs,
    )
    org_exclude_mr.identifiers.append(str(user_1.organization.id))

    track_mr = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.MODULE.value,
        matching_rule_set=mrs,
    )
    track_mr.identifiers.append(str(excluded_org_module.id))
    track_mr.identifiers.append(str(other_org_module.id))

    user_flag_mr = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.USER_FLAG.value,
        matching_rule_set=mrs,
    )
    # user_flag_mr No ids added here to indicate a noop user flag rule.

    session.add_all([country_mr, org_mr, org_exclude_mr, track_mr, user_flag_mr])
    session.commit()

    assert (
        MatchingRuleSet.find_matches_for(
            user_1,
            [aa.practitioner_id],
        )
        == []
    )
    assert MatchingRuleSet.find_matches_for(
        user_2,
        [aa.practitioner_id],
    ) == [aa]


def test_find_matches_for_multiple_sets_any_country_any_org_and_track_and_no_risk_factors(
    factories, session, risk_flags
):
    user_1 = factories.DefaultUserFactory.create()

    user_1 = factories.DefaultUserFactory.create()
    factories.MemberProfileFactory.create(user=user_1, country_code="US")
    factories.MemberTrackFactory.create(name=TrackName.ADOPTION, user=user_1)

    user_2 = factories.DefaultUserFactory.create()
    factories.MemberProfileFactory.create(user=user_2, country_code="US")
    factories.MemberTrackFactory.create(name=TrackName.EGG_FREEZING, user=user_2)

    user_3 = factories.DefaultUserFactory.create()
    factories.MemberProfileFactory.create(user=user_3, country_code="CL")
    factories.MemberTrackFactory.create(name=TrackName.ADOPTION, user=user_3)

    user_4 = factories.DefaultUserFactory.create()
    factories.MemberProfileFactory.create(user=user_4, country_code="US")
    factories.MemberTrackFactory.create(name=TrackName.ADOPTION, user=user_4)

    user_5 = factories.DefaultUserFactory.create()
    factories.MemberProfileFactory.create(user=user_5, country_code="CN")
    factories.MemberTrackFactory.create(
        name=TrackName.EGG_FREEZING,
        user=user_5,
    )

    adoption_module = factories.WeeklyModuleFactory.create(name=TrackName.ADOPTION)
    factories.WeeklyModuleFactory.create(name=TrackName.EGG_FREEZING)

    practitioner = factories.PractitionerUserFactory.create()

    aa = factories.AssignableAdvocateFactory.create_with_practitioner(
        practitioner=practitioner
    )

    practitioner2 = factories.PractitionerUserFactory.create()
    factories.AssignableAdvocateFactory.create_with_practitioner(
        practitioner=practitioner2
    )

    mrs = MatchingRuleSet(assignable_advocate=aa)
    country_mr = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.COUNTRY.value,
        matching_rule_set=mrs,
    )
    country_mr.identifiers.append("US")
    country_mr.identifiers.append("CN")

    org_mr = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.ORGANIZATION.value,
        all=True,
        matching_rule_set=mrs,
    )

    track_mr = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.MODULE.value,
        matching_rule_set=mrs,
    )
    track_mr.identifiers.append(str(adoption_module.id))

    user_flag_mr = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.USER_FLAG.value,
        matching_rule_set=mrs,
    )
    # user_flag_mr No ids added here to indicate a noop user flag rule.

    mrs2 = MatchingRuleSet(assignable_advocate=aa)
    country_mr2 = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.COUNTRY.value,
        all=True,
        matching_rule_set=mrs2,
    )

    org_mr2 = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.ORGANIZATION.value,
        all=True,
        matching_rule_set=mrs2,
    )

    track_mr2 = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.MODULE.value,
        matching_rule_set=mrs2,
    )
    track_mr2.identifiers.append(str(adoption_module.id))

    user_flag_mr2 = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.USER_FLAG.value,
        matching_rule_set=mrs2,
    )

    session.add_all(
        [
            country_mr,
            org_mr,
            track_mr,
            user_flag_mr,
            country_mr2,
            org_mr2,
            track_mr2,
            user_flag_mr2,
        ]
    )
    session.commit()

    assert MatchingRuleSet.find_matches_for(
        user_1,
        [aa.practitioner_id],
    ) == [aa]
    assert (
        MatchingRuleSet.find_matches_for(
            user_2,
            [aa.practitioner_id],
        )
        == []
    )
    assert MatchingRuleSet.find_matches_for(
        user_3,
        [aa.practitioner_id],
    ) == [aa]
    assert MatchingRuleSet.find_matches_for(
        user_4,
        [aa.practitioner_id],
    ) == [aa]
    assert (
        MatchingRuleSet.find_matches_for(
            user_5,
            [aa.practitioner_id],
        )
        == []
    )


def test_find_matches_for_multiple_sets_country_any_org_and_track_and_risk_factors(
    factories, session, risk_flags
):
    user_1 = factories.DefaultUserFactory.create()

    user_1 = factories.DefaultUserFactory.create()
    MemberRiskService(user_1.id).set_risk("High")
    factories.MemberProfileFactory.create(user=user_1, country_code="US")

    track_1 = factories.MemberTrackFactory.create(name=TrackName.PREGNANCY, user=user_1)
    user_1.active_tracks.append(track_1)

    user_2 = factories.DefaultUserFactory.create()
    MemberRiskService(user_2.id).set_risk("High")
    factories.MemberProfileFactory.create(user=user_2, country_code="CN")
    track_2 = factories.MemberTrackFactory.create(name=TrackName.PREGNANCY, user=user_2)
    user_2.active_tracks.append(track_2)

    user_3 = factories.DefaultUserFactory.create()
    factories.MemberProfileFactory.create(user=user_3, country_code="CL")
    track_3 = factories.MemberTrackFactory.create(name=TrackName.PREGNANCY, user=user_3)
    user_3.active_tracks.append(track_3)

    user_4 = factories.DefaultUserFactory.create()
    factories.MemberProfileFactory.create(user=user_4, country_code="US")
    track_4 = factories.MemberTrackFactory.create(
        name=TrackName.EGG_FREEZING, user=user_4
    )
    user_4.active_tracks.append(track_4)

    user_5 = factories.DefaultUserFactory.create()
    factories.MemberProfileFactory.create(user=user_5, country_code="US")
    track_5 = factories.MemberTrackFactory.create(name=TrackName.PREGNANCY, user=user_5)
    user_5.active_tracks.append(track_5)

    user_6 = factories.DefaultUserFactory.create()
    factories.MemberProfileFactory.create(user=user_6, country_code="US")
    track_6 = factories.MemberTrackFactory.create(name=TrackName.PREGNANCY, user=user_6)
    user_6.active_tracks.append(track_6)

    user_7 = factories.DefaultUserFactory.create()
    factories.MemberProfileFactory.create(user=user_7, country_code="CN")
    track_7 = factories.MemberTrackFactory.create(name=TrackName.PREGNANCY, user=user_7)
    user_7.active_tracks.append(track_7)

    pregnancy_module = factories.WeeklyModuleFactory.create(name=TrackName.PREGNANCY)
    other_module = factories.WeeklyModuleFactory.create(name=TrackName.EGG_FREEZING)

    practitioner = factories.PractitionerUserFactory.create()

    aa = factories.AssignableAdvocateFactory.create_with_practitioner(
        practitioner=practitioner
    )

    practitioner2 = factories.PractitionerUserFactory.create()
    factories.AssignableAdvocateFactory.create_with_practitioner(
        practitioner=practitioner2
    )

    mrs = MatchingRuleSet(assignable_advocate=aa)
    country_mr = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.COUNTRY.value,
        matching_rule_set=mrs,
    )
    country_mr.identifiers.append("US")
    country_mr.identifiers.append("CN")

    org_mr = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.ORGANIZATION.value,
        all=True,
        matching_rule_set=mrs,
    )

    track_mr = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.MODULE.value,
        matching_rule_set=mrs,
    )
    track_mr.identifiers.append(str(pregnancy_module.id))
    track_mr.identifiers.append(str(other_module.id))

    user_flag_mr = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.USER_FLAG.value,
        matching_rule_set=mrs,
    )
    user_flag_mr.identifiers.append(risk_flags["High"].id)

    mrs2 = MatchingRuleSet(assignable_advocate=aa)
    country_mr2 = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.COUNTRY.value,
        matching_rule_set=mrs2,
    )
    country_mr2.identifiers.append("US")

    org_mr2 = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.ORGANIZATION.value,
        all=True,
        matching_rule_set=mrs2,
    )

    track_mr2 = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.MODULE.value,
        matching_rule_set=mrs2,
    )
    track_mr2.identifiers.append(str(pregnancy_module.id))

    user_flag_mr2 = MatchingRule(
        type=MatchingRuleType.EXCLUDE.value,
        all=True,
        entity=MatchingRuleEntityType.USER_FLAG.value,
        matching_rule_set=mrs2,
    )

    session.add_all(
        [
            country_mr,
            org_mr,
            track_mr,
            user_flag_mr,
            country_mr2,
            org_mr2,
            track_mr2,
            user_flag_mr2,
        ]
    )
    session.commit()

    assert MatchingRuleSet.find_matches_for(
        user_1,
        [aa.practitioner_id],
    ) == [aa]
    assert MatchingRuleSet.find_matches_for(
        user_2,
        [aa.practitioner_id],
    ) == [aa]
    assert (
        MatchingRuleSet.find_matches_for(
            user_3,
            [aa.practitioner_id],
        )
        == []
    )
    assert MatchingRuleSet.find_matches_for(
        user_4,
        [aa.practitioner_id],
    ) == [aa]
    assert MatchingRuleSet.find_matches_for(
        user_5,
        [aa.practitioner_id],
    ) == [aa]
    assert MatchingRuleSet.find_matches_for(
        user_6,
        [aa.practitioner_id],
    ) == [aa]
    assert (
        MatchingRuleSet.find_matches_for(
            user_7,
            [aa.practitioner_id],
        )
        == []
    )


def test_find_matches_for_multiple_sets_country_any_org_and_track_and_new_risk_factors(
    factories, session, risk_flags
):
    user_1 = factories.DefaultUserFactory.create()
    factories.MemberProfileFactory.create(user=user_1, country_code="US")

    track_1 = factories.MemberTrackFactory.create(name=TrackName.PREGNANCY, user=user_1)
    user_1.active_tracks.append(track_1)

    user_2 = factories.DefaultUserFactory.create()
    MemberRiskService(user_2.id).set_risk("High")
    factories.MemberProfileFactory.create(user=user_2, country_code="CN")
    track_2 = factories.MemberTrackFactory.create(name=TrackName.PREGNANCY, user=user_2)
    user_2.active_tracks.append(track_2)

    user_3 = factories.DefaultUserFactory.create()
    factories.MemberProfileFactory.create(user=user_3, country_code="CL")
    track_3 = factories.MemberTrackFactory.create(
        name=TrackName.PREGNANCY, user=user_3, client_track=track_1.client_track
    )
    user_3.active_tracks.append(track_3)

    pregnancy_module = factories.WeeklyModuleFactory.create(name=TrackName.PREGNANCY)
    other_module = factories.WeeklyModuleFactory.create(name=TrackName.EGG_FREEZING)

    session.add_all(
        [
            track_2.client_track.organization,
        ]
    )
    session.commit()

    practitioner = factories.PractitionerUserFactory.create()

    aa = factories.AssignableAdvocateFactory.create_with_practitioner(
        practitioner=practitioner
    )

    practitioner2 = factories.PractitionerUserFactory.create()
    factories.AssignableAdvocateFactory.create_with_practitioner(
        practitioner=practitioner2
    )

    mrs = MatchingRuleSet(assignable_advocate=aa)
    country_mr = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.COUNTRY.value,
        matching_rule_set=mrs,
    )
    country_mr.identifiers.append("US")
    country_mr.identifiers.append("CN")

    org_mr = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.ORGANIZATION.value,
        all=True,
        matching_rule_set=mrs,
    )

    track_mr = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.MODULE.value,
        matching_rule_set=mrs,
    )
    track_mr.identifiers.append(str(pregnancy_module.id))
    track_mr.identifiers.append(str(other_module.id))

    user_flag_mr = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.USER_FLAG.value,
        matching_rule_set=mrs,
    )
    user_flag_mr.identifiers.append(risk_flags["High"].id)

    mrs2 = MatchingRuleSet(assignable_advocate=aa)
    country_mr2 = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.COUNTRY.value,
        matching_rule_set=mrs2,
    )
    country_mr2.identifiers.append("US")

    org_mr2 = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.ORGANIZATION.value,
        all=True,
        matching_rule_set=mrs2,
    )

    track_mr2 = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.MODULE.value,
        matching_rule_set=mrs2,
    )
    track_mr2.identifiers.append(str(pregnancy_module.id))

    user_flag_mr2 = MatchingRule(
        type=MatchingRuleType.EXCLUDE.value,
        all=True,
        entity=MatchingRuleEntityType.USER_FLAG.value,
        matching_rule_set=mrs2,
    )

    session.add_all(
        [
            country_mr,
            org_mr,
            track_mr,
            user_flag_mr,
            country_mr2,
            org_mr2,
            track_mr2,
            user_flag_mr2,
        ]
    )
    session.commit()

    assert MatchingRuleSet.find_matches_for(
        user_1, [aa.practitioner_id], [risk_flags["High"]]
    ) == [aa]
    assert MatchingRuleSet.find_matches_for(
        user_2,
        [aa.practitioner_id],
        [risk_flags["High"], risk_flags["High2"]],
    ) == [aa]
    assert (
        MatchingRuleSet.find_matches_for(
            user_3,
            [aa.practitioner_id],
        )
        == []
    )


def test_find_matches_for_any_country_any_org_and_track_and_any_and_none_risk_factors(
    factories, session, risk_flags
):
    user_1 = factories.DefaultUserFactory.create()
    member_risks = MemberRiskService(user_1.id)
    member_risks.set_risk("High")
    factories.MemberProfileFactory.create(user=user_1, country_code="IN")

    track_1 = factories.MemberTrackFactory.create(name=TrackName.PREGNANCY, user=user_1)
    user_1.active_tracks.append(track_1)

    user_2 = factories.DefaultUserFactory.create()
    member_risks = MemberRiskService(user_2.id)
    member_risks.set_risk("High")
    factories.MemberProfileFactory.create(user=user_2, country_code="US")
    track_2 = factories.MemberTrackFactory.create(
        name=TrackName.PREGNANCY, user=user_2, client_track=track_1.client_track
    )
    user_2.active_tracks.append(track_2)

    user_3 = factories.DefaultUserFactory.create()
    member_risks = MemberRiskService(user_3.id)
    member_risks.set_risk("High")
    factories.MemberProfileFactory.create(user=user_3, country_code="US")
    track_3 = factories.MemberTrackFactory.create(
        name=TrackName.EGG_FREEZING, user=user_3, client_track=track_1.client_track
    )
    user_3.active_tracks.append(track_3)

    module = factories.WeeklyModuleFactory.create(name=TrackName.PREGNANCY)
    factories.WeeklyModuleFactory.create(name=TrackName.EGG_FREEZING)

    practitioner = factories.PractitionerUserFactory.create()

    aa = factories.AssignableAdvocateFactory.create_with_practitioner(
        practitioner=practitioner
    )

    practitioner2 = factories.PractitionerUserFactory.create()
    factories.AssignableAdvocateFactory.create_with_practitioner(
        practitioner=practitioner2
    )

    mrs = MatchingRuleSet(assignable_advocate=aa)
    country_mr = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.COUNTRY.value,
        all=True,
        matching_rule_set=mrs,
    )

    org_mr = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.ORGANIZATION.value,
        all=True,
        matching_rule_set=mrs,
    )

    track_mr = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.MODULE.value,
        matching_rule_set=mrs,
    )
    track_mr.identifiers.append(str(module.id))

    user_flag_any_mr = MatchingRule(
        type=MatchingRuleType.INCLUDE.value,
        entity=MatchingRuleEntityType.USER_FLAG.value,
        all=True,
        matching_rule_set=mrs,
    )

    user_flag_none_mr = MatchingRule(
        type=MatchingRuleType.EXCLUDE.value,
        entity=MatchingRuleEntityType.USER_FLAG.value,
        all=True,
        matching_rule_set=mrs,
    )

    session.add_all([country_mr, org_mr, track_mr, user_flag_any_mr, user_flag_none_mr])
    session.commit()

    assert MatchingRuleSet.find_matches_for(
        user_1,
        [aa.practitioner_id],
    ) == [aa]

    user_1.email = "abc.xyz2@mavenclinic.com"
    assert MatchingRuleSet.find_matches_for(
        user_1,
        [aa.practitioner_id],
    ) == [aa]

    assert MatchingRuleSet.find_matches_for(
        user_2,
        [aa.practitioner_id],
    ) == [aa]
    assert (
        MatchingRuleSet.find_matches_for(
            user_3,
            [aa.practitioner_id],
        )
        == []
    )


class TestFindMatchesForMultiTrack:
    def test_find_matches_for_multitrack__multiple_tracks(
        self,
        factories,
        complete_matching_rule_set,
        module_pregnancy,
        module_parenting,
        risk_flags,
    ):
        # Given a user with two tracks and a CA available on each track
        user_1 = factories.DefaultUserFactory.create()

        user_1 = factories.DefaultUserFactory.create()
        member_risks = MemberRiskService(user_1.id)
        member_risks.set_risk("High")
        factories.MemberProfileFactory.create(user=user_1, country_code="IN")

        track_11 = factories.MemberTrackFactory.create(
            name=TrackName.PARENTING_AND_PEDIATRICS,
            user=user_1,
        )
        track_12 = factories.MemberTrackFactory.create(
            name=TrackName.PREGNANCY, user=user_1
        )
        user_1.active_tracks.append(track_11)
        user_1.active_tracks.append(track_12)

        practitioner = factories.PractitionerUserFactory.create()
        aa = factories.AssignableAdvocateFactory.create_with_practitioner(
            practitioner=practitioner
        )
        complete_matching_rule_set.get(aa, module_pregnancy)

        practitioner2 = factories.PractitionerUserFactory.create()
        aa2 = factories.AssignableAdvocateFactory.create_with_practitioner(
            practitioner=practitioner2
        )
        complete_matching_rule_set.get(aa2, module_parenting)

        # When
        match_found = MatchingRuleSet.find_matches_for(
            user_1,
            [aa2.practitioner_id, aa.practitioner_id],
        )
        # Then they are assigned the practitioner with the higher-ranking track (pregnancy)
        assert match_found == [aa]
