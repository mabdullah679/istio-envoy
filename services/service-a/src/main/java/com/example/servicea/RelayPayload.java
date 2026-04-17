package com.example.servicea;

public record RelayPayload(
    String service,
    String userId,
    String message,
    EchoPayload downstream,
    long timestamp
) {
}

