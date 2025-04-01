# Google Cloud SDK Setup
- visit https://cloud.google.com/sdk/#Quick_Start

### Create a project
- Someone on the dev team will do this for you so that Maven pays the bill :) Once you have your project name, set it as the `gcloud` default by running `gcloud config set core/project PROJECT_NAME` on your machine.

### for sharing the image builder GCR (Google Container Registry) repo on cloud storage with other projects
Zach or another owner or the image builder project needs to run this for you - you can get the compute engine default service account at: https://console.cloud.google.com/permissions/serviceaccounts?project=YOUR_PROJECT

```
PROJECT_ID=maven-clinic-image-builder
ROBOT=YOUR_DEFAULT_SVC_ACCOUNT@developer.gserviceaccount.com
gsutil iam ch serviceAccount:$ROBOT:objectViewer gs://artifacts.$PROJECT_ID.appspot.com
```

# Deploying a new project using the deployment manager

### Enable the APIs
"Enable" in your project (don't worry about the "credentials" prompt)

- https://console.cloud.google.com/apis/api/deploymentmanager/overview
- https://console.cloud.google.com/apis/api/sqladmin/overview

### Create a new config

- Copy `dev.yml.tmpl` info a new file, `dev.yml`, change the settings as needed, and save as for example `dev.yml` in this folder. Generally for a dev environment, the only settings you need to change is the password for the master auth for the cluster.
- For a QA/production cluster, increase the disk sizes for the disks you need to >0 `GB` and add some not-blank values for the cloud storage buckets, which will create those for log and analytics use.
- We don't want to commit that `YOUR_CONFIG.yml` file to the repo, so please be careful not to do that :) All `.yml` files are ignored by git by default within this directory...

### Create the resources

- `gcloud config set core/project YOUR_PROJECT` or use the `--project` arg in the below command
- `gcloud deployment-manager deployments create maven --config YOUR_CONFIG.yml`
- wait for success, or fix any errors you find. It should "just work"...
- add the DB metadata: add a key called `cloud-sql-instances` with a value of `PROJECT_NAME:AUDIT_DB_REGION:DEFAULT_DB_NAME=tcp:3306,PROJECT_NAME:AUDIT_DB_REGION:AUDIT_DB_NAME=tcp:3305`. `DB_REGION` and `*_DB_NAME` are defined in the config `yml` above. The 2 db names can be the same (they usually are, except in production!)

### Setup cluster log storage and anaytics

The buckets are created based on the names you provide in the `google_deployment_manager` `yml` file. You'll need those here.

- copy pixel from production to your pixel bucket
- logs bucket name cannot be too long

- `gsutil acl ch -g cloud-storage-analytics@google.com:W gs://${LOGS_BUCKET}/`
- `gsutil logging set on -b gs://${LOGS_BUCKET} gs://${PIXEL_BUCKET}/`
- `gsutil logging get gs://${PIXEL_BUCKET}/`

- set metadata for events-etl (Three GCS buckets in GCP project metadata)
- set metadata for syslog archive bucket

- create `events` and `stats` datasets in BigQuery.

### Updating a GKE cluster

We're doing this manually for now. TODO is a script here or better docs.

## To update the deployment

See [Google's docs](https://cloud.google.com/deployment-manager/step-by-step-guide/updating-a-deployment) for limitations. Generally you can coordinate with the backend team about doing this...

- `gcloud deployment-manager deployments update maven --config YOUR_CONFIG.yml --preview` (optional)
- `gcloud deployment-manager deployments update maven`

## DB Access

You'll need to enable the https://console.cloud.google.com/apis/api/sqladmin/overview API for your project before this will work.

Do the below steps in your home folder (e.g. `cd ~`).

### Install cloud sql proxy
You will need `wget` installed for this to work, or I think you can visit the URL below in chrome and it will download it for you. Run `which wget` to see if you have `wget` installed. Using `homebrew` is the best way to get `wget` if you want it and don't have it installed.

```
wget https://dl.google.com/cloudsql/cloud_sql_proxy.darwin.amd64
mv cloud_sql_proxy.darwin.amd64 cloud_sql_proxy
chmod +x cloud_sql_proxy
mv cloud_sql_proxy /usr/local/bin/cloud_sql_proxy
```

### Use cloud sql proxy
(Docs)[https://cloud.google.com/sql/docs/sql-proxy] for more info on connection strings like the instances arg. You need to download the SERVICE_ACCOUNT_JSON_CREDENTIALS_PATH file from the Google Cloud Developers Console and then note where it is stored to use below.

To do that, go to https://console.cloud.google.com/permissions/serviceaccounts?project=maven-clinic-YOU-dev, make a new service account and download a JSON key for use below as SERVICE_ACCOUNT_JSON_CREDENTIALS_PATH. Don't enalbe domain-wide delegation.

```
cd ~
mkdir cloudsql
export GOOGLE_APPLICATION_CREDENTIALS=~/SERVICE_ACCOUNT_JSON_CREDENTIALS_PATH
/usr/local/bin/cloud_sql_proxy -dir=/Users/YOU/cloudsql -instances=project-name:db-region:db-name
```

Connect with a socket type connection in sequel pro eg: /Users/YOU/cloudsql/project-name:db-region:db-name
