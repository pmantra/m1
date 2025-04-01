# Remote Cluster Setup

We use Google Container Engine (GKE) to manage our remote clusters. Creating these and updating them is done in the `google_deployment_manager` folder that's a sibling of this `kubernetes` folder in the `maven` repo. See there for details. To get autorized on kubectl for a remote cluster, the quickstart is something like:

- `gcloud config set core/project CLUSTER_PROJECT` or use the `--project` arg in the below commands
- `gcloud config set compute/zone us-central1-a` (or your zone if you changed that)
- `gcloud components update kubectl`
- get cluster auth set up for `kubectl` (e.g. `gcloud container clusters get-credentials maven`) using the cluster name
- see available contexts use `kubectl config view`
- switch clusters on `kubectl`, use `kubectl config use-context CONTEXT_NAME`

# Cluster Management

The bulk of this folder has templates for the resources we create on our kubernetes clusters. These are in the `resources` folder, and are rendered into finished templates by a container called `deployer` build from the `Dockerfile` right here. This container runs build and update scripts and then uses `kubectl` to apply those changes. It's meant to be run inside the cluster it is managing, as a one-time job submitted by either a cluster admin or a bot.
### First-time admin tasks

- add `maven` database using sequel pro (use the DB connection info on the `Cloud SQL Proxy` section of the `README` at the root of this repo). It should be `utf8mb4/utf8mb4_unicode_ci` when you create it.
- init DB to create all the tables in the models on your current branch by running `kubectl exec -it API_POD_NAME db init` (Get the API Pod's name from `kubectl get pods`)You need a local `docker` to set up cluster infrastructure.

### Secrets/Config

You need to add some `secrets` and some `configs` to the cluster before we can add the services. Get a copy of secrets from a running cluster, a backup from and admin, or just generate the files by reverse-engineering the container definitions in the various services we deploy.

- `secrets` are base64 encoded strings. To create on, use `echo -n SECRET | base64`. The `-n` is important because it supresses the default trailing newline. You'll need `base64` installed before that will work (installed by default on Mac OS).
- `configs` (ConfigMaps to be precise) are similar to `secrets` but don't need to be base64-encoded.

Here's a good workflow for updating secrets/configs. Check that your kubeconfig pointed at the right cluster first :)

- `kubectl get configmaps api -o yaml > ~/Desktop/config.yml`
- edit the file as needed
- `kubectl apply -f ~/Desktop/config.yml`
- `rm ~/Desktop/config.yml`

For secrets, the process is the same but the first step would be:
- `kubectl get secrets api -o yaml > ~/Desktop/secrets.yml`

#### APNS Certificates Updates

- Follow the normal flow to update the `apns-certs` secret
- Restart the workloads that send push notifications: `worker-notify`

## RQ Worker Alert

- We are monitoring all the RQ active queues to prevent RQ jobs from not being run in time.
- Every 3 minutes we ping active worker nodes to collect all active queues they consume tasks from.
- Worker alerts are setup to send emails to the backend team when one or more RQ queues don't have worker consumers.
- Worker node restarts (with a different name) or resizing (increase or decrese of worker node consumers for a given RQ queue) does not affect the worker alert because there will still be at least one worker node consumes tasks from the queue.

## Cron Alerts
- Cron heartbeat machinery are baked into the `cron_base` image (see `cron_base/*` for details). When turned on, it pings GCP stackdriver monitoring service every 2 minutes (adjustable).
- k8s networking issues will also trigger cron alerts as we ensure k8s network operates normally before sending out heartbeats
- Here is a checklist for setup a new type of cron alert:
    - Build a new specific cron image based off `cron_base` image. Put specific cron tasks into a file called `crontab` next to `Dockerfile`, it will automatically be loaded by onbuild steps in cron base image. Cron heartbeats should just work.
    - Add a new chart in stackdriver to look for custom metrics with the metric type matching the cron stat name; setup absence alert for that.

## Stackdriver Setup for Cron Alerts

### Dashboard
- Create a new dashboard called "Cron Dashboard"
- Add a chart for each type of cron that's monitored, with following options:
    - Title: the type of the cron, e.g. "API Cron"
    - Resource Type: "Custom Metrics"
    - Metric: select appropriate option based on the cron type from the prepopulated list, e.g. "cron/api_cron"
    - Chart Type: "stacked area"

### Alerting
- Add a new alerting policy for each type of cron that's monitored, with following options:
    - Conditions: Metric Absence on Custom Metrics
    - Violates when the metric (e.g. "cron/log_rotator") is absent for greater than 10 minutes
    - Notifications: send notifications to the designated email(s) when violations occur
    - Documention: (optional)
    - Name: name the alert with cron type
