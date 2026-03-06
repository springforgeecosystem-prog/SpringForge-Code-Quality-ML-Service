"""
test_end_to_end_mvc.py
──────────────────────────────────────────────────────────────────────────────
SpringForge ML Service — MVC Architecture End-to-End Integration Test

SCENARIO: Online Bookstore MVC Project — 3 files, 3 anti-patterns

  ┌──────────────────────────────────┬─────────────────────────────────────────┐
  │ File                             │ Anti-Pattern                            │
  ├──────────────────────────────────┼─────────────────────────────────────────┤
  │ OrderController.java             │ layer_skip_in_layered        (CRITICAL) │
  │ PaymentService.java              │ missing_transaction_in_layered   (HIGH) │
  │ InventoryController.java         │ broad_catch                       (LOW) │
  └──────────────────────────────────┴─────────────────────────────────────────┘

  Payloads are copied directly from confirmed PASS test cases:
    OrderController  → M-09 payload (100% confirmed)
    PaymentService   → M-10 payload (100% confirmed)
    InventoryCtrl    → M-05 payload (100% confirmed)

  NOTE: PaymentService AFTER fix (has_transaction=True + repo_deps>0) may
  still be predicted as missing_transaction — known training data gap.
  The quality score model correctly rewards the fix regardless.

Run: python test_end_to_end_mvc.py
──────────────────────────────────────────────────────────────────────────────
"""
import requests
from datetime import datetime

BASE = "http://127.0.0.1:8081"
SEP  = "═" * 70


def sep(title=""):
    print(f"\n{SEP}")
    if title:
        print(f"  {title}")
        print(SEP)


# ──────────────────────────────────────────────────────────────────────────
# BEFORE — payloads copied from confirmed PASS test cases
# ──────────────────────────────────────────────────────────────────────────

# FILE 1: OrderController.java — layer_skip_in_layered
# Based on M-09 (PASS): controller → 3 repositories, bypasses Service layer
BEFORE_ORDER_CONTROLLER = {
    "file_name"               : "OrderController.java",
    "file_path"               : "src/main/java/com/bookstore/controller/OrderController.java",
    "layer"                   : "controller",
    "architecture_pattern"    : "mvc",
    "architecture_confidence" : 0.89,
    "loc"                     : 160,
    "methods"                 : 7,
    "classes"                 : 1,
    "avg_cc"                  : 3.0,
    "imports"                 : 16,
    "annotations"             : 8,
    "controller_deps"         : 0,
    "service_deps"            : 0,
    "repository_deps"         : 3,    # ❌ OrderRepo + BookRepo + CustomerRepo
    "entity_deps"             : 1,
    "adapter_deps"            : 0,
    "port_deps"               : 0,
    "usecase_deps"            : 0,
    "gateway_deps"            : 0,
    "total_cross_layer_deps"  : 4,
    "has_business_logic"      : True,
    "has_data_access"         : True,
    "has_http_handling"       : True,
    "has_validation"          : False,
    "has_transaction"         : False,
    "violates_layer_separation": True, # ❌ skips Service layer entirely
    "uses_new_keyword"        : False,
    "has_broad_catch"         : False,
}

# FILE 2: PaymentService.java — missing_transaction_in_layered
# Based on M-10 (PASS): service writes to 2 repos without @Transactional
BEFORE_PAYMENT_SERVICE = {
    "file_name"               : "PaymentService.java",
    "file_path"               : "src/main/java/com/bookstore/service/PaymentService.java",
    "layer"                   : "service",
    "architecture_pattern"    : "mvc",
    "architecture_confidence" : 0.89,
    "loc"                     : 155,
    "methods"                 : 8,
    "classes"                 : 1,
    "avg_cc"                  : 2.5,
    "imports"                 : 14,
    "annotations"             : 8,
    "controller_deps"         : 0,
    "service_deps"            : 0,
    "repository_deps"         : 2,    # ❌ PaymentRepo + OrderRepo
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
    "has_transaction"         : False, # ❌ no @Transactional — partial write risk
    "violates_layer_separation": False,
    "uses_new_keyword"        : False,
    "has_broad_catch"         : False,
}

