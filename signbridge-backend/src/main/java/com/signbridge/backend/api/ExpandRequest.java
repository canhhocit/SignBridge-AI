package com.signbridge.backend.api;

import com.signbridge.backend.common.ContextType;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

import java.util.List;

public record ExpandRequest(
        @NotNull ContextType context,
        @NotNull @Size(min = 1, max = 5) List<@NotBlank @Size(max = 50) String> chips,
        @Size(max = 300) String previousIncoming) {
}
