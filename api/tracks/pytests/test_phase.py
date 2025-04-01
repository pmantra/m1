import pytest

from models.tracks.phase import (
    PhaseNamePrefix,
    UnrecognizedPhaseName,
    convert_legacy_phase_name,
    ensure_new_phase_name,
)


@pytest.mark.parametrize(
    argnames="module_name,legacy_phase_name,new_phase_name",
    argvalues=[
        ("adoption", "adoption", PhaseNamePrefix.STATIC),  # static
        ("adoption", "adoption-end", PhaseNamePrefix.END),  # end
        (
            "breast_milk_shipping",
            "bms-end",
            PhaseNamePrefix.END,
        ),  # end phase where module name isn't prefix of phase name
        ("pregnancy", "week-1", "week-1"),  # weekly with 1-digit week number
        ("postpartum", "week-40", "week-40"),  # weekly with 2-digit week number
    ],
)
def test_convert_valid_legacy_phase_name(
    module_name: str, legacy_phase_name: str, new_phase_name: str
):
    assert convert_legacy_phase_name(legacy_phase_name, module_name) == new_phase_name


@pytest.mark.parametrize(
    argnames="module_name,legacy_phase_name",
    argvalues=[
        ("adoption", "static"),  # new phase name not recognized as legacy name
        ("generic", "random"),  # invalid phase name
        ("pregnancy", "week-a"),  # week is not an integer
        ("pregnancy", "month-1"),  # unknown phase duration
        ("surrogacy", "surrogacy_end"),  # 'end' phases use a hyphen (-end)
    ],
)
def test_convert_invalid_legacy_phase_name(module_name: str, legacy_phase_name: str):
    with pytest.raises(UnrecognizedPhaseName):
        convert_legacy_phase_name(legacy_phase_name, module_name)


@pytest.mark.parametrize(
    argnames="module_name,input_phase_name,expected_phase_name",
    argvalues=[
        ("adoption", "adoption", PhaseNamePrefix.STATIC),  # legacy static
        ("adoption", "static", PhaseNamePrefix.STATIC),  # new static
        ("adoption", "adoption-end", PhaseNamePrefix.END),  # legacy end phase
        ("adoption", "end", PhaseNamePrefix.END),  # new end phase
        ("pregnancy", "week-1", "week-1"),  # weekly (same for new/legacy)
    ],
)
def test_ensure_new_phase_name(
    module_name: str, input_phase_name: str, expected_phase_name: str
):
    assert ensure_new_phase_name(input_phase_name, module_name) == expected_phase_name
