import pytest

from preferences import repository


class TestBaseRepository:
    def test_init_with_uow_normal(self, session):
        repo = repository.PreferenceRepository(session=session, is_in_uow=True)
        assert repo is not None

    def test_init_with_uow_exception(self):
        with pytest.raises(ValueError):
            repository.PreferenceRepository(is_in_uow=True)
