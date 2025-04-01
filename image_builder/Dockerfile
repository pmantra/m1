FROM docker:19.03.8

RUN wget -O /klar https://github.com/optiopay/klar/releases/download/v2.4.0/klar-2.4.0-linux-amd64 \
 && chmod +x /klar \
 && apk add --no-cache 'git=~2.24'

COPY ./klar_whitelist.yaml /klar_whitelist.yaml

ARG STAGED_BUILDER_IMAGE

COPY "${STAGED_BUILDER_IMAGE}" /images/

ARG STAGED_GCLOUD_IMAGE

COPY "${STAGED_GCLOUD_IMAGE}" /images/

ARG STAGED_NODE_IMAGE

COPY "${STAGED_NODE_IMAGE}" /images/
