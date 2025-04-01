from unittest import mock

from eligibility.pytests import factories as e9y_factories
from models.profiles import AgreementNames
from models.programs import Module
from models.tracks import TrackName, configured_tracks


def _assert_okay(api_helpers, res, org):
    json = api_helpers.load_json(res)

    assert res.status_code == 200

    assert (
        json["data"]["verified_employee"]["organization_display_name"]
        == org.marketing_name
    )
    module_names = [m["name"] for m in json["data"]["modules"]["eligible"]]

    all_tracks = configured_tracks()
    assert len(module_names) == len(
        [
            t
            for t in all_tracks
            if all_tracks[t].onboarding.label
            and all_tracks[t].onboarding.label != "None"
        ]
    )


def allow_tracks_for_org(factories, org, track_names=None):
    if track_names:
        modules = Module.query.filter(Module.name.in_(track_names)).all()
    else:
        modules = Module.query.all()
    existing = {ct.track for ct in org.client_tracks}
    tracks = track_names or [*TrackName]
    org.client_tracks.extend(
        factories.ClientTrackFactory.create(track=n, length_in_days=365)
        for n in tracks
        if n not in existing
    )
    added = []
    for module in modules:
        if module not in org.allowed_modules:
            org.allowed_modules.append(module)
            added.append(module)
        else:
            continue

    return added


def test_enterprise_member_multitrack_features(
    api_helpers, client, factories, default_user, track_service, verification
):
    """
    When:
        - A member is enrolled in the generic track
        - The member's organization allows all tracks
    Then:
        - The member calls the /features endpoint without passing any query parameters
    Test that:
        - The /features endpoint returns a 200 status code
        - The /features endpoint shows the tracks the member is eligible for
    """
    # "All tracks" includes the parenting and pediatrics track,
    # the presence of which marks this organization/member as "multitrack."
    org = factories.OrganizationFactory.create(allowed_tracks=[*TrackName])
    factories.MemberTrackFactory.create(
        name="generic",
        user=default_user,
        client_track=factories.ClientTrackFactory(organization=org),
    )
    verification = e9y_factories.VerificationFactory.create(
        user_id=default_user.id, organization_id=org.id
    )

    with mock.patch("eligibility.web.verify_member") as mock_verify_member:
        mock_verify_member.return_value = verification
        res = client.get(
            "/api/v1/features",
            headers=api_helpers.standard_headers(default_user),
        )

    json = api_helpers.load_json(res)

    assert res.status_code == 200

    module_names = [m["name"] for m in json["data"]["modules"]["eligible"]]
    assert len(module_names) > 0
    assert len(module_names) == len(
        track_service.get_enrollable_tracks_for_verification(verification=verification)
    )


def test_enterprise_member_no_features(api_helpers, client, factories, default_user):
    """
    When:
        - A member is enrolled in the generic track
        - The member's organization allows all tracks EXCEPT for parenting and pediatrics
    Then:
        - The member calls the /features endpoint
    Test that:
        - The /features endpoint returns a 409 status code
        - The /features endpoint returns an error stating that the member is not eligible for any additional tracks
    """
    allowed_tracks = [
        tn for tn in [*TrackName] if tn != TrackName.PARENTING_AND_PEDIATRICS
    ]
    org = factories.OrganizationFactory.create(allowed_tracks=allowed_tracks)
    factories.MemberTrackFactory.create(
        name="generic",
        user=default_user,
        client_track=factories.ClientTrackFactory(organization=org),
    )
    verification = e9y_factories.VerificationFactory.create(
        user_id=default_user.id, organization_id=org.id
    )

    with mock.patch("eligibility.web.verify_member") as mock_verify_member:
        mock_verify_member.return_value = verification
        res = client.get(
            "/api/v1/features",
            query_string={
                "date_of_birth": "1989-04-01",
            },
            headers=api_helpers.standard_headers(default_user),
        )

    json = api_helpers.load_json(res)

    assert res.status_code == 409
    assert json["errors"][0]["code"] == "NO_AVAILABLE_TRACKS"


