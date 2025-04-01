####################
# Core region
# don't modify these core commands.
# eng-exp will support issues with the following command categories in this region:
# setup, lint, code-quality & docs, test, migration, seed,
# discoverability (links + info), docker-up/down/reset/nuke,
# dev shells, logs, attaching to container for debugger,
# and proxying & connect to qa dbs,
# ---
# custom commands go below the core region.
####################

SHELL := bash
.SHELLFLAGS := -eu -o pipefail -c
.ONESHELL:

# ==== Global Script Variables ====
MAKEFLAGS += --warn-undefined-variables
MAKEFLAGS += --no-builtin-rules
CQ_REPORT_FILE ?= $(PWD)/gl-code-quality-report.json
JUNIT_XML_FILE ?= $(PWD)/report.xml
DOCKER_RUN := docker compose run -it --rm
DOCKER_EXEC := docker compose exec -it
export HOST := $(shell hostname)
export GAR_IMAGE_ROOT := us-east1-docker.pkg.dev/maven-clinic-image-builder/mvn

# ==== Global Usage modifiers (works with any command) ====
# build=true will have all the docker commands rebuild your images before the command runs.
# local=true will have the makefile run the same commands with `poetry run` instead of `docker compose run -it api`
# run=true will have the docker command spin up the image & its deps and then tear it down after, letting you run the command once without needing a full docker up.

local ?=
run ?=
ifneq ($(local), )
	ifeq ($(VIRTUAL_ENV), )
		RUN_PREFIX := poetry run
	else
	RUN_PREFIX :=
	endif
else ifneq ($(run), )
	RUN_PREFIX := $(DOCKER_RUN) api
else
	RUN_PREFIX := $(DOCKER_EXEC) api
endif

build ?=
BUILD_FLAG ?=
ifneq ($(build), )
	BUILD_FLAG += --build
endif


# region: setup
########
# Setup / Install
########

setup-local-dev: setup-dotenv setup-docker-auth setup-python setup-poetry ## Run this to get your environment set up for local development
	@if ! [ -z $(local) ]; then $(MAKE) setup-local-interpreter; fi
	$(MAKE) setup-pre-commit
.PHONY: setup-local-dev

## See: https://python-poetry.org/docs/configuration/#virtualenvsin-project to make in-project in-effect
setup-poetry:  ## Ensures Poetry is installed and at version 1.8.3 and auth setup
	@if [ -z "$(local)" ]; then \
		echo "Skipping setup poetry as 'local' variable is empty."; \
	else \
		if ! command -v poetry >/dev/null 2>&1 || [ "$$(poetry --version | awk '{print $$3}')" != "1.8.3" ]; then \
			echo "Installing or reinstalling Poetry version 1.8.3..."; \
			curl -sSL https://install.python-poetry.org | POETRY_VERSION=1.8.3 python3 -; \
		fi; \
		poetry config http-basic.gitlab $GITLAB_USER $GITLAB_TOKEN; \
		poetry config virtualenvs.in-project true; \
		echo "Checking for existing Poetry virtual environment..."; \
		POETRY_ENV_PATH=$$(poetry env info --path 2>/dev/null); \
		if [ -n "$$POETRY_ENV_PATH" ] && [ -d "$$POETRY_ENV_PATH" ]; then \
			echo "Removing existing virtual environment at $$POETRY_ENV_PATH..."; \
			rm -rf "$$POETRY_ENV_PATH"; \
		fi; \
		poetry self add -q keyrings.google-artifactregistry-auth@latest; \
	fi
.PHONY: setup-poetry

setup-python:
	@if [ -n "$(local)" ]; then \
		if ! command -v pyenv >/dev/null 2>&1; then \
			echo "Installing pyenv..."; \
			brew install pyenv \
			export PATH="$${HOME}/.pyenv/bin:$${PATH}"; \
			eval "$$(pyenv init -)"; \
			eval "$$(pyenv virtualenv-init -)"; \
		fi; \
		if ! pyenv versions | grep -q ' 3.9'; then \
			echo "Installing Python 3.9..."; \
			pyenv install 3.9; \
		else \
			echo "Python 3.9 is already installed."; \
		fi; \
		pyenv local 3.9; \
	fi
