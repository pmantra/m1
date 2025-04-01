from functools import wraps


def transaction(func):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    @wraps(func)
    def wrapper(self, *args, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        try:
            result = func(self, *args, **kwargs)
            self.session.commit()
            return result
        except Exception as e:
            self.session.rollback()
            raise Exception(e)

    return wrapper


def chunk(iterable, n):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    for i in range(0, len(iterable), n):
        yield iterable[i : i + n]
