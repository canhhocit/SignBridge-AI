package com.signbridge.backend.api;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.request.MockMultipartHttpServletRequestBuilder;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.context.WebApplicationContext;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.multipart;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
class ApiControllerTest {

    @Autowired
    WebApplicationContext ctx;
    MockMvc mvc;

    @BeforeEach
    void setUp() {
        mvc = MockMvcBuilders.webAppContextSetup(ctx).build();
    }

    private static MockMultipartFile frame() {
        return new MockMultipartFile("frames", "f.jpg", MediaType.IMAGE_JPEG_VALUE, new byte[]{1, 2, 3});
    }

    private static MockMultipartHttpServletRequestBuilder signWithFrames(int n) {
        MockMultipartHttpServletRequestBuilder b = multipart("/api/sign");
        for (int i = 0; i < n; i++) {
            b.file(frame());
        }
        return b;
    }

    @Test
    void health() throws Exception {
        mvc.perform(get("/api/health"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("UP"));
    }

    @Test
    void signReturnsSentence() throws Exception {
        mvc.perform(signWithFrames(4).param("context", "PHARMACY")
                        .param("personalChips", "[\"Dị ứng penicillin\"]"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.glosses[0]").value("ĐAU"))
                .andExpect(jsonPath("$.spoken_sentence").value("Chào bạn, mình bị đau đầu, muốn mua thuốc."))
                .andExpect(jsonPath("$.suggestedChips.length()").value(3));
    }

    @Test
    void signLowConfidenceHasEmptySentence() throws Exception {
        mvc.perform(signWithFrames(8).param("context", "PHARMACY").param("personalChips", "[\"MOCK_LOW\"]"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.glosses[0]").value("UNKNOWN"))
                .andExpect(jsonPath("$.spoken_sentence").value(""));
    }

    @Test
    void signRejectsWrongFrameCount() throws Exception {
        mvc.perform(signWithFrames(3).param("context", "CAFE"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error.code").value("INVALID_REQUEST"));
    }

    @Test
    void signRejectsUnknownContext() throws Exception {
        mvc.perform(signWithFrames(4).param("context", "BAR"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error.code").value("INVALID_REQUEST"));
    }

    @Test
    void signRejectsPng() throws Exception {
        mvc.perform(multipart("/api/sign")
                        .file(new MockMultipartFile("frames", "f.png", MediaType.IMAGE_PNG_VALUE, new byte[]{1}))
                        .file(frame()).file(frame()).file(frame())
                        .param("context", "CAFE"))
                .andExpect(status().isUnsupportedMediaType())
                .andExpect(jsonPath("$.error.code").value("UNSUPPORTED_MEDIA_TYPE"));
    }

    @Test
    void expandReturnsSentence() throws Exception {
        mvc.perform(post("/api/expand").contentType(MediaType.APPLICATION_JSON)
                        .content("{\"context\":\"PHARMACY\",\"chips\":[\"Đau đầu\",\"Không buồn ngủ\"]}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.spoken_sentence").isNotEmpty());
    }

    @Test
    void expandRejectsTooManyChips() throws Exception {
        mvc.perform(post("/api/expand").contentType(MediaType.APPLICATION_JSON)
                        .content("{\"context\":\"CAFE\",\"chips\":[\"a\",\"b\",\"c\",\"d\",\"e\",\"f\"]}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error.code").value("INVALID_REQUEST"));
    }

    @Test
    void expandRejectsBadEnum() throws Exception {
        mvc.perform(post("/api/expand").contentType(MediaType.APPLICATION_JSON)
                        .content("{\"context\":\"BAR\",\"chips\":[\"a\"]}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error.code").value("INVALID_REQUEST"));
    }

    @Test
    void summarizeReturnsSummary() throws Exception {
        mvc.perform(multipart("/api/summarize")
                        .file(new MockMultipartFile("audio", "a.m4a", "audio/m4a", new byte[]{1, 2}))
                        .param("context", "PHARMACY"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.summary").value("Panadol Xanh • 1 viên sau ăn • Ngày 2 lần • 35.000đ"))
                .andExpect(jsonPath("$.highlights.length()").value(3))
                .andExpect(jsonPath("$.iconCode").value("PILL"))
                .andExpect(jsonPath("$.quickReplies.length()").value(3))
                .andExpect(jsonPath("$.transcript").isNotEmpty());
    }

    @Test
    void summarizeRejectsWav() throws Exception {
        mvc.perform(multipart("/api/summarize")
                        .file(new MockMultipartFile("audio", "a.wav", "audio/wav", new byte[]{1}))
                        .param("context", "PHARMACY"))
                .andExpect(status().isUnsupportedMediaType());
    }
}
