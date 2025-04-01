FROM nginx:1.23.4-perl

# Set versions
ARG OPENTRACING_NGINX_VERSION="v0.32.0"
ARG DD_OPENTRACING_CPP_VERSION="v1.3.7"

# Update to address libexpat vulnerability
RUN apt-get update && apt-get upgrade -y && \
    apt-get install -yq --no-install-recommends wget ca-certificates  && apt-get clean

# Install Nginx OpenTracing and DataDog APM
# https://github.com/DataDog/dd-opentracing-cpp/blob/master/examples/nginx-tracing/
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
RUN NGINX_VERSION=$(nginx -v 2>&1 > /dev/null | sed -E "s/^.*nginx\/(.*)/\\1/") && \
    echo "versions(nginx: ${NGINX_VERSION}, opentracing-nginx: ${OPENTRACING_NGINX_VERSION}, dd-opentracing-plugin: ${DD_OPENTRACING_CPP_VERSION})" && \
    \
    # Install nginx-opentracing
    wget "https://github.com/opentracing-contrib/nginx-opentracing/releases/download/${OPENTRACING_NGINX_VERSION}/linux-amd64-nginx-${NGINX_VERSION}-ot16-ngx_http_module.so.tgz" && \
    NGINX_MODULES=$(nginx -V 2>&1 | grep "configure arguments" | sed -n 's/.*--modules-path=\([^ ]*\).*/\1/p') && \
    tar zxvf "linux-amd64-nginx-${NGINX_VERSION}-ot16-ngx_http_module.so.tgz" -C "${NGINX_MODULES}" && \
    # Install Datadog module
    wget -O - "https://github.com/DataDog/dd-opentracing-cpp/releases/download/${DD_OPENTRACING_CPP_VERSION}/linux-amd64-libdd_opentracing_plugin.so.gz" | gunzip -c > /usr/local/lib/libdd_opentracing_plugin.so


COPY ./config/ /etc/nginx/conf.d/
COPY ./test_tls/ /etc/nginx/test_tls/
COPY ./dd-config.json /etc/nginx/dd-config.json
