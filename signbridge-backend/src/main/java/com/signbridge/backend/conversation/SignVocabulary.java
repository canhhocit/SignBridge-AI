package com.signbridge.backend.conversation;

import com.signbridge.backend.common.ContextType;

import java.util.ArrayList;
import java.util.List;

/** Bộ 20 ký hiệu demo (mục 7.1) và danh sách gửi cho AI theo ngữ cảnh (mục 7.2). */
public final class SignVocabulary {

    public static final String UNKNOWN = "UNKNOWN";

    private static final List<String> COMMON =
            List.of("XIN CHÀO", "CẢM ƠN", "CÓ", "KHÔNG", "THANH TOÁN", "BAO NHIÊU");
    private static final List<String> NUMBER_TIME = List.of("MỘT", "HAI", "NGÀY");
    private static final List<String> PHARMACY = List.of("ĐAU", "ĐẦU", "BỤNG", "SỐT", "THUỐC", "MUA");
    private static final List<String> CAFE = List.of("MUA", "CÀ PHÊ", "ĐÁ", "MANG ĐI");
    private static final List<String> PUBLIC = List.of("GIẤY TỜ", "Ở ĐÂU");

    private SignVocabulary() {
    }

    public static List<String> allowedFor(ContextType context) {
        List<String> result = new ArrayList<>(COMMON);
        result.addAll(NUMBER_TIME);
        switch (context) {
            case PHARMACY -> result.addAll(PHARMACY);
            case CAFE -> result.addAll(CAFE);
            case PUBLIC -> result.addAll(PUBLIC);
            case CUSTOM -> {
                result.addAll(PHARMACY);
                CAFE.stream().filter(g -> !result.contains(g)).forEach(result::add);
                result.addAll(PUBLIC);
            }
        }
        return List.copyOf(result);
    }
}
