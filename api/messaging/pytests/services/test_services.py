from common.constants import ENVIRONMENT
from messaging.services.zendesk import namespace_subject


def test_namespace_subject():
    subject = "Hello World"
    res = namespace_subject(subject)
    assert res == f"{ENVIRONMENT}: {subject}"
