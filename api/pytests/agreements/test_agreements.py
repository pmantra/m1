from unittest import mock

from models.profiles import Agreement, AgreementAcceptance, AgreementNames


def test_invalid_body(api_helpers, client, default_user, factories):
    # When
    agreement = factories.AgreementFactory.create(optional=False)

    # Then
    res = client.post(
        "/api/v1/_/agreements",
        headers=api_helpers.standard_headers(default_user),
        json={
            "agreements": [
                {
                    "name": agreement.name.value,
                    "version": agreement.version,
                    "unknown_key": "foo",
                }
            ]
        },
    )

    # Test that
    assert res.status_code == 400
    assert AgreementAcceptance.query.count() == 0

    res_body = api_helpers.load_json(res)
    assert res_body["data"] is None

    errors = res_body["errors"]
    assert len(errors) == 1
    error = errors[0]
    assert error["detail"] == "Unknown field."


def test_no_agreements_in_request(api_helpers, client, default_user):
    # Then
    res = client.post(
        "/api/v1/_/agreements",
        headers=api_helpers.standard_headers(default_user),
        json={"agreements": []},
    )

    # Test that
    assert res.status_code == 400
    assert AgreementAcceptance.query.count() == 0

    res_body = api_helpers.load_json(res)
    assert res_body["data"] is None

    errors = res_body["errors"]
    assert len(errors) == 1
    error = errors[0]
    assert error["detail"] == "Agreements field cannot be empty."


def test_unknown_agreement_version(api_helpers, client, default_user, factories):
    # When
    agreement = factories.AgreementFactory.create(version=1)

    # Then
    request_version = agreement.version + 1
    res = client.post(
        "/api/v1/_/agreements",
        headers=api_helpers.standard_headers(default_user),
        json={
            "agreements": [
                {
                    "name": agreement.name.value,
                    "version": request_version,
                }
            ]
        },
    )

    # Test that
    assert res.status_code == 404
    assert AgreementAcceptance.query.count() == 0

    res_body = api_helpers.load_json(res)
    assert res_body["data"] is None

    errors = res_body["errors"]
    assert len(errors) == 1
    error = errors[0]
    assert (
        error["detail"]
        == f"Could not find version {request_version} of {agreement.name.value}"
    )


def test_not_accepting_required_agreement(api_helpers, client, default_user, factories):
    # When
    agreement = factories.AgreementFactory.create(optional=False)

    # Then
    res = client.post(
        "/api/v1/_/agreements",
        headers=api_helpers.standard_headers(default_user),
        json={
            "agreements": [
                {
                    "name": agreement.name.value,
                    "version": agreement.version,
                    "accepted": False,
                }
            ]
        },
    )

    # Test that
    assert res.status_code == 400
    assert AgreementAcceptance.query.count() == 0

    res_body = api_helpers.load_json(res)
    assert res_body["data"] is None

    errors = res_body["errors"]
    assert len(errors) == 1
    error = errors[0]
    assert (
        error["detail"]
        == f"{agreement.display_name} is not optional and must be agreed to"
    )


def test_success_optional_agreement(api_helpers, client, default_user, factories):
    # When
    agreement = factories.AgreementFactory.create(optional=True)

    # Then
    res = client.post(
        "/api/v1/_/agreements",
        headers=api_helpers.standard_headers(default_user),
        json={
            "agreements": [
                {
                    "name": agreement.name.value,
                    "version": agreement.version,
                    "accepted": False,
                }
            ]
        },
    )

    # Test that
    assert res.status_code == 200
    assert AgreementAcceptance.query.count() == 1

    agreement_acceptance = AgreementAcceptance.query.first()
    assert agreement_acceptance.user == default_user
    assert agreement_acceptance.agreement == agreement
    assert agreement_acceptance.accepted is False


