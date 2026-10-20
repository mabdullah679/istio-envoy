package com.example.servicea;

import java.time.Duration;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.Bean;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.web.client.RestClient;

@SpringBootApplication
public class ServiceAApplication {

    public static void main(String[] args) {
        SpringApplication.run(ServiceAApplication.class, args);
    }

    @Bean
    RestClient serviceBRestClient(
        @Value("${service-b.base-url}") String baseUrl,
        @Value("${service-b.connect-timeout:2s}") Duration connectTimeout,
        @Value("${service-b.read-timeout:3s}") Duration readTimeout
    ) {
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(connectTimeout);
        factory.setReadTimeout(readTimeout);
        return RestClient.builder().baseUrl(baseUrl).requestFactory(factory).build();
    }
}
