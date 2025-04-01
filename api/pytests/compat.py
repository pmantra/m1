from sqlalchemy.dialects.mysql import DOUBLE
from sqlalchemy.ext.compiler import compiles


@compiles(DOUBLE, "sqlite")
def compile_double_sqlite(type_, compiler, **kw):
    return "REAL"