.PHONY: setup-python

# Also installs pre-commit if it's not found on laptop
# if this is for docker env, install globally, otherwise pre-commit should be already installed in virtual env
setup-pre-commit:  ## Sets up this project's pre-commit hooks
	@if [ -z "$(local)" ]; then \
		if ! pre-commit --version >/dev/null 2>&1; then \
			brew install pre-commit; \
		fi; \
		pre-commit install; \
		pre-commit install-hooks; \
	else \
		if poetry env info --path >/dev/null 2>&1; then \
			poetry run pre-commit install; \
			poetry run pre-commit install-hooks; \
		else \
			echo "No virtual environment found. Please create one with 'make install'."; \
			exit 1; \
		fi; \
	fi
.PHONY: setup-pre-commit

setup-dotenv:  ## Create a local .env file from the sample, if none exists.
	-cp -n ../.env.sample ../.env
.PHONY: setup-dotenv

setup-local-interpreter: install  ## Setup your machine to run the app locally, if you prefer.
	sudo $(MAKE) fixup-etc-hosts
.PHONY: setup-local-interpreter

install: .venv ## Install python dependencies into a local interpreter on your machine. Use `force=1` to recreate the env.
	poetry install
	source .venv/bin/activate  # this doesn't work still need manually source venv
.PHONY: install

.venv:  ## Create a local python virtual environment using pyenv and poetry (does not install dependencies). Use `force=1` to recreate the env.
	@if [ -z "$(local)" ]; then \
		python3.9 -m venv .venv $(VENV_FLAGS); \
	else \
		pyenv local 3.9; \
		poetry env use $$(which python); \
	fi;
.PHONY: .venv

force ?=
VENV_FLAGS ?=
ifneq ($(force), )
	VENV_FLAGS += --clear
endif


update: ## Update python dependencies.
	$(RUN_PREFIX) poetry update $(depends)
.PHONY: update

depends ?=

lock: ## Re-write the lockfile
	$(RUN_PREFIX) poetry lock --no-update
.PHONY: lock


fixup-etc-hosts: /etc/hosts  ## Add localhost aliases for various mono dependencies to your hosts file, if they don't already exist. Requires sudo.
	$(call appendLineToFile,127.0.0.1 mono-mysql,/etc/hosts)
	$(call appendLineToFile,127.0.0.1 mono-redis,/etc/hosts)
	$(call appendLineToFile,127.0.0.1 mono-dd-agent,/etc/hosts)
	$(call appendLineToFile,127.0.0.1 mono-pubsub,/etc/hosts)
	$(call appendLineToFile,127.0.0.1 mono-dd-agent,/etc/hosts)
	$(call appendLineToFile,127.0.0.1 mysql,/etc/hosts)
	$(call appendLineToFile,127.0.0.1 redis,/etc/hosts)
.PHONY: fixup-etc-hosts

setup-docker-auth:  ## Sets up docker to authenticate image pulls from our internal registry
	gcloud auth configure-docker us-east1-docker.pkg.dev
.PHONY: setup-docker-auth
# endregion
# region: testing

########
# Testing
########
#
# ==== Parameters ====
#
# target=<directory-inside-/api> will let you target a specific directory when running any testing or linting framework
# source=<directory-inside-/api> will let you specify a coverage source when running any code-coverage commands.
# ----
# Notes
#
# ~~~~ Breakpoints ~~~~
# import pdb; pdb.set_trace(); works great here w/ docker compose and any test
#

target ?= .
source ?= .

lint: ## Run our linters and formatters. Toggle targets with `target=path/to/target`
	@if [ -z $(local) ] && [ -z `docker compose ps -q api` ] ; then $(MAKE) docker-api-up ; fi
	$(RUN_PREFIX) black $(target) --check --config=pyproject.toml
	$(RUN_PREFIX) flake8 $(target) --config=.flake8
.PHONY: lint

code-quality-report: ## Run code-quality reporting.
	@echo "==== Generating code quality report."
	$(RUN_PREFIX) flake8 $(target) --config=.flake8.cq --output-file=$(CQ_REPORT_FILE) --exit-zero
	@echo "==== Code quality report saved to $(CQ_REPORT_FILE)"
.PHONY: lint

