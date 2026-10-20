package com.example.servicea;

import java.util.Map;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.HttpStatusCode;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.MissingRequestHeaderException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClientResponseException;

@RestControllerAdvice
public class ApiExceptionHandler {

    private static final Logger log = LoggerFactory.getLogger(ApiExceptionHandler.class);

    @ExceptionHandler(InvalidRequestException.class)
    ResponseEntity<Map<String, Object>> invalid(InvalidRequestException ex) {
        return body(HttpStatus.BAD_REQUEST, ex.getMessage());
    }

    @ExceptionHandler(MissingRequestHeaderException.class)
    ResponseEntity<Map<String, Object>> missingHeader(MissingRequestHeaderException ex) {
        return body(HttpStatus.BAD_REQUEST, "missing required header: " + ex.getHeaderName());
    }

    /** service-b (or its sidecar) answered with an error status. 429 is passed through so callers can back off. */
    @ExceptionHandler(RestClientResponseException.class)
    ResponseEntity<Map<String, Object>> downstreamStatus(RestClientResponseException ex) {
        HttpStatusCode status = ex.getStatusCode();
        log.warn("service-b returned {}", status.value());
        if (status.value() == HttpStatus.TOO_MANY_REQUESTS.value()) {
            return body(HttpStatus.TOO_MANY_REQUESTS, "rate limited by downstream hop");
        }
        return body(HttpStatus.BAD_GATEWAY, "service-b returned " + status.value());
    }

    /** Connect/read failures and timeouts talking to service-b. */
    @ExceptionHandler(ResourceAccessException.class)
    ResponseEntity<Map<String, Object>> downstreamUnavailable(ResourceAccessException ex) {
        log.warn("service-b unreachable: {}", ex.getMessage());
        return body(HttpStatus.GATEWAY_TIMEOUT, "service-b unreachable or timed out");
    }

    private static ResponseEntity<Map<String, Object>> body(HttpStatus status, String message) {
        return ResponseEntity.status(status).body(Map.of("status", status.value(), "error", message));
    }
}
