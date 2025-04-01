from tasks.queues import job

from .sitemap import update as _update


@job
def update_sitemap() -> None:
    _update()
