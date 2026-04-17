FROM maven:3.9.11-eclipse-temurin-25 AS build
WORKDIR /workspace
COPY pom.xml pom.xml
COPY services/service-a/pom.xml services/service-a/pom.xml
COPY services/service-b/pom.xml services/service-b/pom.xml
RUN mvn -q -pl services/service-b -am dependency:go-offline
COPY services/service-b/src services/service-b/src
RUN mvn -q -pl services/service-b -am package -DskipTests

FROM eclipse-temurin:25-jre
WORKDIR /app
COPY --from=build /workspace/services/service-b/target/service-b-0.0.1-SNAPSHOT.jar app.jar
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "/app/app.jar"]
