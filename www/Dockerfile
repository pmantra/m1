FROM node:14.19.0 as build

COPY . .

RUN npm ci --prefer-offline --no-audit && npm run gulp

# previously were mounted on the node build container but then omitted from the buildcontext via dockerignore
RUN rm -r static/sass && rm static/js/mvnApp/**/*.js

FROM nginx:1.17 as release

# Update to address libexpat vulnerability
RUN apt-get update && apt-get upgrade -y && apt-get clean

COPY --from=build ./nginx.conf /etc/nginx/nginx.conf
COPY --from=build ./static /static

RUN chown -R www-data:www-data /static \
 && chmod -R 0555 /static

WORKDIR /static

CMD ["nginx", "-c", "/etc/nginx/nginx.conf"]
