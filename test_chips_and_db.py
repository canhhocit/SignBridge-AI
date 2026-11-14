import sys
import json
from fastapi.testclient import TestClient

from app import app, DB_AVAILABLE

def test_signbridge_postgres_and_chips():
    print(f"[*] DB_AVAILABLE: {DB_AVAILABLE}")
    assert DB_AVAILABLE, "PostgreSQL Database must be available!"

    client = TestClient(app)

    # 1. Health check
    res_health = client.get("/api/health")
    print(f"[1] Health Check: {res_health.status_code} - {res_health.json()}")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "UP"
    assert res_health.json()["database"] == "PostgreSQL"

    # 2. Get chips for user A (System chips only initially)
    user_a = "user_alpha_test_1"
    user_b = "user_beta_test_2"

    res_chips_a = client.get("/api/v1/chips?context=CAFE", headers={"X-User-Id": user_a})
    assert res_chips_a.status_code == 200
    chips_a_initial = res_chips_a.json()
    print(f"[2] User A initial chips count for CAFE: {len(chips_a_initial)}")
    assert len(chips_a_initial) > 0
    assert all(c["is_system"] is True for c in chips_a_initial)

    # 3. User A creates a custom chip
    custom_chip_payload = {
        "text": "Trà sữa trần châu hoàng kim",
        "context": "CAFE"
    }
    res_create = client.post("/api/v1/chips", json=custom_chip_payload, headers={"X-User-Id": user_a})
    assert res_create.status_code == 200
    created_chip = res_create.json()
    print(f"[3] Created chip for User A: {created_chip}")
    assert created_chip["text"] == "Trà sữa trần châu hoàng kim"
    assert created_chip["is_system"] is False
    assert created_chip["user_id"] == user_a
    chip_id = created_chip["id"]

    # 4. User B checks chips: MUST NOT see User A's chip! (Multi-tenancy isolation check)
    res_chips_b = client.get("/api/v1/chips?context=CAFE", headers={"X-User-Id": user_b})
    assert res_chips_b.status_code == 200
    chips_b = res_chips_b.json()
    user_b_chip_texts = [c["text"] for c in chips_b]
    print(f"[4] User B chip texts: {user_b_chip_texts}")
    assert "Trà sữa trần châu hoàng kim" not in user_b_chip_texts, "LEAKAGE: User B saw User A's private chip!"
    print("[+] SUCCESS: Data isolation verified! User B cannot see User A's custom chips.")

    # 5. User A checks chips: MUST see the custom chip
    res_chips_a_after = client.get("/api/v1/chips?context=CAFE", headers={"X-User-Id": user_a})
    chips_a_texts = [c["text"] for c in res_chips_a_after.json()]
    assert "Trà sữa trần châu hoàng kim" in chips_a_texts
    print(f"[5] User A verified seeing own custom chip.")

    # 6. Test AI Suggest Chips endpoint
    suggest_req = {
        "context": "CAFE",
        "recentText": "Quán em có trà đào cam sả và trà sen vàng",
        "existingChips": ["Trà sữa trân châu", "Cà phê đá"]
    }
    res_suggest = client.post("/api/v1/ai/suggest-chips", json=suggest_req)
    assert res_suggest.status_code == 200
    suggested = res_suggest.json().get("suggestedChips", [])
    print(f"[6] AI suggested chips: {suggested}")
    assert len(suggested) > 0

    # 7. User A deletes the custom chip
    res_delete = client.delete(f"/api/v1/chips/{chip_id}", headers={"X-User-Id": user_a})
    assert res_delete.status_code == 200
    assert res_delete.json()["success"] is True

    # 8. User A verifies chip was deleted
    res_chips_a_final = client.get("/api/v1/chips?context=CAFE", headers={"X-User-Id": user_a})
    chips_a_final_texts = [c["text"] for c in res_chips_a_final.json()]
    assert "Trà sữa trần châu hoàng kim" not in chips_a_final_texts
    print(f"[8] User A verified deletion successful.")

    # 9. Verify Web UI index page serves 200 OK
    res_ui = client.get("/")
    assert res_ui.status_code == 200
    assert "SignBridge AI Studio" in res_ui.text
    assert "mode-chip-btn" in res_ui.text
    print(f"[9] Web UI rendered successfully with mode-chip-btn fix.")

    print("\n[🎉] ALL TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_signbridge_postgres_and_chips()
