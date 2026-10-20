package com.example.servicea;

import java.util.regex.Pattern;

/** Validates caller-controlled inputs before they are echoed or forwarded. */
final class RequestValidator {

    static final int MAX_MESSAGE_LENGTH = 200;
    private static final Pattern USER_ID = Pattern.compile("^[A-Za-z0-9._@:-]{1,64}$");

    private RequestValidator() {
    }

    static String userId(String value) {
        if (value == null || !USER_ID.matcher(value).matches()) {
            throw new InvalidRequestException("x-user-id must match [A-Za-z0-9._@:-]{1,64}");
        }
        return value;
    }

    static String message(String value) {
        if (value.length() > MAX_MESSAGE_LENGTH) {
            throw new InvalidRequestException("message must be at most " + MAX_MESSAGE_LENGTH + " characters");
        }
        return value;
    }
}