def test_success_required_agreement(api_helpers, client, default_user, factories):
    # When
    agreement = factories.AgreementFactory.create(optional=False)

    # Then
    res = client.post(
        "/api/v1/_/agreements",
        headers=api_helpers.standard_headers(default_user),
        json={
            "agreements": [
                {
                    "name": agreement.name.value,
                    "version": agreement.version,
                    "accepted": True,
                }
            ]
        },
    )

    # Test that
    assert res.status_code == 200
    assert AgreementAcceptance.query.count() == 1

    agreement_acceptance = AgreementAcceptance.query.first()
    assert agreement_acceptance.user == default_user
    assert agreement_acceptance.agreement == agreement
    assert agreement_acceptance.accepted is True


def test_success_required_agreement_implied_acceptance(
    api_helpers, client, default_user, factories
):
    # When
    agreement = factories.AgreementFactory.create(optional=False)

    # Then
    res = client.post(
        "/api/v1/_/agreements",
        headers=api_helpers.standard_headers(default_user),
        json={
            "agreements": [
                {
                    "name": agreement.name.value,
                    "version": agreement.version,
                }
            ]
        },
    )

    # Test that
    assert res.status_code == 200
    assert AgreementAcceptance.query.count() == 1

    agreement_acceptance = AgreementAcceptance.query.first()
    assert agreement_acceptance.user == default_user
    assert agreement_acceptance.agreement == agreement
    assert agreement_acceptance.accepted is True


def test_success_mixed_agreements(api_helpers, client, default_user, factories):
    # When
    required_agreement = factories.AgreementFactory.create(optional=False)
    optional_agreement = factories.AgreementFactory.create(
        optional=True, name=AgreementNames.MICROSOFT
    )

    factories.AgreementAcceptanceFactory.create(
        agreement=required_agreement, user=default_user
    )
    factories.AgreementAcceptanceFactory.create(
        agreement=optional_agreement, user=default_user
    )

    # Then
    res = client.post(
        "/api/v1/_/agreements",
        headers=api_helpers.standard_headers(default_user),
        json={
            "agreements": [
                {
                    "name": required_agreement.name.value,
                    "version": required_agreement.version,
                },
                {
                    "name": optional_agreement.name.value,
                    "version": optional_agreement.version,
                    "accepted": False,
                },
            ]
        },
    )

    # Test that
    assert res.status_code == 200
    assert AgreementAcceptance.query.count() == 2

    agreement_acceptances = AgreementAcceptance.query.all()
    required_acceptance = next(
        a
        for a in agreement_acceptances
        if a.agreement_id == required_agreement.id and a.accepted
    )
    optional_acceptance = next(
        a
        for a in agreement_acceptances
        if a.agreement_id == optional_agreement.id and not a.accepted
    )
    assert required_acceptance is not None
    assert optional_acceptance is not None


def test_failure_mixed_agreements(api_helpers, client, default_user, factories):
    # When
    required_agreement = factories.AgreementFactory.create(optional=False)
    optional_agreement = factories.AgreementFactory.create(
        optional=True, name=AgreementNames.MICROSOFT
    )

    # Then
    res = client.post(
        "/api/v1/_/agreements",
        headers=api_helpers.standard_headers(default_user),
        json={
            "agreements": [
                {
                    "name": required_agreement.name.value,
                    "version": required_agreement.version,
                    "accepted": False,
                },
                {
                    "name": optional_agreement.name.value,
                    "version": optional_agreement.version,
                    "accepted": False,
                },
            ]
        },
    )

    # Test that
    assert res.status_code == 400
    assert AgreementAcceptance.query.count() == 0


