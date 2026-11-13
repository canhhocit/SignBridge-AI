package com.signbridge.backend.ai;

import com.signbridge.backend.common.ContextType;

import java.util.List;

public record ExpandAiInput(ContextType context, List<String> chips, String previousIncoming) {
}
