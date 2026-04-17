package com.example.serviceb;

public record EchoPayload(
    String service,
    String userId,
    String message,
    long timestamp
) {
}