def test_language_match(
    api_helpers,
    client,
    default_user,
    factories,
):
    # When
    deu = factories.LanguageFactory.create(
        name="German",
        iso_639_3="deu",
    )
    eng = factories.LanguageFactory.create(
        name="English",
        iso_639_3="eng",
    )

    deu_pp = factories.AgreementFactory.create(
        name=AgreementNames.PRIVACY_POLICY,
        version=1,
        language_id=deu.id,
    )

    # English translation with a higher version
    factories.AgreementFactory.create(
        name=AgreementNames.PRIVACY_POLICY,
        version=2,
        language_id=eng.id,
    )

    # Then
    res = client.get(
        f"/api/v1/_/agreements/{AgreementNames.PRIVACY_POLICY.value}",
        headers=api_helpers.standard_headers(default_user),
        query_string={"lang": "deu"},
    )
    json = api_helpers.load_json(res)

    # Test that
    assert res.status_code == 200
    assert json["data"]["language"] == deu.iso_639_3
    assert json["data"]["version"] == deu_pp.version
    assert json["data"]["name"] == deu_pp.name.value


def test_language_does_not_exist(
    api_helpers,
    client,
    default_user,
    factories,
):
    # When
    agreement = factories.AgreementFactory.create(
        name=AgreementNames.PRIVACY_POLICY,
        version=1,
    )

    # Then
    res = client.get(
        f"/api/v1/_/agreements/{agreement.name.value}",
        headers=api_helpers.standard_headers(default_user),
        query_string={"lang": "FOO"},
    )
    json = api_helpers.load_json(res)

    # Test that
    assert res.status_code == 400
    assert json.get("data") is None

    errors = json["errors"]
    assert len(errors) == 1
    error = errors[0]
    assert error["detail"] == "The given language is not supported"


def test_no_language_specified(
    api_helpers,
    client,
    default_user,
    factories,
):
    # When
    eng = factories.LanguageFactory.create(
        name="English",
        iso_639_3="eng",
    )
    deu = factories.LanguageFactory.create(
        name="Deutsch",
        iso_639_3="deu",
    )

    pp_eng = factories.AgreementFactory.create(
        name=AgreementNames.PRIVACY_POLICY,
        version=1,
    )

    factories.AgreementFactory.create(
        name=AgreementNames.PRIVACY_POLICY,
        version=2,
        language_id=deu.id,
    )

    # Then
    res = client.get(
        f"/api/v1/_/agreements/{AgreementNames.PRIVACY_POLICY.value}",
        headers=api_helpers.standard_headers(default_user),
    )
    json = api_helpers.load_json(res)

    # Test that
    assert res.status_code == 200
    assert json["data"]["language"] == eng.iso_639_3
    assert json["data"]["version"] == pp_eng.version
    assert json["data"]["name"] == pp_eng.name.value


def test_language_and_version(
    api_helpers,
    client,
    default_user,
    privacy_english,
    privacy_spanish,
):
    # Then
    res = client.get(
        f"/api/v1/_/agreements/{AgreementNames.PRIVACY_POLICY.value}",
        headers=api_helpers.standard_headers(default_user),
        query_string={"lang": privacy_spanish.language.iso_639_3, "version": "1"},
    )
    json = api_helpers.load_json(res)

    # Test that
    assert res.status_code == 200
    assert json["data"]["language"] == privacy_spanish.language.iso_639_3
    assert json["data"]["version"] == privacy_spanish.version
    assert json["data"]["name"] == privacy_spanish.name.value


def test_no_language_on_agreement_and_version(
    api_helpers,
    client,
    default_user,
    english,
    privacy_no_language,
    privacy_spanish,
):
    # Then
    res = client.get(
        f"/api/v1/_/agreements/{AgreementNames.PRIVACY_POLICY.value}",
        headers=api_helpers.standard_headers(default_user),
        query_string={"lang": "eng", "version": "1"},
    )
    json = api_helpers.load_json(res)

    # Test that
    assert res.status_code == 200
    assert json["data"]["language"] == english.iso_639_3
    assert json["data"]["version"] == privacy_no_language.version
    assert json["data"]["name"] == privacy_no_language.name.value


