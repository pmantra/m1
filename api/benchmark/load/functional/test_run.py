from maven.benchmarking.run_locust import run

# used for demo purposes, not possible to test locust locally without full mono setup
try:
    print(run("benchmark/load/functional/run_config.yaml"))
except Exception as e:  # noqa
    print(e)
