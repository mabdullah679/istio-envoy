package com.example.servicea;

public record EchoPayload(
    String service,
    String userId,
    String message,
    long timestamp
) {
}

