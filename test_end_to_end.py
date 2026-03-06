"""
test_end_to_end.py
──────────────────────────────────────────────────────────────────────────────
SpringForge ML Service — Full End-to-End Integration Test

Tests the complete pipeline for a LAYERED architecture project:

  SCENARIO: E-Commerce project with 2 real anti-patterns
  ┌─────────────────────────────────────┬──────────────────────────────────┐
  │ File                                │ Anti-Pattern                     │
  ├─────────────────────────────────────┼──────────────────────────────────┤
  │ UserController.java                 │ layer_skip_in_layered (CRITICAL) │
  │ OrderService.java                   │ missing_transaction_in_layered   │
  │ ProductService.java                 │ clean ✅                         │
  └─────────────────────────────────────┴──────────────────────────────────┘

  FLOW:
    Step 1 — Anti-pattern detection on BEFORE files
    Step 2 — Quality score on BEFORE files
    Step 3 — Get Gemini AI fix suggestions
    Step 4 — Apply fixes (send AFTER payloads)
    Step 5 — Anti-pattern detection on AFTER files  (expect: clean)
    Step 6 — Quality score on AFTER files           (expect: higher score)
    Step 7 — Print delta report

Run: python test_end_to_end.py
──────────────────────────────────────────────────────────────────────────────
"""
import requests
import json
from datetime import datetime

BASE = "http://127.0.0.1:8081"
SEP  = "═" * 70


def sep(title=""):
    print(f"\n{SEP}")
    if title:
        print(f"  {title}")
        print(SEP)


# ──────────────────────────────────────────────────────────────────────────
# PROJECT FILES — BEFORE FIX
# ──────────────────────────────────────────────────────────────────────────

# FILE 1: UserController.java
#   Anti-pattern: layer_skip_in_layered
#   Why: controller directly injects repository (repo_deps=2), bypasses service
#   Also: no input validation (has_validation=False), high cross-layer deps
BEFORE_USER_CONTROLLER = {
    "file_name"               : "UserController.java",
    "file_path"               : "src/main/java/com/ecommerce/controller/UserController.java",
    "layer"                   : "controller",
    "architecture_pattern"    : "layered",
    "architecture_confidence" : 0.93,
    "loc"                     : 145,
    "methods"                 : 6,
    "classes"                 : 1,
    "avg_cc"                  : 2.8,
    "imports"                 : 15,
    "annotations"             : 8,
    "controller_deps"         : 0,
    "service_deps"            : 0,
    "repository_deps"         : 2,   # ❌ controller directly uses 2 repositories
    "entity_deps"             : 1,
    "adapter_deps"            : 0,
    "port_deps"               : 0,
    "usecase_deps"            : 0,
    "gateway_deps"            : 0,
    "total_cross_layer_deps"  : 3,
    "has_business_logic"      : True,
    "has_data_access"         : True,
    "has_http_handling"       : True,
    "has_validation"          : False,  # ❌ no @Valid
    "has_transaction"         : False,
    "violates_layer_separation": True,  # ❌ skips service layer
    "uses_new_keyword"        : False,
    "has_broad_catch"         : False,
}

# FILE 2: OrderService.java
#   Anti-pattern: missing_transaction_in_layered
#   Why: service layer writes to DB (repo_deps=2, has_data_access=True) without @Transactional
BEFORE_ORDER_SERVICE = {
    "file_name"               : "OrderService.java",
    "file_path"               : "src/main/java/com/ecommerce/service/OrderService.java",
    "layer"                   : "service",
    "architecture_pattern"    : "layered",
    "architecture_confidence" : 0.93,
    "loc"                     : 130,
    "methods"                 : 5,
    "classes"                 : 1,
    "avg_cc"                  : 2.1,
    "imports"                 : 12,
    "annotations"             : 7,
    "controller_deps"         : 0,
    "service_deps"            : 0,
    "repository_deps"         : 2,   # accesses DB
    "entity_deps"             : 1,
    "adapter_deps"            : 0,
    "port_deps"               : 0,
    "usecase_deps"            : 0,
    "gateway_deps"            : 0,
    "total_cross_layer_deps"  : 3,
    "has_business_logic"      : True,
    "has_data_access"         : True,
    "has_http_handling"       : False,
    "has_validation"          : False,
    "has_transaction"         : False,  # ❌ writes DB without @Transactional
    "violates_layer_separation": False,
    "uses_new_keyword"        : False,
    "has_broad_catch"         : False,
}

