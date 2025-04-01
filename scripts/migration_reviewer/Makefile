SHELL := bash
.SHELLFLAGS := -eu -o pipefail -c
.ONESHELL:

MAKEFLAGS += --warn-undefined-variables
MAKEFLAGS += --no-builtin-rules

ifeq ($(VIRTUAL_ENV), )
	RUN_PREFIX := poetry run
else
	RUN_PREFIX :=
endif


# region: environment

bootstrap: pypi-mvn-auth setup-poetry update install install-git-hooks .env  ## Bootstrap your local environment for development.
.PHONY: bootstrap

pypi-mvn-auth:  ## Authenticate with our PyPI mirror.
	@gcloud auth application-default login
.PHONY: pypi-mvn-auth

setup-poetry:  ## Set up your poetry installation with necessary dependencies for working with our PyPI mirror.
	@poetry config virtualenvs.in-project true
	@poetry self update -q
	@poetry self add -q keyrings.google-artifactregistry-auth@latest
.PHONY: setup-poetry

install:  ## Install or re-install your app's dependencies.
	poetry install
.PHONY: install

install-git-hooks:  ## Install or re-install any commit hooks.
	$(RUN_PREFIX) pre-commit install && $(RUN_PREFIX) pre-commit install-hooks
.PHONY: install

update:  ## Update app dependencies
	poetry update
	$(RUN_PREFIX) pre-commit autoupdate
.PHONY: update

# endregion
# region: dev

format:  ## Manually run code-formatters for the app.
	$(RUN_PREFIX) black $(target) --config=pyproject.toml
	$(RUN_PREFIX) isort $(target) --settings-file=pyproject.toml
.PHONY: format

.env: .env.sample  ## Set up a default dotenv file for local development.
	cp .env.sample .env

lint:  ## Run this app's linters. Target a specific file or directory with `target=path/...`.
	$(RUN_PREFIX) black $(target) --check --config=pyproject.toml
	$(RUN_PREFIX) isort $(target) --check --settings-file=pyproject.toml
	$(RUN_PREFIX) flake8 $(target) --config=.flake8
	$(RUN_PREFIX) mypy $(target) --config-file=pyproject.toml
.PHONY: lint

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
