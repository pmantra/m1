#!/bin/sh
# start-cron.sh

# shellcheck disable=SC2155
export GCP_PROJECT="$(curl -s "http://metadata.google.internal/computeMetadata/v1/project/project-id" -H "Metadata-Flavor: Google")"
# TODO make export/re-import env variables more reliable with quoted strings. See https://goo.gl/vwVtMh
env | sed 's/^\(.*\)$/export \1/g' > /root/cron-env.sh

# from http://stackoverflow.com/questions/34962020/cron-and-crontab-files-not-executed-in-docker
touch /etc/crontab

# append onbuild specific crontabs into system cron
test -e /etc/crontab-onbuild && cat /etc/crontab-onbuild >> /etc/crontab

# make sure /etc/contab has a trailing newline
echo >> /etc/crontab

rsyslogd
cron
touch /var/log/cron.log
tail -F /var/log/syslog /var/log/cron.log
