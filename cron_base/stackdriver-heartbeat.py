#!/usr/bin/env python3
import datetime
import os

# from google.cloud import monitoring

cron_type = os.environ.get("CRON_ALERT_STAT_NAME")
project_id = os.environ.get("GCP_PROJECT", "N/A")


def ping_stackdriver_monitoring_api() -> None:
    # client = monitoring.Client()
    #
    # # resource types and their labels are curated not customizable.
    # # http://stackoverflow.com/a/36263795#comment60209297_36263795
    # # see all predefined types+labels https://cloud.google.com/monitoring/api/resources
    # resource = client.resource("global", labels={"project_id": project_id})
    #
    # # 'metric_kind': monitoring.MetricKind.GAUGE,
    # # 'value_type': monitoring.ValueType.BOOL
    # metric = client.metric(type_="custom.googleapis.com/cron/%s" % cron_type, labels={})
    #
    # client.write_point(metric=metric, resource=resource, value=1)
    print(
        "Stackdriver heartbeat pinged at {now}".format(
            now=datetime.datetime.utcnow().isoformat()
        )
    )


if __name__ == "__main__":
    if cron_type:
        ping_stackdriver_monitoring_api()
    else:
        print("Cron heartbeat is disabled.")
