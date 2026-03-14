FROM alpine:3.20.3 AS generate-build-info
RUN mkdir -p /usr/src/app/build
WORKDIR /usr/src
ARG APP_VERSION=develop
ARG BUILD_BRANCH
ARG BUILD_DATE
RUN echo {\"build\": { \"version\": \"${APP_VERSION}\", \"branch\": \"${BUILD_BRANCH}\", \"build_date\": \"${BUILD_DATE}\", \"name\": \"Service UI\", \"repo\": \"reportportal/service-ui\"}} > ./app/build/buildInfo.json

FROM node:20-bookworm AS build-frontend
RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app
COPY service-ui/app/ /usr/src/app/
RUN npm install --legacy-peer-deps
RUN export NODE_OPTIONS="--max-old-space-size=4096" && npm run build

FROM nginxinc/nginx-unprivileged:alpine

USER root

COPY --from=build-frontend /usr/src/app/build /usr/share/nginx/html
COPY --from=generate-build-info /usr/src/app/build /usr/share/nginx/html
COPY service-ui/config.template.json /usr/share/nginx/html/config.template.json

RUN rm /etc/nginx/conf.d/default.conf
COPY service-ui/nginx.conf /etc/nginx/nginx.conf

COPY service-ui/entrypoint.sh /entrypoint.sh
RUN sed -i 's/\r$//' /entrypoint.sh && chmod +x /entrypoint.sh && chown -R nginx:nginx /usr/share/nginx/html /entrypoint.sh

USER nginx

EXPOSE 8080

ENTRYPOINT ["/bin/sh", "/entrypoint.sh"]
