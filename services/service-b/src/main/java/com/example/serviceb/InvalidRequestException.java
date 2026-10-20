package com.example.serviceb;

/** Raised when a caller-supplied value fails validation; mapped to HTTP 400. */
public class InvalidRequestException extends RuntimeException {

    public InvalidRequestException(String message) {
        super(message);
    }
}
