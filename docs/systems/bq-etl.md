# BigQuery Export Transform Load (ETL)

**This file no longer maintained. It has been ported to [Notion](https://www.notion.so/mavenclinic/Bigquery-Data-Export-50aed88e13ec45b28ea2f331a814edaa).**

The `bq-etl` system takes data from the Maven backend and loads it into
BigQuery where it can be consumed by the Growth team.


## Guides

- [Guide to exporting new data to BQ](/docs/guides/adding-a-new-table-to-bq.md)


## Source

- [application](/api/events_join_data/export_event_join_tables.py)
- [cron](/api/cron/crontab)
- [tests](/api/tests/test_export_event_join_tables.py)


## Design

The export process starts with the api cron service that enqueues four
export-specific tasks on a regular cadence: `midnight`, `every_five_hours`,
`every_three_hours`, and `hourly`. These regular cadence tasks enqueue specific
data export tasks, which may in turn enqueue tasks that export a smaller chunk
of the given data domain. The export chunk tasks serialize data as line
delimited json objects conforming to the schema of the intended BigQuery table,
and write those records into a storage bucket from which it can be loaded into
BigQuery.

When data is exported into a BigQuery table, the entire contents of the table
are reconstructed and replaced. This makes changes to the export logic or
export table schema easy to deploy since all historical data will be updated to
the new format the next time the export task is run.


## Configuration

- Environment Variable `ETL_SYNC_BUCKET`: The name of the bucket through which
  exported data will be loaded into BigQuery.
- Implicit: The BigQuery client library we use infers which project to use (e.g.
`maven-clinic` or `maven-clinic-qa`) [from the environment](https://googleapis.dev/python/bigquery/latest/generated/google.cloud.bigquery.client.Client.html).


## Deployment

### Services

The `bq-etl` system runs as part of the existing [api-cron](/docs/services/backend/api-cron.md)
and [workers](/docs/serivces/backend/workers.md) services, making use of
[google cloud storage](/docs/services/gcp/storage.md) to load data into
[BigQuery](/docs/services/gcp/bq.md). A [redis](/docs/services/backend/redis.md)
based distributed lock is used to avoid concurrently loading data into the same
BigQuery table.

### Migrations

BigQuery table migrations are currently performed manually before the
corresponding worker code is deployed. There are two options for applying
schema changes: 1. You can use the [`bq rm`](https://cloud.google.com/bigquery/docs/reference/bq-cli-reference#bq_rm)
and [`bq mk`](https://cloud.google.com/bigquery/docs/reference/bq-cli-reference#bq_mk)
cli commands to drop and create the changed schema as described by the json
schema files we maintain with the source code or 2. You can use the interactive
cloud console to apply schema changes as [shown here](https://cloud.google.com/bigquery/docs/managing-table-schemas).

**note for the future**: since tables are completely reconstructed when
exported, it should be possible in the future to programmatically drop and
create the BQ tables right as data is being exported.


## Testing

Test cases can extend the `BaseExportShardManagerTest` class which patches the
method that delivers serialized records to the bucket, instead asserting that
exported records have expected values.


## QA

`bq-etl` can be fully operated on `QA2` where the `ETL_SYNC_BUCKET` refers to a
suitble existing bucket.
