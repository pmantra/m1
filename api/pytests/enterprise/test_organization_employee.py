def test_organization_employee_country__no_json(factories):
    """
    When:
        - An OrganizationEmployee does not have any json data
    Then:
        - The OrganizationEmployee's country attribute is fetched
    Test that:
        - The OrganizationEmployee's country is None
    """
    emp = factories.OrganizationEmployeeFactory.create()

    assert emp.country is None


def test_organization_employee_country__no_address(factories):
    """
    When:
        - An OrganizationEmployee does not have an address in its json data
    Then:
        - The OrganizationEmployee's country attribute is fetched
    Test that:
        - The OrganizationEmployee's country is None
    """
    emp = factories.OrganizationEmployeeFactory.create(json={"wallet_enabled": True})

    assert emp.country is None


def test_organization_employee_country__no_country(factories):
    """
    When:
        - An OrganizationEmployee has an address, but not a country in its json data
    Then:
        - The OrganizationEmployee's country attribute is fetched
    Test that:
        - The OrganizationEmployee's country is None
    """
    emp = factories.OrganizationEmployeeFactory.create(
        json={
            "address": {
                "employee_first_name": "QATest",
                "employee_last_name": "User",
                "address_1": "",
                "address_2": "",
                "city": None,
                "state": "",
                "zip_code": "",
                "country": None,
            }
        }
    )

    assert emp.country is None


def test_organization_employee_country__invalid_country(factories):
    """
    When:
        - An OrganizationEmployee has an address, with a country in its json data,
          but the country is not recognized
    Then:
        - The OrganizationEmployee's country attribute is fetched
    Test that:
        - The OrganizationEmployee's country is None
    """
    emp = factories.OrganizationEmployeeFactory.create(
        json={
            "address": {
                "employee_first_name": "QATest",
                "employee_last_name": "User",
                "address_1": "",
                "address_2": "",
                "city": None,
                "state": "",
                "zip_code": "",
                "country": "ZZ",
            }
        }
    )

    assert emp.country is None


def test_organization_employee_country__valid_country_alpha_2(factories):
    """
    When:
        - An OrganizationEmployee has an address,
          with a valid alpha-2 representation in its json data
    Then:
        - The OrganizationEmployee's country attribute is fetched
    Test that:
        - The OrganizationEmployee's matching Country object is returned
    """
    emp = factories.OrganizationEmployeeFactory.create(
        json={
            "address": {
                "employee_first_name": "QATest",
                "employee_last_name": "User",
                "address_1": "",
                "address_2": "",
                "city": None,
                "state": "",
                "zip_code": "",
                "country": "US",
            }
        }
    )

    assert emp.country_code == "US"


def test_organization_employee_country__valid_country_alpha_3(factories):
    """
    When:
        - An OrganizationEmployee has an address,
          with a valid alpha-3 representation in its json data
    Then:
        - The OrganizationEmployee's country attribute is fetched
    Test that:
        - The OrganizationEmployee's matching Country object is returned
    """
    emp = factories.OrganizationEmployeeFactory.create(
        json={
            "address": {
                "employee_first_name": "QATest",
                "employee_last_name": "User",
                "address_1": "",
                "address_2": "",
                "city": None,
                "state": "",
                "zip_code": "",
                "country": "USA",
            }
        }
    )

    assert emp.country_code == "US"


def test_organization_employee_country__valid_country_official_name(factories):
    """
    When:
        - An OrganizationEmployee has an address,
          with a valid country name in its json data
    Then:
        - The OrganizationEmployee's country attribute is fetched
    Test that:
        - The OrganizationEmployee's matching Country object is returned
    """
    emp = factories.OrganizationEmployeeFactory.create(
        json={
            "address": {
                "employee_first_name": "QATest",
                "employee_last_name": "User",
                "address_1": "",
                "address_2": "",
                "city": None,
                "state": "",
                "zip_code": "",
                "country": "United States of America",
            }
        }
    )

    assert emp.country_code == "US"
