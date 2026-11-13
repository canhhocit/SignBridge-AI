package com.signbridge.backend.ai;

import com.signbridge.backend.common.ContextType;

public record SummarizeAiInput(ContextType context, String transcript, String previousOutgoing) {
}
