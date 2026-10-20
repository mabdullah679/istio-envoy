package com.example.serviceb;

import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.MissingRequestHeaderException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@RestControllerAdvice
public class ApiExceptionHandler {

    @ExceptionHandler(InvalidRequestException.class)
    ResponseEntity<Map<String, Object>> invalid(InvalidRequestException ex) {
        return body(ex.getMessage());
    }

    @ExceptionHandler(MissingRequestHeaderException.class)
    ResponseEntity<Map<String, Object>> missingHeader(MissingRequestHeaderException ex) {
        return body("missing required header: " + ex.getHeaderName());
    }

    private static ResponseEntity<Map<String, Object>> body(String message) {
        return ResponseEntity.status(HttpStatus.BAD_REQUEST)
            .body(Map.of("status", 400, "error", message));
    }
}
