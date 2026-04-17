package com.example.servicea;

import org.springframework.http.HttpHeaders;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.client.RestClient;

@RestController
public class DemoController {

    private static final String USER_HEADER = "x-user-id";

    private final RestClient serviceBRestClient;

    public DemoController(RestClient serviceBRestClient) {
        this.serviceBRestClient = serviceBRestClient;
    }

    @GetMapping("/api/public/hello")
    EchoPayload hello(
        @RequestHeader(name = USER_HEADER) String userId,
        @RequestParam(name = "message", defaultValue = "hello from service-a") String message
    ) {
        return new EchoPayload("service-a", userId, message, System.currentTimeMillis());
    }

    @GetMapping("/api/public/relay")
    RelayPayload relay(
        @RequestHeader(name = USER_HEADER) String userId,
        @RequestParam(name = "message", defaultValue = "relay from service-a") String message
    ) {
        EchoPayload downstream = serviceBRestClient.get()
            .uri(uriBuilder -> uriBuilder.path("/api/backend/echo")
                .queryParam("message", message)
                .build())
            .header(HttpHeaders.ACCEPT, "application/json")
            .header(USER_HEADER, userId)
            .retrieve()
            .body(EchoPayload.class);

        return new RelayPayload("service-a", userId, message, downstream, System.currentTimeMillis());
    }
}
