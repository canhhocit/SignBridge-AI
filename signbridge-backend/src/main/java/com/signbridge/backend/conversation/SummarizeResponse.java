package com.signbridge.backend.conversation;

import com.signbridge.backend.ai.Highlight;
import com.signbridge.backend.ai.IconCode;

import java.util.List;

/** Response 200 của POST /api/summarize (mục 4.4). */
public record SummarizeResponse(
        String transcript,
        String summary,
        List<Highlight> highlights,
        IconCode iconCode,
        List<String> quickReplies) {
}
