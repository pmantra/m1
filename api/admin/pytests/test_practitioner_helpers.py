import pytest

from admin.views.models.practitioner import PractitionerHelpers


class TestPractitionerHelpers:
    @pytest.mark.parametrize("bad_input", [None, ""])
    def test_get_bookable_times__start_time__doesnt_error(self, factories, bad_input):
        practitioner = factories.PractitionerUserFactory.create()
        product = practitioner.products[0]
        bookable_times = PractitionerHelpers.get_bookable_times(
            model=practitioner.profile,
            product=product,
            days=3,
            availability_start_time=bad_input,
        )
        assert bookable_times is not None
