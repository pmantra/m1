from pymysql.constants import CLIENT
from sqlalchemy import create_engine

from app import create_app
from storage.connection import db

metadata = db.metadata


if __name__ == "__main__":
    app = create_app()

    def dump(sql, *multiparams, **params):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        print(sql.compile(dialect=engine.dialect))

    for v in app.config["SQLALCHEMY_BINDS"].values():
        engine = create_engine(
            v,
            strategy="mock",
            executor=dump,
            # pymysql backward compatibility
            connect_args={
                "binary_prefix": True,
                "client_flag": CLIENT.MULTI_STATEMENTS | CLIENT.FOUND_ROWS,
            },
        )
        metadata.create_all(engine, checkfirst=False)
        print("*" * 90)
