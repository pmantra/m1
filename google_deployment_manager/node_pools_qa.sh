#!/bin/bash

CLUSTER="$1"
ZONE="us-central1-b"
tag=$(date +%s)

echo "Node Pools $tag creating for $CLUSTER/$ZONE at $(date +%d-%m-%y/%H:%M:%S)"

gcloud container node-pools create stateless-pool-"$tag" --cluster="$CLUSTER" --zone="$ZONE" --num-nodes=2 --machine-type=n1-standard-1 --image-type=gci --no-enable-cloud-endpoints  --node-labels=maven-node-type=stateless --scopes https://www.googleapis.com/auth/logging.write,https://www.googleapis.com/auth/monitoring.write,https://www.googleapis.com/auth/sqlservice.admin,storage-ro,https://www.googleapis.com/auth/trace.append

gcloud container node-pools create admin-support-pool-"$tag" --cluster="$CLUSTER" --zone="$ZONE" --num-nodes=1 --machine-type=g1-small --image-type=gci --no-enable-cloud-endpoints  --node-labels=maven-node-type=admin-support --scopes https://www.googleapis.com/auth/logging.write,https://www.googleapis.com/auth/monitoring.write,storage-ro,https://www.googleapis.com/auth/trace.append

gcloud container node-pools create stateless-dataprocess-pool-"$tag" --cluster="$CLUSTER" --zone="$ZONE" --num-nodes=1 --machine-type=g1-small --image-type=gci --no-enable-cloud-endpoints --node-labels=maven-node-type=stateless-dataprocess --scopes https://www.googleapis.com/auth/logging.write,https://www.googleapis.com/auth/monitoring.write,https://www.googleapis.com/auth/sqlservice.admin,https://www.googleapis.com/auth/bigquery,https://www.googleapis.com/auth/devstorage.read_write,storage-ro,https://www.googleapis.com/auth/trace.append

gcloud container node-pools create cron-pool-"$tag" --cluster="$CLUSTER" --zone="$ZONE" --image-type=gci  --num-nodes=1 --machine-type=g1-small --node-labels=maven-node-type=cron --no-enable-cloud-endpoints --scopes https://www.googleapis.com/auth/logging.write,https://www.googleapis.com/auth/monitoring.write,https://www.googleapis.com/auth/sqlservice.admin,storage-ro,https://www.googleapis.com/auth/trace.append

gcloud container node-pools create cache-pool-"$tag" --cluster="$CLUSTER" --zone="$ZONE" --num-nodes=1 --machine-type=g1-small --image-type=gci --no-enable-cloud-endpoints --node-labels=maven-node-type=cache-support --scopes https://www.googleapis.com/auth/logging.write,https://www.googleapis.com/auth/monitoring.write,storage-ro,https://www.googleapis.com/auth/trace.append

gcloud container node-pools create support-pool-"$tag" --cluster="$CLUSTER" --zone="$ZONE" --image-type=gci  --num-nodes=1 --machine-type=g1-small --node-labels=maven-node-type=logging-support --no-enable-cloud-endpoints --scopes https://www.googleapis.com/auth/logging.write,https://www.googleapis.com/auth/monitoring.write,https://www.googleapis.com/auth/bigquery,storage-full,https://www.googleapis.com/auth/trace.append

gcloud container node-pools create stateless-worker-pool-"$tag" --cluster="$CLUSTER" --zone="$ZONE" --num-nodes=1 --machine-type=g1-small --image-type=gci --no-enable-cloud-endpoints --node-labels=maven-node-type=stateless-worker --scopes https://www.googleapis.com/auth/logging.write,https://www.googleapis.com/auth/monitoring.write,https://www.googleapis.com/auth/bigquery,https://www.googleapis.com/auth/sqlservice.admin,storage-full,https://www.googleapis.com/auth/trace.append

echo "All Set at $(date +%d-%m-%y/%H:%M:%S)"