def test_no_language_in_request_and_version(
    api_helpers,
    client,
    default_user,
    privacy_english,
    privacy_spanish,
):
    # Then
    res = client.get(
        f"/api/v1/_/agreements/{AgreementNames.PRIVACY_POLICY.value}",
        headers=api_helpers.standard_headers(default_user),
        query_string={"version": "1"},
    )
    json = api_helpers.load_json(res)

    # Test that
    assert res.status_code == 200
    assert json["data"]["language"] == privacy_english.language.iso_639_3
    assert json["data"]["version"] == privacy_english.version
    assert json["data"]["name"] == privacy_english.name.value


def test_no_language_and_version(
    api_helpers,
    client,
    default_user,
    english,
    privacy_no_language,
    privacy_spanish,
):
    # Then
    res = client.get(
        f"/api/v1/_/agreements/{AgreementNames.PRIVACY_POLICY.value}",
        headers=api_helpers.standard_headers(default_user),
        query_string={"version": "1"},
    )
    json = api_helpers.load_json(res)

    # Test that
    assert res.status_code == 200
    assert json["data"]["language"] == english.iso_639_3
    assert json["data"]["version"] == privacy_no_language.version
    assert json["data"]["name"] == privacy_no_language.name.value


def test_no_language_on_agreement(
    api_helpers,
    client,
    default_user,
    english,
    privacy_no_language,
):
    # Then
    res = client.get(
        f"/api/v1/_/agreements/{privacy_no_language.name.value}",
        headers=api_helpers.standard_headers(default_user),
    )
    json = api_helpers.load_json(res)

    # Test that
    assert res.status_code == 200
    assert json["data"]["language"] == english.iso_639_3
    assert json["data"]["version"] == privacy_no_language.version
    assert json["data"]["name"] == privacy_no_language.name.value


def test_get_pending_agreements(
    api_helpers,
    client,
    enterprise_user,
    factories,
):
    factories.LanguageFactory.create(name="English")
    accepted_agreement = factories.AgreementFactory.create(
        name=AgreementNames.PRIVACY_POLICY
    )
    factories.AgreementAcceptanceFactory.create(
        agreement=accepted_agreement, user=enterprise_user
    )
    factories.AgreementFactory.create(name=AgreementNames.TERMS_OF_USE)
    org_agreement = factories.AgreementFactory.create(name=AgreementNames.MICROSOFT)
    factories.OrganizationAgreementFactory.create(
        organization=enterprise_user.organization, agreement=org_agreement
    )

    # Then
    with mock.patch(
        "eligibility.service.EnterpriseVerificationService.get_eligible_organization_ids_for_user",
        return_value={enterprise_user.organization_v2.id},
    ):
        res = client.get(
            "/api/v1/agreements/pending",
            headers=api_helpers.standard_headers(enterprise_user),
        )
    json = api_helpers.load_json(res)

    # Test that
    assert res.status_code == 200
    assert len(json["organization"]) == 1
    assert json["organization"][0]["name"] == AgreementNames.MICROSOFT.value
    assert len(json["user"]) == 1
    assert json["user"][0]["name"] == AgreementNames.TERMS_OF_USE.value


def test_get_by_version(spanish, privacy_english, privacy_spanish):
    # Then
    agreement = Agreement.get_by_version(
        AgreementNames.PRIVACY_POLICY,
        version=1,
        language=spanish,
    )

    # Test that
    assert agreement == privacy_spanish


def test_get_by_version_no_language_specified(
    privacy_english,
    privacy_spanish,
):
    # Then
    agreement = Agreement.get_by_version(
        AgreementNames.PRIVACY_POLICY,
        version=1,
        language=None,
    )

    # Test that
    assert agreement == privacy_english


def test_get_by_version_no_language_on_agreement(
    privacy_spanish,
    privacy_no_language,
):
    # Then
    agreement = Agreement.get_by_version(
        AgreementNames.PRIVACY_POLICY,
        version=1,
        language=None,
    )

    # Test that
    assert agreement == privacy_no_language