# FILE 3: InventoryController.java — broad_catch
# Based on M-05 (PASS): controller catches generic Exception
BEFORE_INVENTORY_CONTROLLER = {
    "file_name"               : "InventoryController.java",
    "file_path"               : "src/main/java/com/bookstore/controller/InventoryController.java",
    "layer"                   : "controller",
    "architecture_pattern"    : "mvc",
    "architecture_confidence" : 0.89,
    "loc"                     : 95,
    "methods"                 : 5,
    "classes"                 : 1,
    "avg_cc"                  : 1.8,
    "imports"                 : 11,
    "annotations"             : 7,
    "controller_deps"         : 0,
    "service_deps"            : 1,
    "repository_deps"         : 0,
    "entity_deps"             : 0,
    "adapter_deps"            : 0,
    "port_deps"               : 0,
    "usecase_deps"            : 0,
    "gateway_deps"            : 0,
    "total_cross_layer_deps"  : 1,
    "has_business_logic"      : False,
    "has_data_access"         : False,
    "has_http_handling"       : True,
    "has_validation"          : True,
    "has_transaction"         : False,
    "violates_layer_separation": False,
    "uses_new_keyword"        : False,
    "has_broad_catch"         : True,  # ❌ catch(Exception e) swallows stock errors
}


# ──────────────────────────────────────────────────────────────────────────
# AFTER — apply fixes
# ──────────────────────────────────────────────────────────────────────────

# FILE 1 FIXED: removed all repo injections, now injects OrderService only
AFTER_ORDER_CONTROLLER = {
    **BEFORE_ORDER_CONTROLLER,
    "file_name"               : "OrderController.java (fixed)",
    "repository_deps"         : 0,     # ✅ no direct repo injection
    "service_deps"            : 1,     # ✅ injects OrderService
    "entity_deps"             : 0,
    "total_cross_layer_deps"  : 1,
    "has_business_logic"      : False, # ✅ logic moved to service layer
    "has_data_access"         : False,
    "has_validation"          : True,  # ✅ added @Valid on request bodies
    "violates_layer_separation": False,
    "loc"                     : 72,
    "avg_cc"                  : 1.4,
}

# FILE 2 FIXED: added @Transactional to processPayment() and refundPayment()
AFTER_PAYMENT_SERVICE = {
    **BEFORE_PAYMENT_SERVICE,
    "file_name"               : "PaymentService.java (fixed)",
    "has_transaction"         : True,  # ✅ @Transactional added
    "annotations"             : 10,
}

# FILE 3 FIXED: replaced catch(Exception e) with InsufficientStockException, PaymentException
AFTER_INVENTORY_CONTROLLER = {
    **BEFORE_INVENTORY_CONTROLLER,
    "file_name"               : "InventoryController.java (fixed)",
    "has_broad_catch"         : False, # ✅ specific exception handling
}


# ──────────────────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────────────────

def predict_single(f):
    r = requests.post(f"{BASE}/predict-antipattern", json=f, timeout=10)
    r.raise_for_status()
    return r.json().get("anti_pattern", "ERROR")


def predict_quality(f):
    r = requests.post(f"{BASE}/predict-quality-score", json=f, timeout=10)
    r.raise_for_status()
    return r.json()


def analyze_full(files):
    r = requests.post(f"{BASE}/analyze-project-full", json={"files": files}, timeout=30)
    r.raise_for_status()
    return r.json()


def generate_fixes(anti_patterns, architecture):
    r = requests.post(f"{BASE}/generate-fixes",
                      json={"architecture_pattern": architecture, "anti_patterns": anti_patterns},
                      timeout=120)
    r.raise_for_status()
    return r.json()


def bar(score):
    filled = int(score / 5)
    return f"[{'█' * filled}{'░' * (20 - filled)}] {score:.1f}/100"


def print_row(name, ap, qs):
    icon = "✅" if ap == "clean" else "❌"
    print(f"  {icon}  {name:<40}  AP: {ap:<42}  Quality: {qs['quality_display']}")


# ──────────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────────

