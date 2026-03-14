FROM --platform=$BUILDPLATFORM gradle:9.3.1-jdk25-alpine AS build
ARG RELEASE_MODE
ARG APP_VERSION
WORKDIR /usr/app
COPY service-api /usr/app
RUN sed -i "/alias(libs.plugins.owasp.dependencycheck)/d" build.gradle \
    && sed -i "/alias(libs.plugins.drill.integration)/d" build.gradle \
    && sed -i "/alias(libs.plugins.openapi.generator)/d" build.gradle \
    && sed -i "/alias(libs.plugins.jooq.codegen)/d" build.gradle \
    && sed -i "/import org.owasp.dependencycheck.reporting.ReportGenerator/d" build.gradle \
    && sed -i "/^dependencyCheck {$/,/^}$/d" build.gradle \
    && sed -i "/^drill {$/,/^}$/d" build.gradle \
    && sed -i "/^openApiGenerate {$/,/^}$/d" build.gradle \
    && sed -i "/jooqCodegen(.*)/d" build.gradle \
    && sed -i "/compileJava\\.dependsOn tasks.named('openApiGenerate')/d" build.gradle \
    && sed -i "/compileJava\\.dependsOn tasks.named('downloadManifestSchema')/d" build.gradle
RUN if [ "${RELEASE_MODE}" = true ]; then \
    gradle build --no-build-cache --exclude-task test \
        -PreleaseMode=true \
        -Dorg.gradle.project.version=${APP_VERSION}; \
    else gradle build --no-build-cache --exclude-task test -Dorg.gradle.project.version=${APP_VERSION}; fi

FROM amazoncorretto:25.0.2
LABEL version=${APP_VERSION} description="EPAM Report portal. Main API Service" maintainer="Andrei Varabyeu <andrei_varabyeu@epam.com>, Hleb Kanonik <hleb_kanonik@epam.com>"
ARG APP_VERSION=${APP_VERSION}
ENV APP_DIR=/usr/app
ENV JAVA_OPTS="-Xmx1g -XX:+UseG1GC -XX:InitiatingHeapOccupancyPercent=70 -Djava.security.egd=file:/dev/./urandom "
WORKDIR $APP_DIR
COPY --from=build $APP_DIR/build/libs/service-api-*exec.jar .
EXPOSE 8080
ENTRYPOINT ["sh", "-c", "java ${JAVA_OPTS} -jar ${APP_DIR}/service-api-*exec.jar"]
