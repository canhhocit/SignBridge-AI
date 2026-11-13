package com.signbridge.backend.ai;

import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.List;

/** Output SIGN_RECOGNIZE — cũng là response 200 của POST /api/sign sau khi backend kiểm tra. */
public record SignAiOutput(
        List<String> glosses,
        double confidence,
        @JsonProperty("spoken_sentence") String spokenSentence,
        List<String> suggestedChips) {
}
