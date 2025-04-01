import pytest

from utils.dotdict import DotDict


def test_DotDict():
    # defaults
    dd = DotDict()
    assert dd.foo is None
    with pytest.raises(AttributeError):
        # foo is None
        dd.foo.bar

    # nested instantiation
    dd = DotDict({"foo": {"bar": "baz"}})
    assert dd.foo.bar == "baz"
    dd = DotDict({"foo": {"bar": {"baz": "qux"}}})
    assert dd.foo.bar.baz == "qux"

    # nested assignment
    dd = DotDict()
    dd.foo = {"bar": "baz"}
    assert dd.foo.bar == "baz"
    # and reassignment
    dd.foo = 123
    with pytest.raises(AttributeError):
        # foo is a number
        dd.foo.bar
    assert dd.foo == 123