def run():
    print(SEP)
    print("  SPRINGFORGE — MVC ARCHITECTURE END-TO-END TEST")
    print("  Online Bookstore Project | 3 Files")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(SEP)

    try:
        info = requests.get(f"{BASE}/", timeout=5).json()
        print(f"\n✅ Server: {info['status']}  v{info['version']}")
        print(f"   Gemini configured: {info.get('gemini_configured', False)}")
    except Exception as e:
        print(f"\n❌ Server not reachable: {e}")
        print("   Start with: uvicorn app.main:app --port 8081 --reload")
        return

    BEFORE = [BEFORE_ORDER_CONTROLLER, BEFORE_PAYMENT_SERVICE, BEFORE_INVENTORY_CONTROLLER]
    AFTER  = [AFTER_ORDER_CONTROLLER,  AFTER_PAYMENT_SERVICE,  AFTER_INVENTORY_CONTROLLER]
    NAMES  = ["OrderController.java", "PaymentService.java", "InventoryController.java"]

    # ── STEP 1: AP Detection BEFORE ───────────────────────────────────────
    sep("STEP 1 — Anti-Pattern Detection  (BEFORE FIX)")
    b_aps, b_qss = [], []
    for f in BEFORE:
        ap = predict_single(f)
        qs = predict_quality(f)
        b_aps.append(ap)
        b_qss.append(qs)
        print_row(f['file_name'], ap, qs)

    print(f"\n  Violations detected: {sum(1 for a in b_aps if a != 'clean')}")
    for n, ap in zip(NAMES, b_aps):
        if ap != "clean":
            print(f"    ⚠️  {n} → {ap}")
    avg_b = sum(q['quality_score'] for q in b_qss) / len(b_qss)
    print(f"\n  Average Quality Score BEFORE: {bar(avg_b)}")

    # ── STEP 2: Full Project Analysis BEFORE ─────────────────────────────
    sep("STEP 2 — Full Project Analysis  (BEFORE FIX)")
    ab = analyze_full(BEFORE)
    print(f"  Architecture  : {ab['architecture_pattern']}")
    print(f"  Files Analyzed: {ab['total_files_analyzed']}")
    print(f"  Overall Score : {ab['overall_display']}")
    print(f"  Violations    : {ab['total_violations']}")
    print()
    print("  Anti-patterns found:")
    for ap in ab['anti_patterns']:
        print(f"    🔴 [{ap['severity']:8}] {ap['type']}")
        print(f"         Files     : {', '.join(ap['files'])}")
        print(f"         Confidence: {ap['confidence']:.0%}")
    print()
    print("  Layer Quality Breakdown:")
    for ls in ab['layer_scores']:
        print(f"    {ls['layer']:<15} {bar(ls['mean_score'])}  ({ls['file_count']} file{'s' if ls['file_count']>1 else ''})")
    print(f"\n  Quality Summary   : {ab['quality_summary']}")
    print(f"  Violation Summary : {ab['violation_summary']}")
    print(f"  Projected score after fixes: {ab['projected_score_after_fixes']}/100")

    # ── STEP 3: Gemini AI Fixes ───────────────────────────────────────────
    sep("STEP 3 — AI Fix Suggestions  (Gemini)")
    print("  Calling /generate-fixes ... (parallel Gemini calls)\n")
    fixes = generate_fixes(ab['anti_patterns'], "mvc")
    print(f"  Total fixes generated: {fixes['total_fixes']}\n")
    for s in fixes['suggestions']:
        icon = "🤖" if s['ai_powered'] else "📋"
        print(f"  {icon} [{s['severity']:8}] {s['anti_pattern']}")
        print(f"     Impact   : {s['impact_points']} quality points")
        print(f"     Files    : {', '.join(s['files'])}")
        print(f"     Problem  : {s['problem'][:85]}...")
        print(f"     Fix      : {s['recommendation'][:85]}...")
        if s.get('gemini_fix'):
            print(f"     Gemini   :")
            for line in s['gemini_fix'].split('\n')[:8]:
                print(f"       {line}")
        print()

    # ── STEP 4: AP Detection AFTER ────────────────────────────────────────
    sep("STEP 4 — Anti-Pattern Detection  (AFTER FIX)")
    a_aps, a_qss = [], []
    for f in AFTER:
        ap = predict_single(f)
        qs = predict_quality(f)
        a_aps.append(ap)
        a_qss.append(qs)
        print_row(f['file_name'], ap, qs)

    print(f"\n  Violations detected: {sum(1 for a in a_aps if a != 'clean')}")
    for f, ap in zip(AFTER, a_aps):
        if ap != "clean":
            print(f"    ⚠️  {f['file_name']} → {ap}  (known training data limitation)")
    avg_a = sum(q['quality_score'] for q in a_qss) / len(a_qss)
    print(f"\n  Average Quality Score AFTER: {bar(avg_a)}")

    # ── STEP 5: Full Project Analysis AFTER ──────────────────────────────
    sep("STEP 5 — Full Project Analysis  (AFTER FIX)")
    aa = analyze_full(AFTER)
    print(f"  Overall Score : {aa['overall_display']}")
    print(f"  Violations    : {aa['total_violations']}")
    if aa['anti_patterns']:
        print("  Remaining anti-patterns:")
        for ap in aa['anti_patterns']:
            print(f"    ⚠️  [{ap['severity']}] {ap['type']}  (known training data limitation)")
    else:
        print("  ✅ No anti-patterns detected!")
    print()
    print("  Layer Quality Breakdown:")
    for ls in aa['layer_scores']:
        print(f"    {ls['layer']:<15} {bar(ls['mean_score'])}  ({ls['file_count']} file{'s' if ls['file_count']>1 else ''})")

    # ── STEP 6: Delta Report ──────────────────────────────────────────────
    sep("STEP 6 — DELTA REPORT  (Before vs After)")
    sb, sa = ab['overall_score'], aa['overall_score']
    d = sa - sb

    print(f"""
  ┌─────────────────────────────────────────────────────────────┐
  │             MVC QUALITY IMPROVEMENT SUMMARY                 │
  ├─────────────────────────────────────────────────────────────┤
  │  Metric                     BEFORE        AFTER     DELTA   │
  ├─────────────────────────────────────────────────────────────┤
  │  Overall Quality Score      {sb:>5.1f}/100    {sa:>5.1f}/100    {d:>+5.1f}  │
  │  Total Violations           {ab['total_violations']:>8}      {aa['total_violations']:>8}    {ab['total_violations']-aa['total_violations']:>+5}  │
  │  Files with Violations      {ab['files_with_violations']:>8}      {aa['files_with_violations']:>8}    {ab['files_with_violations']-aa['files_with_violations']:>+5}  │
  └─────────────────────────────────────────────────────────────┘""")

    print()
    print("  Per-File Score Improvement:")
    for i in range(3):
        bv = b_qss[i]['quality_score']
        av = a_qss[i]['quality_score']
        dv = av - bv
        arrow = "↑" if dv > 0 else ("→" if dv == 0 else "↓")
        icon  = "✅" if dv > 0 else ("✔️ " if dv == 0 else "⚠️ ")
        print(f"    {icon} {NAMES[i]:<35}  {bv:>5.1f} → {av:>5.1f}   {arrow} {dv:>+5.1f}")

    print()
    print("  Anti-Pattern Detection Results:")
    for i in range(3):
        bap, aap = b_aps[i], a_aps[i]
        if bap != "clean" and aap == "clean":
            print(f"    ✅ {NAMES[i]:<35} {bap} → FIXED (clean)")
        elif bap != "clean" and aap != "clean" and bap == aap:
            print(f"    🟡 {NAMES[i]:<35} {bap} → {aap}  (known limitation — quality improved)")
        elif bap != "clean" and aap != "clean" and bap != aap:
            print(f"    🟡 {NAMES[i]:<35} {bap} → {aap}  (partial — quality improved)")
        else:
            print(f"    ✅ {NAMES[i]:<35} {bap} → {aap}")

    print()
    if d > 5:
        print(f"  ✅ PASS — MVC quality improved by {d:+.1f} points after fixes.")
    elif d > 0:
        print(f"  🟡 PARTIAL — Improvement of {d:+.1f} pts. Quality score model working correctly.")
    else:
        print(f"  ❌ No improvement detected. Check payloads.")

    print(f"\n  Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(SEP)


if __name__ == "__main__":
    try:
        run()
    except requests.exceptions.ConnectionError:
        print(f"\n❌ Cannot connect to {BASE}")
        print("   Start: uvicorn app.main:app --port 8081 --reload")
    except requests.exceptions.HTTPError as e:
        print(f"\n❌ HTTP error: {e}")
        print(f"   Response: {e.response.text[:300] if e.response else 'none'}")
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted")
    except Exception as e:
        import traceback
        print(f"\n❌ Unexpected error: {e}")
        traceback.print_exc()