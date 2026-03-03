"""
test_gemini_fixes.py  — UPDATED
─────────────────────────────────────────────────────────────────────────────
Tests for the AI fix suggestion endpoints.
Now verifies the 'recommendation' field and prints Gemini diagnostics.
Run with:  python test_gemini_fixes.py
─────────────────────────────────────────────────────────────────────────────
"""

import requests
import json

BASE = "http://localhost:8081"


def sep(title=""):
    print(f"\n{'═'*65}")
    if title:
        print(f"  {title}")
    print('═'*65)


def print_fix(data: dict, show_code: bool = True):
    """Pretty-print a FixSuggestion dict."""
    print(f"Anti-Pattern : {data['anti_pattern']}")
    print(f"Layer        : {data['layer']}")
    print(f"Severity     : {data['severity']}")
    print(f"Impact       : {data['impact_points']} pts")
    print(f"AI Powered   : {data['ai_powered']}")

    print(f"\n📄 Files Affected ({len(data['files'])}):")
    for f in data['files'][:5]:
        print(f"   • {f}")

    print(f"\n📖 Problem:")
    print(f"   {data['problem']}")

    print(f"\n💡 Recommendation:")
    print(f"   {data['recommendation']}")      # ← always shown now

    if show_code and data.get('before_code'):
        print(f"\n🔧 Example Fix:")
        print(f"   // ❌ BEFORE")
        for line in data['before_code'].split('\n')[:8]:
            print(f"   {line}")
        print(f"\n   // ✅ AFTER")
        for line in data['after_code'].split('\n')[:8]:
            print(f"   {line}")

    if data.get('gemini_fix'):
        print(f"\n🤖 AI-Generated Fix (Gemini):")
        print("   " + "\n   ".join(data['gemini_fix'].split('\n')))
    else:
        print("\n⚠️  Gemini fix: not available")
        print("   → Check the uvicorn server console for [Gemini] diagnostic lines")


# ── Test 1: Single fix — no_validation ────────────────────────────────────
def test_single_fix_no_validation():
    sep("TEST 1: Single Fix — no_validation")
    payload = {
        "anti_pattern"        : "no_validation",
        "files"               : ["UserController.java", "OrderController.java", "ProductController.java"],
        "architecture_pattern": "layered",
        "affected_layer"      : "Controller",
        "severity"            : "MEDIUM",
        "description"         : "Controller endpoints accept @RequestBody without @Valid annotation"
    }
    r = requests.post(f"{BASE}/generate-fix", json=payload, timeout=30)
    if r.status_code != 200:
        print(f"❌ HTTP {r.status_code}: {r.text[:300]}")
        return
    print_fix(r.json())


# ── Test 2: Single fix — layer_skip ──────────────────────────────────────
def test_single_fix_layer_skip():
    sep("TEST 2: Single Fix — layer_skip_in_layered")
    payload = {
        "anti_pattern"        : "layer_skip_in_layered",
        "files"               : ["BookController.java"],
        "architecture_pattern": "layered",
        "affected_layer"      : "Controller",
        "severity"            : "HIGH",
        "description"         : "Controller directly injects Repository, bypassing Service layer"
    }
    r = requests.post(f"{BASE}/generate-fix", json=payload, timeout=30)
    if r.status_code != 200:
        print(f"❌ HTTP {r.status_code}: {r.text[:300]}")
        return
    data = r.json()
    print(f"Impact: {data['impact_points']} pts | AI: {data['ai_powered']}")
    print(f"\n💡 Recommendation:\n   {data['recommendation']}")
    if data.get('gemini_fix'):
        print(f"\n🤖 Gemini:\n{data['gemini_fix']}")


