package com.signbridge.backend.ai;

public record Highlight(HighlightType type, String text) {

    public enum HighlightType { PRICE, COUNTER, DOSAGE, TIME, QUANTITY, OTHER }
}
