import types

# see https://github.com/wtforms/wtforms/blob/2.3.3/tests/fields.py
from wtforms.form import Form

from admin.views.base import AmountDisplayCentsInDollarsField


def make_form(_name="F", **fields):
    return type(str(_name), (Form,), fields)


# see https://github.com/wtforms/wtforms/blob/2.3.3/tests/common.py
class DummyPostData(dict):
    def getlist(self, key):
        v = self[key]
        if not isinstance(v, (list, tuple)):
            v = [v]
        return v


class TestAmountDisplayCentsInDollarsField:
    def test_handle_stored_null(self):
        F = make_form(price=AmountDisplayCentsInDollarsField())
        form = F(price=None)
        assert form.price._value() == ""

    def test_handle_stored_value(self):
        F = make_form(price=AmountDisplayCentsInDollarsField())
        form = F(price=2499)
        assert form.price._value() == "24.99"

    def test_handle_submitted(self):
        F = make_form(price=AmountDisplayCentsInDollarsField())
        form = F(DummyPostData(price="750.00"))
        obj = types.SimpleNamespace()
        form.populate_obj(obj)
        assert obj.price == 75000

    def test_handle_submitted_invalid(self):
        F = make_form(price=AmountDisplayCentsInDollarsField())
        form = F(DummyPostData(price="0.625"))
        form.validate()
        assert len(form.errors) == 1

    def test_handle_submitted_empty_input(self):
        F = make_form(price=AmountDisplayCentsInDollarsField())
        form = F(DummyPostData(price=""))
        obj = types.SimpleNamespace()
        form.populate_obj(obj)
        assert obj.price is None

    def test_handle_submitted_no_negatives(self):
        F = make_form(price=AmountDisplayCentsInDollarsField())
        form = F(DummyPostData(price="-0.99"))
        form.validate()
        assert len(form.errors) == 1

    def test_handle_submitted_allow_negatives(self):
        F = make_form(price=AmountDisplayCentsInDollarsField(allow_negative=True))
        form = F(DummyPostData(price="-42.42"))
        obj = types.SimpleNamespace()
        form.populate_obj(obj)
        assert obj.price == -4242
