FROM python:3.8

RUN apt-get update && apt-get install -y --no-install-recommends -qq \
    cron \
    curl \
    rsyslog \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

#RUN pip install --upgrade setuptools>=40.3.0 && pip install google-cloud-monitoring>=2.11.0

ENV K8S_VERSION="v1.14.3"
RUN curl -so /usr/local/bin/kubectl "https://storage.googleapis.com/kubernetes-release/release/${K8S_VERSION}/bin/linux/amd64/kubectl" \
 && chmod +x /usr/local/bin/kubectl

COPY stackdriver-heartbeat.py /usr/local/bin/stackdriver-heartbeat
COPY start-cron.sh /usr/local/bin/start-cron.sh
COPY crontab /etc/crontab-base
RUN cat /etc/crontab-base > /etc/crontab \
 && touch /var/log/cron.log

ONBUILD COPY crontab /etc/crontab-onbuild
ONBUILD CMD ["/usr/local/bin/start-cron.sh"]
