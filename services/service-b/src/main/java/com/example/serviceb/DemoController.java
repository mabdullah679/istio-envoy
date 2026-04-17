package com.example.serviceb;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class DemoController {

    private static final String USER_HEADER = "x-user-id";

    @GetMapping("/api/backend/echo")
    EchoPayload echo(
        @RequestHeader(name = USER_HEADER) String userId,
        @RequestParam(name = "message", defaultValue = "hello from service-b") String message
    ) {
        return new EchoPayload("service-b", userId, message, System.currentTimeMillis());
    }
}
