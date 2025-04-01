# How to run locust load tests locally

Refer to the documentation located [here](https://gitlab.com/maven-clinic/packages/maven-sdk-benchmarking-python) at maven-sdk-benchmarking-python.

## Prerequisites
* You need to have locust installed
* maven-sdk-benchmarking-python configured in pyproject.toml. Locally right now, this requires a few workarounds:

Add the following as a source in pyproject.toml:
`[[tool.poetry.source]]
name = "pypi-mvn"
url = "https://us-east1-python.pkg.dev/maven-clinic-image-builder/pypi-mvn/simple/"
priority = "explicit"
`

Add `maven-sdk-benchmarking-python = {version = "*", source = "pypi-mvn"}` to the `tool.poetry.dependencies` section

Comment out `#Flask = "^1.1.2"` and `#opencensus-ext-flask = "^0.7.3"`

## How to run
1. Make sure you have the libraries installed locally
2. Configure the tests you want to run, point your new config to a file and adjust the configurations for how you want locust to run
3. Run the `test_run.py` and see output in your console