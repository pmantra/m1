from braze import client
from tasks.queues import job


@job(team_ns="enrollments")
def fetch_maus() -> None:
    braze_client = client.BrazeClient()
    braze_client.get_mau_count()


@job(team_ns="enrollments")
def fetch_daus() -> None:
    braze_client = client.BrazeClient()
    braze_client.get_dau_count()
