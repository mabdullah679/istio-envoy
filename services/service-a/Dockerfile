FROM maven:3.9.11-eclipse-temurin-25 AS build
WORKDIR /workspace
COPY pom.xml pom.xml
COPY services/service-a/pom.xml services/service-a/pom.xml
COPY services/service-b/pom.xml services/service-b/pom.xml
RUN mvn -q -pl services/service-a -am dependency:go-offline
COPY services/service-a/src services/service-a/src
RUN mvn -q -pl services/service-a -am package -DskipTests

FROM eclipse-temurin:25-jre
RUN groupadd --gid 10001 app && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin app
WORKDIR /app
COPY --from=build --chown=10001:10001 /workspace/services/service-a/target/service-a-0.0.1-SNAPSHOT.jar app.jar
USER 10001:10001
EXPOSE 8080
ENV JAVA_TOOL_OPTIONS="-XX:MaxRAMPercentage=70 -XX:+ExitOnOutOfMemoryError"
ENTRYPOINT ["java", "-jar", "/app/app.jar"]