# Run our pytest-backed automated tests.
# ==== Parameters ====
# coverage=true ; run the tests w/ coverage report generation
# source ; set the directory or file to generate coverage report on
# target ; set the directory, file, or specific test to run tests on
# ----
# Examples:
#
# make test
# make test coverage=true
# make test target=authn
# make test target=pytests/utils/test_onboarding_state.py
# make test target=pytests/utils/test_onboarding_state.py::TestOnboardingState
# make test target=pytests/utils/test_onboarding_state.py::TestOnboardingState::test_onboarding_state_transitions

test: ## Run pytest-backed test suite(s). Toggle coverage with `coverage=<true|false>` and run targets with `target=path/to/test.py::test_case`.
	$(run_tests)
.PHONY: test

test-xdist:  ## Run the monolith's test suite with parallelism using pytest-xdist. Review the makefile for args.
	$(RUN_PREFIX) pytest $(testArgsWithDist)
.PHONY: test-xdist

test-last-failed:  ## Run the all tests which failed in the last test run. Review the makefile for args.
	$(RUN_PREFIX) pytest $(testArgs) --last-failed --last-failed-no-failures none
.PHONY: test-last-failed

workerNum ?= $(CI_NODE_INDEX)
workerTotal ?= $(CI_NODE_TOTAL)
projectDir ?= $(CI_PROJECT_DIR)
ifeq ($(projectDir), )
	projectDir := $(target)
endif
fileSuffix ?= -$(ARTIFACT_ID)
ifeq ($(fileSuffix), -)
	fileSuffix :=
endif
coverageFile ?= "$(projectDir)/.coverage$(fileSuffix)"
durationsPath ?= "$(projectDir)/.test_durations$(fileSuffix)"
junitXML ?= "$(projectDir)/report$(fileSuffix).xml"
forceRetry ?= false
numWorkers ?= 8
strategy ?=
testPaths ?=
dist ?= loadscope
ifeq ($(strategy), suites)
	dist := loadgroup
endif
testArgs := $(testPaths) --cov=. --cov-append --cov-report=xml
testArgs += --store-durations --clean-durations --durations-path=$(durationsPath)
testArgs += --junitxml=$(junitXML) -m "$(MARK)"
flaky ?= true
maxFlakes ?= 5
ifeq ($(flaky), true)
	testArgs += --force-flaky --max-runs=$(maxFlakes)
endif
ifeq ($(strategy), splits)
	testArgs += --group=$(workerNum) --splits=$(workerTotal)
endif
testArgsWithDist := $(testArgs) -n $(numWorkers) --dist=$(dist)


connector-tests:
	$(RUN_PREFIX) python -m storage.pytests.runner --coverage
.PHONY: connector-tests


coverage ?=
run_tests := $(RUN_PREFIX) pytest $(target)
ifneq ($(coverage), )
	run_tests := $(RUN_PREFIX) coverage run --source=$(source) -m pytest $(target) --junitxml=$(JUNIT_XML_FILE)
endif


# Generate a coverage report
coverage-report:  ## Generate a coverage report.
	$(RUN_PREFIX) coverage combine .coverage*
	$(RUN_PREFIX) coverage report -m --skip-empty --rcfile=.coveragerc
.PHONY: coverage-report

benchmarks:
	pipx install locust
	locust -f benchmark/locustfile.py
.PHONY: benchmarks


image: ## Build the app's container image.
	@GAR_TOKEN=$(GAR_TOKEN) $(BUILD_CMD) $(BUILD_ARGS) $(target)
.PHONY: image

GAR_TOKEN ?= $(shell gcloud auth application-default print-access-token)
BUILD_CMD ?= docker buildx build
BUILD_ARGS += --secret id=GAR_TOKEN,env=GAR_TOKEN


# endregion
# region: migrations

########
# Migrations
########
# ----
# Notes
#
# Commit any changes to the schema & procedure `.sql` files
# Don't commit any MYSQL SQL tables scoped with the `maven.` database - this will not work for multiverse QA
# For example: (CREATE TABLE `user`) is OK, but not (CREATE TABLE `maven.user`)


