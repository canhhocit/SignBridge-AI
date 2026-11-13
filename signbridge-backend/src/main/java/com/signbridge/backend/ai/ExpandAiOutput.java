package com.signbridge.backend.ai;

import com.fasterxml.jackson.annotation.JsonProperty;

/** Output EXPAND — cũng là response 200 của POST /api/expand. */
public record ExpandAiOutput(@JsonProperty("spoken_sentence") String spokenSentence) {
}
