def paginate(q, col, size=100, chunk=False):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """
    Yields a SQLAlchemy query of param size, useful for minimizing memory use of large result sets.

    ex:
        for u in paginate(User.query, User.id):
            print(y) # yields records 100 at a time
    """
    q = q.order_by(col)
    last_id = None

    while True:
        sub_q = q
        if last_id is not None:
            sub_q = sub_q.filter(col > last_id)

        _chunk = sub_q.limit(size).all()
        if not _chunk:
            break
        last_id = getattr(_chunk[-1], col.name)

        if chunk:
            yield _chunk
        else:
            for row in _chunk:
                yield row