# Configurable values (may be overridden by external environment)
DUMP_SCHEMA_DIR ?= schemas/dump
DUMP_DEFAULT_SCHEMA_OUT ?= $(DUMP_SCHEMA_DIR)/default_schema.sql
DUMP_DEFAULT_ROUTINES_OUT ?= $(DUMP_SCHEMA_DIR)/default_routines.sql
DUMP_SERVER_HOST ?= localhost
DUMP_SERVER_USER ?= root
DUMP_SERVER_PASSWORD ?= root
# Internal values
DUMP_ARGS := --skip-dump-date --skip-add-drop-table --lock-tables=false
DUMP_ARGS_SCHEMA := $(DUMP_ARGS) --no-data --skip-triggers
DUMP_ARGS_ROUTINES := $(DUMP_ARGS) --no-data --no-create-info --skip-add-locks --skip-comments --routines
DUMP_ARGS_ALEMBIC_VERSION := $(DUMP_ARGS) --no-create-info --skip-add-locks --skip-comments
DUMP_COMMAND := mysqldump -h $(DUMP_SERVER_HOST) -u $(DUMP_SERVER_USER) --password=$(DUMP_SERVER_PASSWORD)
DUMP_FILTER_COMMAND := sed 's/ AUTO_INCREMENT=[0-9]*//g'
DUMP_FILTER_COMMAND += | sed 's/-- MySQL dump.*/-- MySQL dump/'
DUMP_FILTER_COMMAND += | sed '/-- Server version.*/d'
DUMP_FILTER_COMMAND += | sed '/Warning: Using a password on the command line interface can be insecure./d'
DUMP_FILTER_COMMAND += | sed 's;\*/ /\*!50017 DEFINER=.*\*/ /\*!50003;;g'
DUMP_FILTER_COMMAND += | sed 's;DEFINER=`.*`@`.*` ;;g'
DUMP_FILTER_COMMAND += | tr -d '\r'
DUMP_DEFAULT_SCHEMA_COMMAND := $(DUMP_COMMAND) $(DUMP_ARGS_SCHEMA) maven | $(DUMP_FILTER_COMMAND) > $(DUMP_DEFAULT_SCHEMA_OUT)
DUMP_DEFAULT_ROUTINES_COMMAND := $(DUMP_COMMAND) $(DUMP_ARGS_ROUTINES) maven | $(DUMP_FILTER_COMMAND) > $(DUMP_DEFAULT_ROUTINES_OUT)
DUMP_DEFAULT_ALEMBIC_COMMAND := $(DUMP_COMMAND) $(DUMP_ARGS_ALEMBIC_VERSION) maven alembic_version | $(DUMP_FILTER_COMMAND) >> $(DUMP_DEFAULT_SCHEMA_OUT)


# Migrate your database to the latest head and dump the `maven` schema.
#	then runs the schema dump on your docker mysql service.
# ==== Parameters ====
# name = the name of the new migration to create
# rev = the revision ID to migrate up or down to. Can be a relative negative number if doing migrate-down.
# ----
# Examples:
# make migration name="My new migration"
# make migrate
# make migrate rev=5717819ea650
# make migrate-down
# make migrate-down rev=-2
# make migrate-down rev=5b920d2d16b0

name ?=
rev ?=

migrate: ## Migrate your database to the latest head. Toggle the specific revision with `rev=<sha>`.
	$(RUN_PREFIX) alembic upgrade $(or $(rev), head)
	$(MAKE) dump-maven-schema
	$(MAKE) init-test-dbs
.PHONY: migrate

migrate-down: ## Migrate your database down a revision. Toggle the number of revisions or a specific revision with `rev=<-n|sha>`.
	$(RUN_PREFIX) alembic downgrade $(or $(rev), -1)
	$(MAKE) dump-maven-schema
	$(MAKE) init-test-dbs
.PHONY: migrate-down

migration: ## Create a new migration. Set the name of the migration with `name=<name>`.
	@if [ -z $(name) ] ; then echo $(error_msg) && exit 1 ; fi
	$(RUN_PREFIX) alembic revision -m "$(name)"
.PHONY: migration

init-test-dbs: ## Initialize your local test database for running unit test.
	$(DOCKER_EXEC) mysql .$(DB_INIT_SCRIPT_PATH)
.PHONY: init-test-dbs