# ── Test 3: Single fix — missing_transaction ─────────────────────────────
def test_single_fix_missing_tx():
    sep("TEST 3: Single Fix — missing_transaction_in_layered")
    payload = {
        "anti_pattern"        : "missing_transaction_in_layered",
        "files"               : ["ProductService.java", "PaymentService.java"],
        "architecture_pattern": "layered",
        "affected_layer"      : "Service",
        "severity"            : "HIGH",
        "description"         : "Service methods write to DB without @Transactional"
    }
    r = requests.post(f"{BASE}/generate-fix", json=payload, timeout=30)
    if r.status_code != 200:
        print(f"❌ HTTP {r.status_code}: {r.text[:300]}")
        return
    data = r.json()
    print(f"Impact: {data['impact_points']} pts | AI: {data['ai_powered']}")
    print(f"\n💡 Recommendation:\n   {data['recommendation']}")


# ── Test 4: Full project fixes ───────────────────────────────────────────
def test_project_fixes():
    sep("TEST 4: Full Project Fix — /generate-fixes")
    payload = {
        "architecture_pattern": "layered",
        "anti_patterns": [
            {
                "type": "no_validation", "severity": "MEDIUM",
                "affected_layer": "Controller", "confidence": 0.91,
                "files": ["UserController.java", "OrderController.java"],
                "description": "Missing @Valid on @RequestBody",
                "recommendation": "Add @Valid annotation"
            },
            {
                "type": "layer_skip_in_layered", "severity": "HIGH",
                "affected_layer": "Controller", "confidence": 0.95,
                "files": ["BookController.java"],
                "description": "Controller directly accesses Repository",
                "recommendation": "Add Service layer"
            },
            {
                "type": "missing_transaction_in_layered", "severity": "HIGH",
                "affected_layer": "Service", "confidence": 0.88,
                "files": ["ProductService.java"],
                "description": "Data operations without @Transactional",
                "recommendation": "Add @Transactional"
            }
        ]
    }
    r = requests.post(f"{BASE}/generate-fixes", json=payload, timeout=60)
    if r.status_code != 200:
        print(f"❌ HTTP {r.status_code}: {r.text[:300]}")
        return
    data = r.json()
    print(f"Architecture : {data['architecture_pattern']}")
    print(f"Total Fixes  : {data['total_fixes']}")
    for s in data['suggestions']:
        print(f"\n  ── [{s['severity']}] {s['anti_pattern']}")
        print(f"     Impact      : {s['impact_points']} pts | AI: {s['ai_powered']}")
        print(f"     Files       : {', '.join(s['files'])}")
        print(f"     💡 Recommendation: {s['recommendation'][:100]}...")
        if s.get('gemini_fix'):
            print(f"     🤖 Gemini   : {s['gemini_fix'][:150]}...")


