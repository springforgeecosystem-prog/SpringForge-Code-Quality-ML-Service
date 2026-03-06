"""
test_gemini_direct.py
Run from your ML service directory:
    python test_gemini_direct.py
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

KEY   = os.getenv("GEMINI_API_KEY", "")
MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
URL   = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"

print(f"Key set    : {bool(KEY)}")
print(f"Key prefix : {KEY[:12]}...")
print(f"Model      : {MODEL}")
print(f"URL        : {URL}")
print()

# ── Test 1: minimal prompt ──────────────────────────────────────────────
print("=" * 60)
print("TEST 1 — minimal prompt")
print("=" * 60)
payload = {
    "contents": [{"parts": [{"text": "Say hello in one word."}]}],
    "generationConfig": {"maxOutputTokens": 50, "temperature": 0.1}
}
try:
    r = requests.post(f"{URL}?key={KEY}", json=payload, timeout=30)
    print(f"HTTP status : {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        print(f"Response    : {text}")
        print("✅ TEST 1 PASSED — Gemini is reachable")
    else:
        print(f"❌ TEST 1 FAILED")
        print(f"Error body  : {r.text[:600]}")
except Exception as e:
    print(f"❌ Exception: {e}")

print()

# ── Test 2: exact prompt format used by fix service ────────────────────
print("=" * 60)
print("TEST 2 — fix service prompt format")
print("=" * 60)
prompt = """You are a senior Spring Boot architect reviewing a layered architecture project.

Anti-pattern: Layer Skip (Controller→Repository)
Architecture: layered
Affected layer: controller
Severity: CRITICAL
Files affected:
  - UserController.java
Problem: Controller directly injects Repository, bypassing Service layer.

Write a concise fix suggestion using EXACTLY this format:

💡 RECOMMENDATION:
<2 sentences specific to the architecture and files listed above>

🔧 EXAMPLE FIX:
// ❌ BEFORE
<short problematic code>

// ✅ AFTER
<short corrected code>

⭐ EXTRA TIPS:
• <tip 1 specific to layered architecture>
• <tip 2 specific to layered architecture>"""

payload2 = {
    "contents": [{"parts": [{"text": prompt}]}],
    "generationConfig": {
        "temperature": 0.3,
        "maxOutputTokens": 2048,
        "topP": 0.8,
    }
}
try:
    r2 = requests.post(f"{URL}?key={KEY}", json=payload2, timeout=45)
    print(f"HTTP status : {r2.status_code}")
    if r2.status_code == 200:
        data2  = r2.json()
        parts2 = data2["candidates"][0]["content"]["parts"]
        text2  = parts2[0]["text"].strip() if parts2 else ""
        print(f"Response length : {len(text2)} chars")
        print(f"Preview         : {text2[:300]}...")
        print("✅ TEST 2 PASSED — fix prompt works")
    else:
        print(f"❌ TEST 2 FAILED")
        print(f"Error body : {r2.text[:600]}")
except Exception as e:
    print(f"❌ Exception: {e}")

print()

# ── Test 3: simulate exactly what generate_fix_suggestion() does ───────
print("=" * 60)
print("TEST 3 — simulate generate_fix_suggestion()")
print("=" * 60)
try:
    import sys
    sys.path.insert(0, ".")
    from app.gemini_fix_service import generate_fix_suggestion

    result = generate_fix_suggestion(
        anti_pattern = "layer_skip_in_layered",
        files        = ["UserController.java"],
        architecture = "layered",
        layer        = "controller",
        severity     = "CRITICAL",
        description  = "Controller directly injects Repository, bypassing Service layer.",
        use_gemini   = True,
    )
    print(f"ai_powered  : {result['ai_powered']}")
    print(f"gemini_fix  : {result['gemini_fix'][:300] if result['gemini_fix'] else '(empty)'}")
    if result["ai_powered"]:
        print("✅ TEST 3 PASSED — generate_fix_suggestion works end-to-end")
    else:
        print("❌ TEST 3 FAILED — ai_powered is False")
        print("   → gemini_fix is empty, Gemini call silently failed")
        print("   → Check the [Gemini] log lines above for HTTP status")
except Exception as ex:
    print(f"❌ Exception in TEST 3: {ex}")
    import traceback; traceback.print_exc()

print()
print("=" * 60)
print("Done. Share the full output above.")
print("=" * 60)