# FILE 3: ProductService.java
#   Clean — proper service with @Transactional
BEFORE_PRODUCT_SERVICE = {
    "file_name"               : "ProductService.java",
    "file_path"               : "src/main/java/com/ecommerce/service/ProductService.java",
    "layer"                   : "service",
    "architecture_pattern"    : "layered",
    "architecture_confidence" : 0.93,
    "loc"                     : 95,
    "methods"                 : 4,
    "classes"                 : 1,
    "avg_cc"                  : 1.5,
    "imports"                 : 10,
    "annotations"             : 7,
    "controller_deps"         : 0,
    "service_deps"            : 0,
    "repository_deps"         : 1,
    "entity_deps"             : 0,
    "adapter_deps"            : 0,
    "port_deps"               : 0,
    "usecase_deps"            : 0,
    "gateway_deps"            : 0,
    "total_cross_layer_deps"  : 1,
    "has_business_logic"      : True,
    "has_data_access"         : True,
    "has_http_handling"       : False,
    "has_validation"          : False,
    "has_transaction"         : True,   # ✅ properly annotated
    "violates_layer_separation": False,
    "uses_new_keyword"        : False,
    "has_broad_catch"         : False,
}


# ──────────────────────────────────────────────────────────────────────────
# PROJECT FILES — AFTER FIX
# ──────────────────────────────────────────────────────────────────────────

# FILE 1 FIXED: UserController.java
#   Removed direct repository injection — now uses UserService only
#   Added @Valid to request bodies
AFTER_USER_CONTROLLER = {
    **BEFORE_USER_CONTROLLER,
    "repository_deps"         : 0,     # ✅ no longer directly uses repo
    "service_deps"            : 1,     # ✅ now properly injects UserService
    "entity_deps"             : 0,
    "total_cross_layer_deps"  : 1,
    "has_business_logic"      : False, # ✅ moved to service
    "has_data_access"         : False, # ✅ controller no longer touches data
    "has_validation"          : True,  # ✅ added @Valid
    "violates_layer_separation": False,# ✅ fixed
    "loc"                     : 75,    # ✅ controller is now thinner
    "avg_cc"                  : 1.4,
}

# FILE 2 FIXED: OrderService.java
#   Added @Transactional to all data-modifying methods
AFTER_ORDER_SERVICE = {
    **BEFORE_ORDER_SERVICE,
    "has_transaction"         : True,  # ✅ added @Transactional
    "annotations"             : 9,     # ✅ more annotations after fix
}

# FILE 3: ProductService.java — unchanged (was already clean)
AFTER_PRODUCT_SERVICE = {**BEFORE_PRODUCT_SERVICE}


# ──────────────────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────────────────

def predict_single(file_data: dict) -> str:
    """Call /predict-antipattern for one file."""
    r = requests.post(f"{BASE}/predict-antipattern", json=file_data, timeout=10)
    r.raise_for_status()
    return r.json().get("anti_pattern", "ERROR")


def predict_quality(file_data: dict) -> dict:
    """Call /predict-quality-score for one file."""
    r = requests.post(f"{BASE}/predict-quality-score", json=file_data, timeout=10)
    r.raise_for_status()
    return r.json()


def analyze_full(files: list) -> dict:
    """Call /analyze-project-full for a list of files."""
    r = requests.post(f"{BASE}/analyze-project-full", json={"files": files}, timeout=30)
    r.raise_for_status()
    return r.json()


def generate_fixes(anti_patterns: list, architecture: str) -> dict:
    """Call /generate-fixes for all detected violations."""
    payload = {
        "architecture_pattern": architecture,
        "anti_patterns": anti_patterns,
    }
    r = requests.post(f"{BASE}/generate-fixes", json=payload, timeout=120)
    r.raise_for_status()
    return r.json()


def quality_bar(score: float) -> str:
    filled = int(score / 5)
    empty  = 20 - filled
    return f"[{'█' * filled}{'░' * empty}] {score:.0f}/100"


def print_file_prediction(name: str, ap: str, qs: dict):
    icon = "✅" if ap == "clean" else "❌"
    print(f"  {icon}  {name:<35} AP: {ap:<40} Quality: {qs['quality_display']}")


# ──────────────────────────────────────────────────────────────────────────
# MAIN TEST
# ──────────────────────────────────────────────────────────────────────────