DB_INIT_SCRIPT_PATH ?= /docker-entrypoint-initdb.d/init.sh

error_msg := "Can't create migration. 'name' must be defined"

dump-maven-schema: ## Dump the mysql schema for the api database.
	$(DOCKER_EXEC) mysql $(DUMP_DEFAULT_SCHEMA_COMMAND)
	$(DOCKER_EXEC) mysql $(DUMP_DEFAULT_ALEMBIC_COMMAND)
	$(DOCKER_EXEC) mysql $(DUMP_DEFAULT_ROUTINES_COMMAND)
.PHONY: dump-maven-schema

dump-schemas: dump-maven-schema  ## Dump the mysql schemas for the api databases.

# endregion
# region: data
########
# Data
########

seed: ## "Seed" the database with a basic snapshot of configuration data.
	@if ([ -z $(local) ] && [ -z `docker compose ps -q api` ]) ; then $(MAKE) docker-all-up ; fi
	$(RUN_PREFIX) db seed
.PHONY: seed

# endregion
# region: docs
#########
# Docs
#########

# I've no clue how files in /docs are generated so if someone knows the commands plz put them in here too
docs: ## Generate the legacy api endpoint documentation.
	@if ! aglio --version ; then \
		npm install -g aglio ; \
	fi
	aglio -i $(PWD)/docs/v1.apib -o v1.html
	aglio -i $(PWD)/docs/v2.apib -o v2.html
	@echo "==== Docs generated to $(PWD)/v1.html and $(PWD)/v2.html"
	@echo "==== Open them with your favorite browser; like \`open -a \"Google Chrome\" ./v1.html\`"
.PHONY: docs

# endregion
# region: dev environment

########
# Dev / Internal
########

login:  ## Reauthenticate in order to locally access hosted internal resources
	gcloud auth application-default login
.PHONY: login

docker-info:  ## Get basic information about the currently-running docker compose processes.
	docker compose --profile=all ps
.PHONY: docker-info

docker-links:  ## Get host:port (in a hyper-link if possible) configurations for your running docker containers.
	@echo "API: http://localhost$(shell docker port mono-api | grep -o ':.*' | tail -1)/api/v1/_/metadata"
	@echo "ADMIN: http://localhost$(shell docker port mono-admin | grep -o ':.*' | tail -1)/admin"
	@echo "DATA-ADMIN: http://localhost$(shell docker port mono-data-admin | grep -o ':.*' | tail -1)/data-admin"
	@echo "MYSQL: localhost$(shell docker port mono-mysql | grep -o ':.*' | tail -1)"
	@echo "REDIS: localhost$(shell docker port mono-redis | grep -o ':.*' | tail -1)"
.PHONY: docker-links

# Logs
# ----
# Examples
#
# make logs
# make logs scope=api
# make logs scope="api admin"
scope ?=

logs:  ## Tail the logs for your docker containers. Toggle specific workloads with `scope="api admin ..."`.
	docker compose --profile=all logs -f $(scope)
.PHONY: logs

# Attach
# For single container log output and debugger interaction

attach-api: ## Attach the mono-api docker container to a foreground process on your machine.
	docker attach mono-api --detach-keys="ctrl-c"
.PHONY: attach-api

attach-admin: ## Attach the mono-admin docker-container to a foreground process on your machine.
	docker attach mono-admin --detach-keys="ctrl-c"
.PHONY: attach-admin

attach-data-admin: ## Attach the mono-data-admin docker-container to a foreground process on your machine.
	docker attach mono-data-admin --detach-keys="ctrl-c"
.PHONY: attach-data-admin


# API Dev Shell
# ----

dev-shell: ## Open up the api's dev shell.
	$(RUN_PREFIX) dev shell
.PHONY: dev-shell


# Bash Shells
# ----

shell-api:  ## Open up a bash shell in the mono-api docker container.
	$(DOCKER_EXEC) api bash
.PHONY: shell-api

shell-admin: ## Open up a bash shell in the mono-admin docker container.
	$(DOCKER_EXEC) admin bash
.PHONY: shell-admin

shell-data-admin: ## Open up a bash shell in the mono-data-admin docker container.
	$(DOCKER_EXEC) data-admin bash
.PHONY: shell-data-admin

# Python shells
# ----

