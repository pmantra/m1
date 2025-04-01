from utils.transactional import only_on_successful_commit


def test_only_on_successful_commit(db):
    class Foo:
        def __init__(self) -> None:
            self.func_calls = 0

        @only_on_successful_commit
        def some_after_commit_logic(self) -> int:
            self.func_calls += 1
            return 1

    first_bar = Foo()
    second_bar = Foo()

    assert first_bar.func_calls == 0
    assert second_bar.func_calls == 0

    with db.session.begin_nested():
        first_bar.some_after_commit_logic()

        assert first_bar.func_calls == 0

    assert first_bar.func_calls == 1
    assert second_bar.func_calls == 0

    with db.session.begin_nested():
        second_bar.some_after_commit_logic()

        assert second_bar.func_calls == 0

    assert first_bar.func_calls == 1
    assert second_bar.func_calls == 1

    try:
        with db.session.begin_nested():
            first_bar.some_after_commit_logic()
            raise Exception("Rollback")
    except Exception:
        pass

    assert first_bar.func_calls == 1
    assert second_bar.func_calls == 1

    with db.session.begin_nested():
        first_bar.some_after_commit_logic()
        first_bar.some_after_commit_logic()
        second_bar.some_after_commit_logic()

        assert first_bar.func_calls == 1
        assert second_bar.func_calls == 1

    assert first_bar.func_calls == 3
    assert second_bar.func_calls == 2

    with db.session.begin_nested():
        first_bar.some_after_commit_logic()
        try:
            with db.session.begin_nested():
                first_bar.some_after_commit_logic()
                second_bar.some_after_commit_logic()
                raise Exception("Rollback")
        except Exception:
            pass

        assert first_bar.func_calls == 3
        assert second_bar.func_calls == 2

    assert first_bar.func_calls == 4
    assert second_bar.func_calls == 2
