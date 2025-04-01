import pytest


@pytest.fixture(scope="package", autouse=True)
def apply_patch_e9y_service_functions(patch_e9y_service_functions):
    yield
