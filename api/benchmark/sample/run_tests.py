from pprint import pprint

from maven.benchmarking.run_locust import run

try:
    pprint(run("run_config.yaml"))
except Exception as e:  # noqa
    pprint(e)
