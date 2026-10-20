package com.example.serviceb;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

class DemoControllerTest {

    private MockMvc mvc;

    @BeforeEach
    void setUp() {
        mvc = MockMvcBuilders.standaloneSetup(new DemoController())
            .setControllerAdvice(new ApiExceptionHandler())
            .addFilters(new SecurityHeadersFilter())
            .build();
    }

    @Test
    void echoReturnsUserAndMessage() throws Exception {
        mvc.perform(get("/api/backend/echo").param("message", "hi").header("x-user-id", "bob"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.service").value("service-b"))
            .andExpect(jsonPath("$.userId").value("bob"))
            .andExpect(jsonPath("$.message").value("hi"));
    }

    @Test
    void missingUserHeaderIsJson400() throws Exception {
        mvc.perform(get("/api/backend/echo"))
            .andExpect(status().isBadRequest())
            .andExpect(jsonPath("$.error").value("missing required header: x-user-id"));
    }

    @Test
    void oversizedUserIdIsRejected() throws Exception {
        mvc.perform(get("/api/backend/echo").header("x-user-id", "a".repeat(65)))
            .andExpect(status().isBadRequest());
    }

    @Test
    void illegalUserIdCharactersAreRejected() throws Exception {
        mvc.perform(get("/api/backend/echo").header("x-user-id", "bo b"))
            .andExpect(status().isBadRequest());
    }

    @Test
    void oversizedMessageIsRejected() throws Exception {
        mvc.perform(get("/api/backend/echo").param("message", "m".repeat(201)).header("x-user-id", "u"))
            .andExpect(status().isBadRequest());
    }

    @Test
    void responsesCarrySecurityHeaders() throws Exception {
        mvc.perform(get("/api/backend/echo").header("x-user-id", "u"))
            .andExpect(header().string("X-Content-Type-Options", "nosniff"))
            .andExpect(header().string("Cache-Control", "no-store"));
    }
}
