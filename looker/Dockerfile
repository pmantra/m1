FROM ubuntu:18.04

# https://github.com/hadolint/hadolint/wiki/DL4006
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Looker needs its own user and group
RUN adduser --disabled-password --gecos '' --shell /bin/bash looker

# Disable the interactive time zone selection
ARG DEBIAN_FRONTEND=noninteractive

# git and tzdata are needed at runtime by Looker
# curl & bzip2 are needed during the build (in principle, we could extract this)
# libfontconfig1 is a requirement for PhantomJS
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    tzdata \
    locales \
    git \
    bzip2 \
    zstd \
    fonts-freefont-otf \
    openjdk-8-jdk \
    chromium-browser \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
# N.B. - chrommium is temporarily disabled by not symlinking it

# Set the time zone
ARG TZ=Etc/UTC
RUN echo $TZ > /etc/timezone && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && date

# Run a locale generatation and set the same environment variables for runtime
RUN locale-gen en_US.UTF-8
ENV LANG='en_US.UTF-8' LANGUAGE='en_US:en' LC_ALL='en_US.UTF-8'

COPY run-looker /usr/local/bin
RUN chmod a+x /usr/local/bin/run-looker

WORKDIR /home/looker/looker

CMD ["su", "looker", "-c", "/usr/local/bin/run-looker"]
