# How to run the benchmark SDK (locust tests)

Refer to the documentation located [here](https://gitlab.com/maven-clinic/packages/maven-sdk-benchmarking-python) at maven-sdk-benchmarking-python.


## How to run
1. Make sure you have the SDK installed locally
2. Configure the tests you want to run
   1. This is easily achieved by inheriting the parent classes provided by the SDK to abstract away user creation, user authentication, and user deletion.
   2. An example can be found in `sample/sample_test.py`
   3. Please remember to add `@locust.task(weight=n)` where `n` is the probability of the API being called among all the other tasks.
3. Point your new config to a file and adjust the configurations for how you want locust to run
   1. An example can be found in `sample/run_config.yaml`
3. Utilize the `run` utility from the SDK to read the config yaml and run all tests.
   1. An example can be found in `sample/run_tests.py`
   2. An example no auth (`will not mess up with auth0`) test run against QA2 can be found in `sample/run_no_auth_tests.py`

## Recommendation
1. For running the load testing, we recommend to keep the QPS around 200