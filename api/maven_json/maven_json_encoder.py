import datetime
from json import JSONEncoder


class MavenJSONEncoder(JSONEncoder):
    def default(self, o):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if isinstance(o, datetime.datetime):
            o = o.replace(tzinfo=None, microsecond=0)
            return o.isoformat()
        elif isinstance(o, datetime.date):
            return o.isoformat()
        else:
            return super().default(o)
