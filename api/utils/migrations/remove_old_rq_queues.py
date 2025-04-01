import tasks.queues


def remove_old_rq_queues():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    queues_to_remove = [
        "appointments",
        "assets",
        "availability",
        "content",
        "dashboard_reporting",
        "enterprise",
        "forum",
        "marketing",
        "messaging",
        "notify",
        "recommendations",
        "subscriptions",
        "zendesk",
    ]

    for queue_name in queues_to_remove:
        queue = tasks.queues.get_queue(queue_name)
        queue.delete()

    print("🗑️ RQ queues have been deleted! (if they exist)️")


if __name__ == "__main__":
    remove_old_rq_queues()
