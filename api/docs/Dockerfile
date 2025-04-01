FROM node:13.0-buster-slim
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
# install...
#   watch for the preview server &&
#   gsutil for uploading rendered documentation to GCS &&
#   aglio for rendering api blueprint source files into html
RUN apt-get update && apt-get install -y --no-install-recommends watch apt-transport-https ca-certificates \
 && curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | apt-key --keyring /usr/share/keyrings/cloud.google.gpg add - \
 && echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" | tee -a /etc/apt/sources.list.d/google-cloud-sdk.list \
 && apt-get update && apt-get install -y --no-install-recommends google-cloud-sdk \
 && rm -rf /var/lib/apt/lists/* \
 && npm install --global --unsafe-perm aglio@2.3.0

# This image is intended to be used in two distinct contexts:
#
# 1) As a service run on a local k8s cluster for previewing documentation changes in real time.
# 2) As the image for a pipeline job that renders and uploads api documenation to GCS.