def test_module_required_information(api_helpers, client, factories, default_user):
    """
    When:
        - A member exists in e9y with the information provided by the member
        - The member's organization supports all tracks
    Then:
        - The member calls the /features endpoint
    Test that:
        - The /features endpoint returns a 200 status code
        - The /features endpoint returns all tracks the user is eligible in
        - The /features endpoint returns the appropriate required information for specific modules
    """
    org = factories.OrganizationFactory.create(allowed_tracks=[*TrackName])
    emp = factories.OrganizationEmployeeFactory.create(
        date_of_birth="2000-01-01",
        email="employee@company.com",
        organization=org,
    )
    factories.UserOrganizationEmployeeFactory.create(
        user=default_user,
        organization_employee=emp,
    )
    verification = e9y_factories.VerificationFactory.create(
        user_id=default_user.id, organization_id=org.id
    )

    with mock.patch("eligibility.web.verify_member") as mock_verify_member:
        mock_verify_member.return_value = verification
        res = client.get(
            "/api/v1/features",
            query_string={
                "date_of_birth": "2000-01-01",
                "company_email": "employee@company.com",
            },
            headers=api_helpers.standard_headers(default_user),
        )
        _assert_okay(api_helpers, res, org)
    json = api_helpers.load_json(res)

    required_information_by_module = {
        "pregnancy": "DUE_DATE",
        "partner_pregnant": "DUE_DATE",
        "postpartum": "CHILD_BIRTH",
        "partner_newparent": "CHILD_BIRTH",
    }
    all_modules = json["data"]["modules"]["eligible"]
    for module_name, required_info in required_information_by_module.items():
        module = next(m for m in all_modules if m["name"] == module_name)
        assert required_info in module["required_information"]


def test_module_length_in_days(api_helpers, client, factories, default_user):
    """
    When:
        - A member exists in e9y with the information provided by the member
        - The member's organization supports all tracks, including a seprately configured track length
    Then:
        - The member calls the /features endpoint
    Test that:
        - The /features endpoint returns a 200 status code
        - The /features endpoint returns all tracks the user is eligible in
        - The /features endpoint returns the appropriate length_in_days for specific modules
    """
    org = factories.OrganizationFactory.create(allowed_tracks=[*TrackName])
    emp = factories.OrganizationEmployeeFactory.create(
        date_of_birth="2000-01-01",
        email="employee@company.com",
        organization=org,
    )
    factories.UserOrganizationEmployeeFactory.create(
        user=default_user,
        organization_employee=emp,
    )
    verification = e9y_factories.VerificationFactory.create(
        user_id=default_user.id, organization_id=org.id
    )

    with mock.patch("eligibility.web.verify_member") as mock_verify_member:
        mock_verify_member.return_value = verification
        res = client.get(
            "/api/v1/features",
            query_string={
                "date_of_birth": "2000-01-01",
                "company_email": "employee@company.com",
            },
            headers=api_helpers.standard_headers(default_user),
        )
        _assert_okay(api_helpers, res, org)
    json = api_helpers.load_json(res)

    features = json["data"]["modules"]["eligible"]
    pregnancy_feature = next(f for f in features if f["name"] == "pregnancy")

    assert (
        pregnancy_feature["length_in_days"]
        == 365  # matches test setup for client track, not track config of 294
    )