def test_latest_versions(factories):
    # When
    factories.LanguageFactory.create(name="English")
    deu = factories.LanguageFactory.create(name="Deutsch")

    factories.AgreementFactory.create(
        name=AgreementNames.PRIVACY_POLICY,
        version=1,
    )

    pp_deu = factories.AgreementFactory.create(
        name=AgreementNames.PRIVACY_POLICY,
        version=1,
        language_id=deu.id,
    )

    # Then
    latest_versions = Agreement.latest_versions(
        agreement_names={AgreementNames.PRIVACY_POLICY},
        language=deu,
    )

    # Test that
    assert len(latest_versions) == 1
    assert latest_versions[0] == pp_deu


def test_latest_versions_no_language_specified(factories):
    # When
    eng = factories.LanguageFactory.create(name="English")
    deu = factories.LanguageFactory.create(name="Deutsch")

    pp_eng = factories.AgreementFactory.create(
        name=AgreementNames.PRIVACY_POLICY,
        version=1,
        language_id=eng.id,
    )

    factories.AgreementFactory.create(
        name=AgreementNames.PRIVACY_POLICY,
        version=1,
        language_id=deu.id,
    )

    # Then
    latest_versions = Agreement.latest_versions(
        agreement_names={AgreementNames.PRIVACY_POLICY},
    )

    # Test that
    assert len(latest_versions) == 1
    assert latest_versions[0] == pp_eng


def test_latest_versions_no_language_specified_or_on_agreement(
    privacy_no_language,
    privacy_spanish,
):
    # Then
    latest_versions = Agreement.latest_versions(
        agreement_names={AgreementNames.PRIVACY_POLICY},
    )

    # Test that
    assert len(latest_versions) == 1
    assert latest_versions[0] == privacy_no_language


def test_latest_versions_no_language_given(
    privacy_english,
    privacy_spanish,
):
    # Then
    latest_versions = Agreement.latest_versions(
        agreement_names={AgreementNames.PRIVACY_POLICY},
        language=None,
    )

    # Test that
    assert len(latest_versions) == 1
    assert latest_versions[0] == privacy_english


def test_get_pending_version_no_agreement_acceptances(factories, enterprise_user):
    # When
    eng = factories.LanguageFactory.create(name="English")

    factories.AgreementFactory.create(
        name=AgreementNames.PRIVACY_POLICY,
        version=1,
        language=eng,
    )

    pp_v2 = factories.AgreementFactory.create(
        name=AgreementNames.PRIVACY_POLICY,
        version=2,
        language=eng,
    )

    # Then
    pending_agreements = enterprise_user._all_pending_agreements
    pending_pp = [
        a for a in pending_agreements if a.name == AgreementNames.PRIVACY_POLICY
    ]

    # Test that
    assert len(pending_pp) == 1
    assert pending_pp[0] == pp_v2


def test_get_pending_version_no_english_version(factories, enterprise_user):
    # When
    factories.LanguageFactory.create(name="English")
    deu = factories.LanguageFactory.create(name="German")

    factories.AgreementFactory.create(
        name=AgreementNames.PRIVACY_POLICY,
        version=1,
        language=deu,
    )

    factories.AgreementFactory.create(
        name=AgreementNames.PRIVACY_POLICY,
        version=2,
        language=deu,
    )

    # Then
    pending_agreements = enterprise_user._all_pending_agreements
    pending_pp = [
        a for a in pending_agreements if a.name == AgreementNames.PRIVACY_POLICY
    ]

    # Test that
    assert len(pending_pp) == 0