python-api: ## Open up a python shell in the mono-admin docker container.
	$(DOCKER_EXEC) api python
.PHONY: python-api

python-admin: ## Open up a python shell in the mono-admin docker container.
	$(DOCKER_EXEC) admin python
.PHONY: python-admin

python-data-admin: ## Open up a python shell in the mono-data-admin docker container.
	$(DOCKER_EXEC) data-admin python
.PHONY: python-data-admin

# Open a mysql shell
# Examples
#
# make shell-mysql
# make shell-mysql db=maven
db ?= maven
shell-mysql: ## Open up a mysql shell in the mono-mysql docker container.
	@if [ -z `docker compose ps -q mysql` ] ; then $(MAKE) docker-storage-up ; fi
	docker exec -it mono-mysql mysql --user root -proot --host 127.0.0.1 --port 3306 $(db)
.PHONY: shell-mysql

shell-redis: ## Open up a redis shell in the mono-redis docker container.
	@if [ -z `docker compose ps -q redis` ] ; then $(MAKE) docker-storage-up ; fi
	docker exec -it mono-redis redis-cli
.PHONY: shell-redis

docker-test-up:  ## Startup minimal containers for test / lint purposes
	@GAR_TOKEN=$(GAR_TOKEN) docker compose --env-file=../.env --file=../docker-compose.yml --profile=test up $(BUILD_FLAG) -d
.PHONY: docker-storage-up

docker-storage-up:  ## Startup the storage backends for mono api.
	docker compose --env-file=../.env --file=../docker-compose.yml --profile=storage up $(BUILD_FLAG) -d
	# Sneaking in the dd-agent in case the user wants to test trace export.
	docker compose --env-file=../.env --file=../docker-compose.yml up $(BUILD_FLAG) -d dd-agent
.PHONY: docker-storage-up

docker-api-up:  ## Startup the storage backends, api, admin, and data-admin.
	@GAR_TOKEN=$(GAR_TOKEN) docker compose --env-file=../.env --file=../docker-compose.yml --profile=backend up $(BUILD_FLAG) -d
.PHONY: docker-api-up

docker-backend-up: docker-api-up ## Startup the backends: api, admin, data-admin. (alias for `docker-api-up`).
.PHONY: docker-backend-up

docker-all-up:  ## Startup all services: api, admin, data-admin, flask runtimes, pubsub, web, etc.
	@GAR_TOKEN=$(GAR_TOKEN) docker compose --env-file=../.env --file=../docker-compose.yml --profile=all up $(BUILD_FLAG) -d
.PHONY: docker-all-up

docker-stop:  ## Stop all running services, but leave the containers in-tact.
	docker compose --env-file=../.env --file=../docker-compose.yml --profile=all stop
.PHONY: docker-stop

docker-down:  ## Stop all running services and destroy their containers, but leave the images in-tact.
	docker compose --env-file=../.env --file=../docker-compose.yml --profile=all down
.PHONY: docker-down

docker-nuke:  ## Removes all containers, volumes & db data, networks, and images
	docker compose --profile=all down -v --rmi all
.PHONY: docker-nuke

docker-storage-reset: docker-down  ## Hard-reset docker storage: stop and destroy all containers, delete the associated volumes, restart the containers in the storage group.
	docker volume rm maven_mono-mysql maven_mono-redis
	$(MAKE) docker-storage-up
	@echo "==== Storage reset. Remember to run 'make seed' when the migrations have finished to seed your database."
.PHONY: docker-storage-reset

# endregion
# region: qa

########
# QA
########
# Open a mysql shell to QA1 or 2
# requires you download the `cloud_sql_proxy` and `mysql` clients.
# see: https://cloud.google.com/sql/docs/mysql/sql-proxy#install
# and `brew install mysql`
port ?=
ifeq ($(port), )
	qa1_port ?= 20001
	qa2_port ?= 20002
else
	qa1_port ?= $(port)
	qa2_port ?= $(port)
endif

proxy-db-qa1:  ## Proxy the MySQL instance in QA1 to your local machine. Toggle the port with `port=<port>`.
	cloud_sql_proxy -instances=maven-clinic-qa1:us-central1:mvn-5e1ebb74-mono=tcp:$(qa1_port)