def test_organization_id(api_helpers, client, factories, default_user):
    """
    When:
        - A member exists in e9y with the information provided by the member
        - The member's organization supports all tracks, including a seprately configured track length
    Then:
        - The member calls the /features endpoint
    Test that:
        - The /features endpoint returns a 200 status code
        - The /features endpoint returns all tracks the user is eligible in
        - The /features endpoint returns the appropriate organization_id
    """
    org = factories.OrganizationFactory.create(allowed_tracks=[*TrackName])
    emp = factories.OrganizationEmployeeFactory.create(
        date_of_birth="2000-01-01",
        email="employee@company.com",
        organization=org,
    )
    factories.UserOrganizationEmployeeFactory.create(
        user=default_user,
        organization_employee=emp,
    )
    verification = e9y_factories.VerificationFactory.create(
        user_id=default_user.id, organization_id=org.id
    )

    with mock.patch("eligibility.web.verify_member") as mock_verify_member:
        mock_verify_member.return_value = verification
        res = client.get(
            "/api/v1/features",
            query_string={
                "date_of_birth": "2000-01-01",
                "company_email": "employee@company.com",
            },
            headers=api_helpers.standard_headers(default_user),
        )
        _assert_okay(api_helpers, res, org)
    json = api_helpers.load_json(res)

    features = json["data"]["modules"]["eligible"]
    pregnancy_feature = next(f for f in features if f["name"] == "pregnancy")

    assert (
        pregnancy_feature["organization_id"]
        == org.id  # matches test setup for client track, not track config of 294
    )


def test_pending_organization_agreement(api_helpers, client, factories, default_user):
    """
    When:
        - The member's organization supports all tracks
        - The member has a pending agreement that is tied to their organization
    Then:
        - The member calls the /features endpoint
    Test that:
        - The /features endpoint returns a 200 status code
        - The /features endpoint returns all tracks the user is eligible in
        - The /features endpoint returns a list of agreements that have yet to be agreed to that are specific to this member's organization
    """
    factories.LanguageFactory.create(name="English")
    org = factories.OrganizationFactory.create(allowed_tracks=[*TrackName])
    emp = factories.OrganizationEmployeeFactory.create(
        date_of_birth="2000-01-01",
        email="employee@company.com",
        organization=org,
    )
    factories.UserOrganizationEmployeeFactory.create(
        user=default_user,
        organization_employee=emp,
    )
    verification = e9y_factories.VerificationFactory.create(
        user_id=default_user.id, organization_id=org.id
    )

    agreement = factories.AgreementFactory.create(name=AgreementNames.GINA)
    factories.OrganizationAgreementFactory.create(
        organization=emp.organization, agreement=agreement
    )
    factories.MemberProfileFactory.create(user=default_user)

    with mock.patch("eligibility.web.verify_member") as mock_verify_member:
        mock_verify_member.return_value = verification
        res = client.get(
            "/api/v1/features",
            query_string={
                "date_of_birth": "2000-01-01",
                "company_email": "employee@company.com",
            },
            headers=api_helpers.standard_headers(default_user),
        )

    _assert_okay(api_helpers, res, org)
    json = api_helpers.load_json(res)

    assert (
        json["data"]["verified_employee"]["all_pending_agreements"]["organization"][0][
            "name"
        ]
        == AgreementNames.GINA.value
    )


def test_pending_user_agreement(api_helpers, client, factories, default_user):
    """
    When:
        - The member's organization supports all tracks
        - The member has a pending agreement that is not tied to a specific organization
    Then:
        - The member calls the /features endpoint
    Test that:
        - The /features endpoint returns a 200 status code
        - The /features endpoint returns all tracks the user is eligible in
        - The /features endpoint returns a list of agreements that have yet to be agreed to that are not specific to this member's organization but are specific to this member
    """
    factories.LanguageFactory.create(name="English")
    org = factories.OrganizationFactory.create(allowed_tracks=[*TrackName])
    emp = factories.OrganizationEmployeeFactory.create(
        date_of_birth="2000-01-01",
        email="employee@company.com",
        organization=org,
    )
    factories.UserOrganizationEmployeeFactory.create(
        user=default_user,
        organization_employee=emp,
    )
    verification = e9y_factories.VerificationFactory.create(
        user_id=default_user.id, organization_id=org.id
    )
    factories.AgreementFactory.create(name=AgreementNames.PRIVACY_POLICY)
    factories.MemberProfileFactory.create(user=default_user)

    with mock.patch("eligibility.web.verify_member") as mock_verify_member:
        mock_verify_member.return_value = verification
        res = client.get(
            "/api/v1/features",
            query_string={
                "date_of_birth": "2000-01-01",
                "company_email": "employee@company.com",
            },
            headers=api_helpers.standard_headers(default_user),
        )

    _assert_okay(api_helpers, res, org)
    json = api_helpers.load_json(res)

    assert (
        json["data"]["verified_employee"]["all_pending_agreements"]["user"][0]["name"]
        == AgreementNames.PRIVACY_POLICY.value
    )