def test_get_pending_version_english_version(factories, enterprise_user):
    # When
    eng = factories.LanguageFactory.create(name="English")
    deu = factories.LanguageFactory.create(name="German")

    factories.AgreementFactory.create(
        name=AgreementNames.PRIVACY_POLICY,
        version=1,
        language=deu,
    )

    pp_v2 = factories.AgreementFactory.create(
        name=AgreementNames.PRIVACY_POLICY,
        version=2,
        language=eng,
    )

    factories.AgreementAcceptanceFactory.create(
        agreement=pp_v2,
        user=enterprise_user,
    )

    # Then
    pending_agreements = enterprise_user._all_pending_agreements
    pending_pp = [
        a for a in pending_agreements if a.name == AgreementNames.PRIVACY_POLICY
    ]

    # Test that
    assert len(pending_pp) == 0


def test_get_pending_version_after_english_version(factories, enterprise_user):
    # When
    eng = factories.LanguageFactory.create(name="English")
    deu = factories.LanguageFactory.create(name="German")

    factories.AgreementFactory.create(
        name=AgreementNames.PRIVACY_POLICY,
        version=1,
        language=eng,
    )

    pp_v2 = factories.AgreementFactory.create(
        name=AgreementNames.PRIVACY_POLICY,
        version=2,
        language=deu,
    )

    factories.AgreementAcceptanceFactory.create(
        agreement=pp_v2,
        user=enterprise_user,
    )

    # Then
    pending_agreements = enterprise_user._all_pending_agreements
    pending_pp = [
        a for a in pending_agreements if a.name == AgreementNames.PRIVACY_POLICY
    ]

    # Test that
    assert len(pending_pp) == 0


def test_get_pending_version_non_english(factories, enterprise_user):
    # When
    eng = factories.LanguageFactory.create(name="English")
    deu = factories.LanguageFactory.create(name="German")

    pp_v1 = factories.AgreementFactory.create(
        name=AgreementNames.PRIVACY_POLICY,
        version=1,
        language=eng,
    )

    pp_v2 = factories.AgreementFactory.create(
        name=AgreementNames.PRIVACY_POLICY,
        version=2,
        language=deu,
    )

    factories.AgreementFactory.create(
        name=AgreementNames.PRIVACY_POLICY,
        version=3,
        language=deu,
    )

    factories.AgreementAcceptanceFactory.create(
        agreement=pp_v2,
        user=enterprise_user,
    )

    # Then
    pending_agreements = enterprise_user._all_pending_agreements
    pending_pp = [
        a for a in pending_agreements if a.name == AgreementNames.PRIVACY_POLICY
    ]

    # Test that
    assert len(pending_pp) == 1
    assert pending_pp[0] == pp_v1


def test_get_pending_organization_agreement(factories, enterprise_user):
    # When
    eng = factories.LanguageFactory.create(name="English")

    org_agreement_v1 = factories.AgreementFactory.create(
        name=AgreementNames.CHEESECAKE_FACTORY,
        version=1,
        language=eng,
    )

    org_agreement_v2 = factories.AgreementFactory.create(
        name=AgreementNames.CHEESECAKE_FACTORY,
        version=2,
        language=eng,
    )

    other_org = factories.OrganizationFactory.create()

    factories.OrganizationAgreementFactory.create(
        organization=enterprise_user.organization, agreement=org_agreement_v1
    )
    factories.OrganizationAgreementFactory.create(
        organization=other_org, agreement=org_agreement_v1
    )

    factories.OrganizationAgreementFactory.create(
        organization=enterprise_user.organization, agreement=org_agreement_v2
    )
    factories.OrganizationAgreementFactory.create(
        organization=other_org, agreement=org_agreement_v2
    )

    factories.AgreementAcceptanceFactory.create(
        agreement=org_agreement_v1,
        user=enterprise_user,
    )

    # Then
    pending_agreements = enterprise_user.get_pending_organization_agreements(
        organization_ids={enterprise_user.organization_v2.id}
    )
    pending_org_agreement = [
        a for a in pending_agreements if a.name == AgreementNames.CHEESECAKE_FACTORY
    ]

    # Test that
    assert len(pending_org_agreement) == 1
    assert pending_org_agreement[0] == org_agreement_v2