.PHONY: proxy-db-qa1

proxy-db-qa2:  ## Proxy the MySQL instance in QA2 to your local machine. Toggle the port with `port=<port>`.
	cloud_sql_proxy -instances=maven-clinic-qa2:us-central1:mvn-efe82412-mono=tcp:$(qa2_port)
.PHONY: proxy-db-qa2

connect-db-qa1:  ## Connect the MySQL instance in QA1 to via the msql-cli on your local machine. Toggle the port with 'port=<port>'.
	@echo "==== Make sure to run \`make proxy-db-qa1\` in a separate shell."
	@echo "==== Get the password from 1Pass" && \
	mysql --host=127.0.0.1 --port=$(qa1_port) --user=mavenapp --password
.PHONY: connect-db-qa1

connect-db-qa2:  ## Connect the MySQL instance in QA2 to via the msql-cli on your local machine. Toggle the port with 'port=<port>'.
	@echo "==== Make sure to run \`make proxy-db-qa2\` in a separate shell."
	@echo "==== Get the password from 1Pass" && \
	mysql --host=127.0.0.1 --port=$(qa2_port) --user=mavenapp --password
.PHONY: connect-db-qa2

# endregion

# region: meta

.PHONY: help
help: ## Display this help screen.
	@printf "$(BOLD)$(ITALIC)$(MAGENTA)✨  Make Maven with Make. ✨ $(RESET)\n"
	@printf "\n$(ITALIC)$(GREEN)Useful Modifiers: $(RESET)\n"
	@printf "$(CYAN)$(MSGPREFIX) %-$(MAX_CHARS)s$(RESET) $(ITALIC)$(DIM)Use a local python interpreter instead of docker.$(RESET)\n" "local"
	@printf "$(CYAN)$(MSGPREFIX) %-$(MAX_CHARS)s$(RESET) $(ITALIC)$(DIM)Force docker to rebuild dependent containers.$(RESET)\n" "build"
	@printf "$(CYAN)$(MSGPREFIX) %-$(MAX_CHARS)s$(RESET) $(ITALIC)$(DIM)For various test/lint commands, specify the target module or directory.$(RESET)\n" "target"
	@printf "$(CYAN)$(MSGPREFIX) %-$(MAX_CHARS)s$(RESET) $(ITALIC)$(DIM)Use \`docker run\` rather than \`docker exec\` for docker-based commands.$(RESET)\n" "run"
	@printf "\n$(ITALIC)$(GREEN)Supported Commands: $(RESET)\n"
	@grep -E '^[a-zA-Z0-9._-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "$(CYAN)$(MSGPREFIX) %-$(MAX_CHARS)s$(RESET) $(ITALIC)$(DIM)%s$(RESET)\n", $$1, $$2}'

generate-dag-for-mono:
	cd airflow/configs && poetry run python3 generate_dag_with_kpo_on_mono.py --config_file="kpo_on_mono_dag_configs/${config_file}"
.PHONY: generate-dag-for-mono

generate-dags-for-all-mono:
	@for file in $(shell find airflow/configs/kpo_on_mono_dag_configs -type f -name '*.yaml'); do \
		echo "Processing $$file..."; \
		cd airflow/configs && poetry run python3 generate_dag_with_kpo_on_mono.py --config_file="kpo_on_mono_dag_configs/$$(basename $$file)" && cd -; \
	done
.PHONY: generate-dags-for-all-mono

.DEFAULT_GOAL := help

# Messaging
MAX_CHARS ?= 24
BOLD := \033[1m
RESET_BOLD := \033[21m
ITALIC := \033[3m
RESET_ITALIC := \033[23m
DIM := \033[2m
BLINK := \033[5m
RESET_BLINK := \033[25m
RED := \033[1;31m
GREEN := \033[32m
YELLOW := \033[1;33m
MAGENTA := \033[1;35m
CYAN := \033[36m
RESET := \033[0m
MSGPREFIX ?=   »

# Append line ($1) to file ($2) if it doesn't exist.
define appendLineToFile
	if ! grep -q "$(1)" "$(2)" ; then \
		echo "$(1)" >> $(2) ; \
	fi
endef

# endregion

####################
# end eng-exp region
####################
# custom commands below