# ── Test 5: Full pipeline ─────────────────────────────────────────────────
def test_full_pipeline():
    sep("TEST 5: Full Pipeline — analyze then generate-fixes")
    files_payload = {
        "files": [
            {
                "file_name": "UserController.java",
                "file_path": "src/main/java/controller/UserController.java",
                "layer": "controller", "architecture_pattern": "layered",
                "architecture_confidence": 0.85,
                "loc": 280, "methods": 12, "classes": 1, "avg_cc": 3.5,
                "imports": 22, "annotations": 10,
                "controller_deps": 0, "service_deps": 1, "repository_deps": 2,
                "entity_deps": 0, "adapter_deps": 0, "port_deps": 0,
                "usecase_deps": 0, "gateway_deps": 0, "total_cross_layer_deps": 3,
                "has_business_logic": True, "has_data_access": False,
                "has_http_handling": True, "has_validation": False,
                "has_transaction": False, "violates_layer_separation": True
            },
            {
                "file_name": "OrderService.java",
                "file_path": "src/main/java/service/OrderService.java",
                "layer": "service", "architecture_pattern": "layered",
                "architecture_confidence": 0.85,
                "loc": 120, "methods": 6, "classes": 1, "avg_cc": 2.0,
                "imports": 10, "annotations": 6,
                "controller_deps": 0, "service_deps": 0, "repository_deps": 1,
                "entity_deps": 0, "adapter_deps": 0, "port_deps": 0,
                "usecase_deps": 0, "gateway_deps": 0, "total_cross_layer_deps": 1,
                "has_business_logic": True, "has_data_access": True,
                "has_http_handling": False, "has_validation": False,
                "has_transaction": False, "violates_layer_separation": False
            }
        ]
    }

    print("📊 Step 1: Analyzing project...")
    r1 = requests.post(f"{BASE}/analyze-project-full", json=files_payload, timeout=30)
    analysis = r1.json()
    print(f"  Overall    : {analysis['overall_display']}")
    print(f"  Violations : {analysis['total_violations']}")
    aps = [ap['type'] for ap in analysis['anti_patterns']]
    print(f"  Patterns   : {aps}")

    print("\n🤖 Step 2: Getting AI fix suggestions...")
    fix_payload = {
        "architecture_pattern": analysis["architecture_pattern"],
        "anti_patterns": analysis["anti_patterns"]
    }
    r2 = requests.post(f"{BASE}/generate-fixes", json=fix_payload, timeout=60)
    fixes = r2.json()
    print(f"  Total AI fixes: {fixes['total_fixes']}")
    for s in fixes['suggestions']:
        print(f"\n  [{s['severity']}] {s['anti_pattern']}")
        print(f"  AI powered: {s['ai_powered']}")
        print(f"  💡 Recommendation: {s['recommendation']}")
        if s.get('gemini_fix'):
            lines = s['gemini_fix'].split('\n')
            for line in lines[:10]:
                print(f"    {line}")


# ── Quick verification: check 'recommendation' field present ──────────────
def test_recommendation_field_always_present():
    sep("TEST 6: Verify 'recommendation' field is always present")
    patterns = [
        "no_validation", "layer_skip_in_layered", "missing_transaction_in_layered",
        "business_logic_in_controller_layered", "broad_catch", "tight_coupling_new_keyword",
        "missing_port_adapter_in_hexagonal", "framework_dependency_in_domain_hexagonal"
    ]
    all_ok = True
    for pat in patterns:
        payload = {
            "anti_pattern": pat, "files": ["TestFile.java"],
            "architecture_pattern": "layered", "affected_layer": "Controller",
            "severity": "MEDIUM", "description": ""
        }
        r = requests.post(f"{BASE}/generate-fix", json=payload, timeout=20)
        data = r.json()
        rec = data.get("recommendation", "")
        status = "✅" if rec else "❌"
        if not rec:
            all_ok = False
        print(f"  {status} {pat}")
        if rec:
            print(f"       {rec[:80]}...")
    print()
    print("✅ All recommendations present!" if all_ok else "❌ Some recommendations missing!")


if __name__ == "__main__":
    print("SpringForge ML Service — Gemini Fix Suggestion Tests (v2)")
    print("Server must be running: uvicorn app.main:app --port 8081 --reload\n")
    print("💡 TIP: Watch the uvicorn server console for [Gemini] diagnostic lines.")
    print("        If you see '[Gemini] HTTP status: 400/403', the API key needs checking.")
    print("        If you see 'NameResolutionError', your server has no internet access.\n")

    try:
        r = requests.get(f"{BASE}/")
        if r.status_code != 200:
            print("❌ Server not running!")
            exit(1)
        print(f"✅ Server running: v{r.json()['version']}\n")

        test_single_fix_no_validation()
        test_single_fix_layer_skip()
        test_single_fix_missing_tx()
        test_project_fixes()
        test_full_pipeline()
        test_recommendation_field_always_present()

        print(f"\n{'═'*65}")
        print("✅ All tests complete!")
        print('═'*65)

    except requests.exceptions.ConnectionError:
        print("\n❌ Cannot connect. Start: uvicorn app.main:app --port 8081 --reload")
    except Exception as e:
        import traceback
        print(f"\n❌ Unexpected error: {e}")
        traceback.print_exc()