#!/usr/bin/env python
"""
api/tasks/worker.py

The entrypoint for running an RQ worker consuming and evaluating jobs from one
or more queue.

Usage:
  worker.py [<queue>...]

Options:
  <queue>  Zero or more queues the worker will subscribe to. [default: default]
"""
import sys

if __name__ == "__main__":
    # See https://python-rq.org/docs/workers/#performance-notes
    #
    # Basically the rq worker shell script is a simple fetch-fork-execute loop.
    # When a lot of your jobs do lengthy setups, or they all depend on the same
    # set of modules, you pay this overhead each time you run a job (since
    # you’re doing the import after the moment of forking). This is clean,
    # because RQ won’t ever leak memory this way, but also slow.
    #
    # A pattern you can use to improve the throughput performance for these
    # kind of jobs can be to import the necessary modules before the fork.
    # There is no way of telling RQ workers to perform this set up for you, but
    # you can do it yourself before starting the work loop.

    import ddtrace

    import tasks.queues
    from appointments.tasks.appointment_notifications import *  # noqa: F401,F403
    from appointments.tasks.appointment_rx_notifications import *  # noqa: F401,F403
    from appointments.tasks.appointments import *  # noqa: F401,F403
    from appointments.tasks.availability import *  # noqa: F401,F403
    from appointments.tasks.availability_notifications import *  # noqa: F401,F403
    from appointments.tasks.plan import *  # noqa: F401,F403
    from tasks.enterprise import *  # noqa: F401,F403
    from tasks.forum import *  # noqa: F401,F403
    from tasks.marketing import *  # noqa: F401,F403
    from tasks.messaging import *  # type: ignore[no-redef] # Name "datetime" already defined (by an import) #type: ignore[no-redef] # Name "datetime" already defined (by an import) # noqa: F401,F403
    from tasks.notifications import *  # noqa: F401,F403
    from tasks.payments import *  # type: ignore[no-redef] # Name "datetime" already defined (by an import) #type: ignore[no-redef] # Name "datetime" already defined (by an import) # noqa: F401,F403
    from tasks.programs import *  # noqa: F401,F403
    from tasks.users import *  # noqa: F401,F403
    from tasks.worker_utils import ensure_dependency_readiness

    # this takes the place of a k8s readiness probe.
    # we *must* ensure that the cloud_sql_proxy container is ready (meaning the db is ready to be connected to),
    # otherwise jobs will fail. this functionality cannot be an actual k8s readiness probe because k8s will only use
    # that probe to determine when to allow traffic to be sent to it. this is a worker, however, meaning no traffic is
    # "sent" to it, it pulls off of the queues. in other words, we need to do our own readiness probe at the app level,
    # so that our workers are guaranteed to not start pulling jobs for which they have no database connection.
    ensure_dependency_readiness()

    ddtrace.patch_all()

    # Pull work off of the queue passed in as the first command line argument.
    qs = sys.argv[1:] or ["default"]

    # Blocking call to start the worker process.
    tasks.queues.work(qs)