def test_pending_organization_and_user_agreement(
    api_helpers, client, factories, default_user
):
    """
    When:
        - The member's organization supports all tracks
        - The member has a pending agreement that is tied to a specific organization
        - The member also has a pending agreement that is not tied to a specific organization
    Then:
        - The member calls the /features endpoint
    Test that:
        - The /features endpoint returns a 200 status code
        - The /features endpoint returns all tracks the user is eligible in
        - The /features endpoint returns a list of agreements that have yet to be agreed to that are specific to this member's organization
        - The /features endpoint returns a list of agreements that have yet to be agreed to that are not specific to this member's organization but are specific to this member
    """
    factories.LanguageFactory.create(name="English")
    org = factories.OrganizationFactory.create(allowed_tracks=[*TrackName])
    emp = factories.OrganizationEmployeeFactory.create(
        date_of_birth="2000-01-01",
        email="employee@company.com",
        organization=org,
    )
    factories.UserOrganizationEmployeeFactory.create(
        user=default_user,
        organization_employee=emp,
    )
    verification = e9y_factories.VerificationFactory.create(
        user_id=default_user.id, organization_id=org.id
    )
    agreement = factories.AgreementFactory.create(name=AgreementNames.GINA)
    factories.OrganizationAgreementFactory.create(
        organization=emp.organization, agreement=agreement
    )
    factories.AgreementFactory.create(name=AgreementNames.PRIVACY_POLICY)
    factories.MemberProfileFactory.create(user=default_user)

    with mock.patch("eligibility.web.verify_member") as mock_verify_member:
        mock_verify_member.return_value = verification
        res = client.get(
            "/api/v1/features",
            query_string={
                "date_of_birth": "2000-01-01",
                "company_email": "employee@company.com",
            },
            headers=api_helpers.standard_headers(default_user),
        )

    _assert_okay(api_helpers, res, org)
    json = api_helpers.load_json(res)

    assert (
        json["data"]["verified_employee"]["all_pending_agreements"]["organization"][0][
            "name"
        ]
        == AgreementNames.GINA.value
    )

    assert (
        json["data"]["verified_employee"]["all_pending_agreements"]["user"][0]["name"]
        == AgreementNames.PRIVACY_POLICY.value
    )


def test_no_pending_agreement(api_helpers, client, factories, default_user):
    """
    When:
        - The member's organization supports all tracks
        - The member has no pending agreements
    Then:
        - The member calls the /features endpoint
    Test that:
        - The /features endpoint returns a 200 status code
        - The /features endpoint returns all tracks the user is eligible in
        - The /features endpoint should not return any agreements
    """
    factories.LanguageFactory.create(name="English")
    org = factories.OrganizationFactory.create(allowed_tracks=[*TrackName])
    emp = factories.OrganizationEmployeeFactory.create(
        date_of_birth="2000-01-01",
        email="employee@company.com",
        organization=org,
    )
    factories.UserOrganizationEmployeeFactory.create(
        user=default_user,
        organization_employee=emp,
    )
    verification = e9y_factories.VerificationFactory.create(
        user_id=default_user.id, organization_id=org.id
    )
    factories.MemberProfileFactory.create(user=default_user)

    with mock.patch("eligibility.web.verify_member") as mock_verify_member:
        mock_verify_member.return_value = verification
        res = client.get(
            "/api/v1/features",
            query_string={
                "date_of_birth": "2000-01-01",
                "company_email": "employee@company.com",
            },
            headers=api_helpers.standard_headers(default_user),
        )

    _assert_okay(api_helpers, res, org)
    json = api_helpers.load_json(res)

    assert (
        len(json["data"]["verified_employee"]["all_pending_agreements"]["organization"])
        == 0
    )

    assert len(json["data"]["verified_employee"]["all_pending_agreements"]["user"]) == 0
