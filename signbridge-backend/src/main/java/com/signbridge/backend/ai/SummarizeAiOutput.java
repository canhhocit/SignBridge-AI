package com.signbridge.backend.ai;

import java.util.List;

public record SummarizeAiOutput(
        String summary,
        List<Highlight> highlights,
        IconCode iconCode,
        List<String> quickReplies) {
}
