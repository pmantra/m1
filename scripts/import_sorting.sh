#!/bin/bash

# set the flag that will allow isort exit code to be exposed to the job
export ALLOW_ISORT_FAIL_SIGNAL=1

pre-commit run isort --all-files
