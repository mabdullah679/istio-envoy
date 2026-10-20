package com.example.servicea;

import static org.springframework.test.web.client.match.MockRestRequestMatchers.header;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withStatus;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.io.IOException;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.client.RestClient;

class DemoControllerTest {

    private MockRestServiceServer downstream;
    private MockMvc mvc;

    @BeforeEach
    void setUp() {
        RestClient.Builder builder = RestClient.builder().baseUrl("http://service-b");
        downstream = MockRestServiceServer.bindTo(builder).build();
        mvc = MockMvcBuilders.standaloneSetup(new DemoController(builder.build()))
            .setControllerAdvice(new ApiExceptionHandler())
            .addFilters(new SecurityHeadersFilter())
            .build();
    }

    @Test
    void helloEchoesUserAndMessage() throws Exception {
        mvc.perform(get("/api/public/hello").param("message", "hi").header("x-user-id", "alice"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.service").value("service-a"))
            .andExpect(jsonPath("$.userId").value("alice"))
            .andExpect(jsonPath("$.message").value("hi"));
    }

    @Test
    void missingUserHeaderIsJson400() throws Exception {
        mvc.perform(get("/api/public/hello"))
            .andExpect(status().isBadRequest())
            .andExpect(jsonPath("$.error").value("missing required header: x-user-id"));
    }

    @Test
    void oversizedUserIdIsRejected() throws Exception {
        mvc.perform(get("/api/public/hello").header("x-user-id", "a".repeat(65)))
            .andExpect(status().isBadRequest());
    }

    @Test
    void userIdWithIllegalCharactersIsRejected() throws Exception {
        mvc.perform(get("/api/public/hello").header("x-user-id", "al ice;drop"))
            .andExpect(status().isBadRequest());
    }

    @Test
    void oversizedMessageIsRejected() throws Exception {
        mvc.perform(get("/api/public/hello").param("message", "m".repeat(201)).header("x-user-id", "u"))
            .andExpect(status().isBadRequest());
    }

    @Test
    void responsesCarrySecurityHeaders() throws Exception {
        mvc.perform(get("/api/public/hello").header("x-user-id", "u"))
            .andExpect(header().string("X-Content-Type-Options", "nosniff"))
            .andExpect(header().string("X-Frame-Options", "DENY"))
            .andExpect(header().string("Cache-Control", "no-store"));
    }

    @Test
    void relayForwardsUserIdAndReturnsDownstreamPayload() throws Exception {
        downstream.expect(requestTo("http://service-b/api/backend/echo?message=m"))
            .andExpect(header("x-user-id", "alice"))
            .andRespond(withSuccess(
                "{\"service\":\"service-b\",\"userId\":\"alice\",\"message\":\"m\",\"timestamp\":1}",
                MediaType.APPLICATION_JSON));

        mvc.perform(get("/api/public/relay").param("message", "m").header("x-user-id", "alice"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.downstream.service").value("service-b"))
            .andExpect(jsonPath("$.downstream.userId").value("alice"));
        downstream.verify();
    }

    @Test
    void relayEncodesMessageSoItCannotInjectQueryParameters() throws Exception {
        downstream.expect(requestTo("http://service-b/api/backend/echo?message=a%26user%3Dbob"))
            .andRespond(withSuccess(
                "{\"service\":\"service-b\",\"userId\":\"alice\",\"message\":\"a&user=bob\",\"timestamp\":1}",
                MediaType.APPLICATION_JSON));

        mvc.perform(get("/api/public/relay").param("message", "a&user=bob").header("x-user-id", "alice"))
            .andExpect(status().isOk());
        downstream.verify();
    }

    @Test
    void downstreamRateLimitIsPropagatedAs429() throws Exception {
        downstream.expect(requestTo("http://service-b/api/backend/echo?message=m"))
            .andRespond(withStatus(HttpStatus.TOO_MANY_REQUESTS));

        mvc.perform(get("/api/public/relay").param("message", "m").header("x-user-id", "alice"))
            .andExpect(status().isTooManyRequests())
            .andExpect(jsonPath("$.status").value(429));
    }

    @Test
    void downstreamServerErrorBecomes502() throws Exception {
        downstream.expect(requestTo("http://service-b/api/backend/echo?message=m"))
            .andRespond(withStatus(HttpStatus.INTERNAL_SERVER_ERROR));

        mvc.perform(get("/api/public/relay").param("message", "m").header("x-user-id", "alice"))
            .andExpect(status().isBadGateway());
    }

    @Test
    void downstreamTimeoutBecomes504() throws Exception {
        downstream.expect(requestTo("http://service-b/api/backend/echo?message=m"))
            .andRespond(request -> {
                throw new IOException("read timed out");
            });

        mvc.perform(get("/api/public/relay").param("message", "m").header("x-user-id", "alice"))
            .andExpect(status().isGatewayTimeout());
    }
}
