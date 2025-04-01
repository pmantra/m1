FROM python:3.9-slim as base

WORKDIR /api

FROM python:3.9 as requirements

ENV POETRY_VERSION="1.8.5"
ENV POETRY_URL="https://install.python-poetry.org"
ENV RUNTIME_GROUPS="main,server,airflow,database,services,integrations,instrumentation,utilities,opencensus,google,shell,temporary"
ENV DEV_GROUPS="test,lint,dev"

SHELL ["/bin/bash", "-o", "pipefail", "-c"]
RUN curl -sSL "${POETRY_URL}" | python3 -

COPY pyproject.toml pyproject.toml
COPY poetry.lock poetry.lock
COPY wheelhouse wheelhouse
RUN /root/.local/bin/poetry export  \
    --without-urls  \
    --without-hashes \
    --only="${RUNTIME_GROUPS}"  \
    -f requirements.txt  \
    -o requirements.txt
RUN /root/.local/bin/poetry export  \
    --without-urls  \
    --without-hashes  \
    --only="${DEV_GROUPS}"  \
    -f requirements.txt  \
    -o dev-requirements.txt

# Core runtime dependencies. Built with heavy image to support compiling outdated dists.
FROM python:3.9 as dependencies

WORKDIR /api

ENV PIP_DEFAULT_TIMEOUT=100 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_PREFER_BINARY=1 \
    PIP_NO_INPUT=1 \
    GAR_PYPI="${GAR_PYPI:-'us-east1-python.pkg.dev/maven-clinic-image-builder/pypi-mvn/simple'}" \
    GAR_USER="${GAR_USER:-oauth2accesstoken}"

COPY --from=requirements requirements.txt requirements.txt
COPY --from=requirements wheelhouse /wheelhouse

RUN --mount=type=secret,id=GAR_TOKEN \
    python -m venv .venv \
    && PIP_EXTRA_INDEX_URL="https://${GAR_USER}:$(cat /run/secrets/GAR_TOKEN)@${GAR_PYPI}" \
    .venv/bin/pip install -r requirements.txt

# Dev dependencies, layered on top of our runtime dependencies.
FROM dependencies as dev-dependencies

COPY --from=requirements dev-requirements.txt dev-requirements.txt

RUN --mount=type=secret,id=GAR_TOKEN \
    PIP_EXTRA_INDEX_URL="https://${GAR_USER}:$(cat /run/secrets/GAR_TOKEN)@${GAR_PYPI}" \
    .venv/bin/pip install -r dev-requirements.txt


# Compile static web assets for the admin frontend
FROM node:14-slim AS admin-js-builder
WORKDIR /api/admin/js
COPY ./admin/js .
# Avoid storing npm dependencies to optimize cache performance in the common case when admin/js is unchanged.
RUN npm ci && \
    npm run prod:v2 && \
    rm -rf node_modules

# Install the contentful CLI
FROM debian:stable-slim AS contentful

ARG contentful_version="1.19.1"
ENV CONTENTFUL_HOST=${CONTENTFUL_HOST:-"https://github.com/contentful/contentful-cli/releases/download"}
ENV CONTENTFUL_SOURCE_URL="${CONTENTFUL_HOST}/v${contentful_version}/contentful-cli-linux-${contentful_version}.zip"

# We want the extra dependencies so that we can perform cert verification.
# hadolint ignore=DL3015
RUN apt-get update -yq && apt-get install -yq wget unzip && \
		wget -O /tmp/contentful-cli.zip ${CONTENTFUL_SOURCE_URL} && \
    unzip /tmp/contentful-cli.zip -d /usr/local/bin && \
    chmod +x /usr/local/bin/contentful && \
    rm -f /tmp/contentful-cli.zip

# Builder image layer
FROM base as builder

ENV PYTHONFAULTHANDLER=1 \
    PYTHONHASHSEED=random \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TZ="UTC" \
    VIRTUAL_ENV=/api/.venv

# Image API depends upon python-magic, which needs libmagic.
# 	https://pypi.org/project/python-magic/
RUN apt-get update -yq \
    && apt-get install -yq --no-install-recommends libmagic1 gnupg \
    && apt-get clean

COPY --from=admin-js-builder /api/admin/static/js/app-min-v2.js admin/static/js/app-min-v2.js
COPY --from=contentful --chown=nonroot /usr/local/bin/contentful /usr/local/bin/contentful
COPY . .

COPY --from=dev-dependencies --chown=nonroot /api/.venv .venv
RUN .venv/bin/pip install -q -e .

ENV PATH=${VIRTUAL_ENV}/bin:${PATH}

# Compile externalized translations
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
RUN find . -name "*.po" -type f ! -path './.venv/*' | sed "s/\.po$//" | xargs -I% pybabel compile -i %.po -o %.mo --use-fuzzy

# Dev API image
FROM builder as api
EXPOSE 8888/tcp

COPY application_dev.py application_dev.py

CMD ["gunicorn", "-c", "gunicorn_config.py", "--logger-class", "gunicorn_logging.GunicornLogger", "application:wsgi"]


# Runtime environment with subset of dependencies and allowed source code appropriate for production
FROM builder as api-deploy

RUN rm -rf \
    data_admin \
    conftest.py \
		tests \
    ./*pytests* \
    /api/.venv

COPY --from=dependencies --chown=nonroot /api/.venv .venv
RUN .venv/bin/pip install -q -e .

ENTRYPOINT [".venv/bin/python", "-m"]
CMD ["gunicorn", "-c", "gunicorn_config.py", "--logger-class", "gunicorn_logging.GunicornLogger", "application:wsgi"]