def run():
    print(SEP)
    print("  SPRINGFORGE — END-TO-END INTEGRATION TEST")
    print("  Layered Architecture | E-Commerce Project | 3 Files")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(SEP)

    # ── Verify server ────────────────────────────────────────────────────
    try:
        r = requests.get(f"{BASE}/", timeout=5)
        info = r.json()
        print(f"\n✅ Server: {info['status']}  v{info['version']}")
        print(f"   Gemini configured: {info.get('gemini_configured', False)}")
    except Exception as e:
        print(f"\n❌ Server not reachable: {e}")
        print("   Start with: uvicorn app.main:app --port 8081 --reload")
        return

    BEFORE_FILES = [BEFORE_USER_CONTROLLER, BEFORE_ORDER_SERVICE, BEFORE_PRODUCT_SERVICE]
    AFTER_FILES  = [AFTER_USER_CONTROLLER,  AFTER_ORDER_SERVICE,  AFTER_PRODUCT_SERVICE]

    # ════════════════════════════════════════════════════════════════════
    # STEP 1 — Anti-pattern detection on BEFORE files
    # ════════════════════════════════════════════════════════════════════
    sep("STEP 1 — Anti-Pattern Detection  (BEFORE FIX)")

    before_aps  = []
    before_qss  = []
    before_names = ["UserController.java", "OrderService.java", "ProductService.java"]

    for i, f in enumerate(BEFORE_FILES):
        ap = predict_single(f)
        qs = predict_quality(f)
        before_aps.append(ap)
        before_qss.append(qs)
        print_file_prediction(before_names[i], ap, qs)

    print()
    violations_before = [(n, ap) for n, ap in zip(before_names, before_aps) if ap != "clean"]
    print(f"  Violations detected: {len(violations_before)}")
    for name, ap in violations_before:
        print(f"    ⚠️  {name} → {ap}")

    avg_before = sum(q['quality_score'] for q in before_qss) / len(before_qss)
    print(f"\n  Average Quality Score BEFORE: {quality_bar(avg_before)}")

    # ════════════════════════════════════════════════════════════════════
    # STEP 2 — Full project analysis BEFORE
    # ════════════════════════════════════════════════════════════════════
    sep("STEP 2 — Full Project Analysis  (BEFORE FIX)")

    analysis_before = analyze_full(BEFORE_FILES)
    print(f"  Architecture  : {analysis_before['architecture_pattern']}")
    print(f"  Files Analyzed: {analysis_before['total_files_analyzed']}")
    print(f"  Overall Score : {analysis_before['overall_display']}")
    print(f"  Violations    : {analysis_before['total_violations']}")
    print()
    print("  Anti-patterns found:")
    for ap in analysis_before['anti_patterns']:
        print(f"    🔴 [{ap['severity']:8}] {ap['type']}")
        print(f"         Files     : {', '.join(ap['files'])}")
        print(f"         Confidence: {ap['confidence']:.0%}")
    print()
    print("  Layer Quality Breakdown:")
    for ls in analysis_before['layer_scores']:
        bar = quality_bar(ls['mean_score'])
        print(f"    {ls['layer']:<15} {bar}  ({ls['file_count']} file{'s' if ls['file_count']>1 else ''})")
    print()
    print(f"  Quality Summary:\n    {analysis_before['quality_summary']}")
    print(f"\n  Violation Summary:\n    {analysis_before['violation_summary']}")
    print(f"\n  Projected score after fixes: {analysis_before['projected_score_after_fixes']}/100")

    # ════════════════════════════════════════════════════════════════════
    # STEP 3 — Gemini AI fix suggestions
    # ════════════════════════════════════════════════════════════════════
    sep("STEP 3 — AI Fix Suggestions  (Gemini)")

    print("  Calling /generate-fixes ... (parallel Gemini calls)\n")
    fixes = generate_fixes(analysis_before['anti_patterns'], "layered")

    print(f"  Total fixes generated: {fixes['total_fixes']}")
    print()

    for s in fixes['suggestions']:
        ai_icon = "🤖" if s['ai_powered'] else "📋"
        print(f"  {ai_icon} [{s['severity']:8}] {s['anti_pattern']}")
        print(f"     Impact  : {s['impact_points']} quality points")
        print(f"     Files   : {', '.join(s['files'])}")
        print(f"     Problem : {s['problem'][:90]}...")
        print(f"     Fix     : {s['recommendation'][:90]}...")
        if s.get('gemini_fix'):
            lines = s['gemini_fix'].split('\n')
            print(f"     Gemini  :")
            for line in lines[:8]:
                print(f"       {line}")
        print()

    # ════════════════════════════════════════════════════════════════════
    # STEP 4 — Anti-pattern detection on AFTER files
    # ════════════════════════════════════════════════════════════════════
    sep("STEP 4 — Anti-Pattern Detection  (AFTER FIX)")

    after_aps  = []
    after_qss  = []
    after_names = ["UserController.java (fixed)", "OrderService.java (fixed)", "ProductService.java"]

    for i, f in enumerate(AFTER_FILES):
        ap = predict_single(f)
        qs = predict_quality(f)
        after_aps.append(ap)
        after_qss.append(qs)
        print_file_prediction(after_names[i], ap, qs)

    print()
    violations_after = [(n, ap) for n, ap in zip(after_names, after_aps) if ap != "clean"]
    print(f"  Violations detected: {len(violations_after)}")
    if violations_after:
        for name, ap in violations_after:
            print(f"    ⚠️  {name} → {ap}")
    else:
        print("    ✅ No violations — all files are clean!")

    avg_after = sum(q['quality_score'] for q in after_qss) / len(after_qss)
    print(f"\n  Average Quality Score AFTER: {quality_bar(avg_after)}")

    # ════════════════════════════════════════════════════════════════════
    # STEP 5 — Full project analysis AFTER
    # ════════════════════════════════════════════════════════════════════
    sep("STEP 5 — Full Project Analysis  (AFTER FIX)")

    analysis_after = analyze_full(AFTER_FILES)
    print(f"  Overall Score : {analysis_after['overall_display']}")
    print(f"  Violations    : {analysis_after['total_violations']}")
    print()
    if analysis_after['anti_patterns']:
        print("  Remaining anti-patterns:")
        for ap in analysis_after['anti_patterns']:
            print(f"    ⚠️  [{ap['severity']}] {ap['type']}")
    else:
        print("  ✅ No anti-patterns detected!")
    print()
    print("  Layer Quality Breakdown:")
    for ls in analysis_after['layer_scores']:
        bar = quality_bar(ls['mean_score'])
        print(f"    {ls['layer']:<15} {bar}  ({ls['file_count']} file{'s' if ls['file_count']>1 else ''})")

    # ════════════════════════════════════════════════════════════════════
    # STEP 6 — Delta Report
    # ════════════════════════════════════════════════════════════════════
    sep("STEP 6 — DELTA REPORT  (Before vs After)")

    score_before = analysis_before['overall_score']
    score_after  = analysis_after['overall_score']
    delta        = score_after - score_before
    viol_before  = analysis_before['total_violations']
    viol_after   = analysis_after['total_violations']

    print(f"""
  ┌─────────────────────────────────────────────────────────┐
  │              QUALITY IMPROVEMENT SUMMARY                │
  ├─────────────────────────────────────────────────────────┤
  │  Metric                    BEFORE       AFTER    DELTA  │
  ├─────────────────────────────────────────────────────────┤
  │  Overall Quality Score     {score_before:>5.1f}/100   {score_after:>5.1f}/100   {delta:+.1f}  │
  │  Total Violations          {viol_before:>8}     {viol_after:>8}   {viol_before-viol_after:+5}  │
  │  Files with Violations     {analysis_before['files_with_violations']:>8}     {analysis_after['files_with_violations']:>8}   {analysis_before['files_with_violations']-analysis_after['files_with_violations']:+5}  │
  └─────────────────────────────────────────────────────────┘""")

    print()
    print("  Per-File Score Improvement:")
    file_labels = ["UserController.java", "OrderService.java  ", "ProductService.java"]
    for i in range(len(BEFORE_FILES)):
        b = before_qss[i]['quality_score']
        a = after_qss[i]['quality_score']
        d = a - b
        d_str = f"{d:+.1f}"
        arrow = "↑" if d > 0 else ("→" if d == 0 else "↓")
        color = "✅" if d > 0 else ("✔️ " if d == 0 else "⚠️ ")
        print(f"    {color} {file_labels[i]}   {b:>5.1f} → {a:>5.1f}   {arrow} {d_str}")

    print()
    print("  Anti-Pattern Detection Results:")
    for i in range(len(BEFORE_FILES)):
        b = before_aps[i]
        a = after_aps[i]
        if b == a == "clean":
            print(f"    ✅ {before_names[i]:<35} clean → clean")
        elif b != "clean" and a == "clean":
            print(f"    ✅ {before_names[i]:<35} {b} → FIXED (clean)")
        elif b == "clean" and a != "clean":
            print(f"    ❌ {before_names[i]:<35} clean → REGRESSION ({a})")
        else:
            print(f"    ⚠️  {before_names[i]:<35} {b} → {a}")

    print()
    # Overall assessment
    if delta > 0 and viol_after < viol_before:
        print("  ✅ PASS — Quality improved and violations reduced after fix.")
    elif delta > 0:
        print("  🟡 PARTIAL — Quality improved but some violations remain.")
    elif delta == 0 and viol_after == 0:
        print("  ✅ PASS — Already clean, no regression.")
    else:
        print("  ❌ FAIL — Quality did not improve as expected.")

    print()
    print(f"  Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(SEP)


if __name__ == "__main__":
    try:
        run()
    except requests.exceptions.ConnectionError:
        print(f"\n❌ Cannot connect to {BASE}")
        print("   Start server: uvicorn app.main:app --port 8081 --reload")
    except requests.exceptions.HTTPError as e:
        print(f"\n❌ HTTP error: {e}")
        print(f"   Response: {e.response.text[:300] if e.response else 'none'}")
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted")
    except Exception as e:
        import traceback
        print(f"\n❌ Unexpected error: {e}")
        traceback.print_exc()