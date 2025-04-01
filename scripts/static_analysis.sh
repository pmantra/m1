#!/bin/bash

# set the flag that will allow mypy exit code to be exposed to the job
export ALLOW_MYPY_FAIL_SIGNAL=1

# run mypy on the enforced glob patterns
pre-commit run mypy --all-files
