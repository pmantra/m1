from direct_payment.invoicing.utils import generate_user_friendly_report_cadence


def test_generate_user_friendly_report_cadence_invalid_input():
    assert not generate_user_friendly_report_cadence(123, None)

    assert not generate_user_friendly_report_cadence(123, "1 ** 234 *")


def test_generate_user_friendly_report_cadence_valid_input():
    assert (
        generate_user_friendly_report_cadence(123, "* * 20 * *")
        == "on day 20, every month"
    )

    assert (
        generate_user_friendly_report_cadence(123, "* * 20 10 *")
        == "on day 20, October"
    )

    assert generate_user_friendly_report_cadence(123, "* * * * 0") == "every Sunday"
    assert (
        generate_user_friendly_report_cadence(123, "* * 15 3 5")
        == "on day 15, March, every Friday"
    )
    assert (
        generate_user_friendly_report_cadence(123, "* * * * *")
        == "every day, every month"
    )
