"""
test_quality_score.py
──────────────────────────────────────────────────────────────────
Tests for Quality Score endpoints + Combined analysis endpoint.
Run with:  python test_quality_score.py
──────────────────────────────────────────────────────────────────
"""

import requests
import json

BASE = "http://localhost:8081"

# ── Reusable sample files ─────────────────────────────────────────

BAD_CONTROLLER = {
    "file_name": "UserController.java",
    "file_path": "src/main/java/controller/UserController.java",
    "layer": "controller",
    "architecture_pattern": "layered",
    "architecture_confidence": 0.85,
    "loc": 280, "methods": 12, "classes": 1, "avg_cc": 3.5,
    "imports": 22, "annotations": 10,
    "controller_deps": 0, "service_deps": 1, "repository_deps": 2,
    "entity_deps": 0, "adapter_deps": 0, "port_deps": 0,
    "usecase_deps": 0, "gateway_deps": 0, "total_cross_layer_deps": 3,
    "has_business_logic": True, "has_data_access": False,
    "has_http_handling": True, "has_validation": False,
    "has_transaction": False, "violates_layer_separation": True,
}

GOOD_SERVICE = {
    "file_name": "OrderService.java",
    "file_path": "src/main/java/service/OrderService.java",
    "layer": "service",
    "architecture_pattern": "layered",
    "architecture_confidence": 0.85,
    "loc": 120, "methods": 6, "classes": 1, "avg_cc": 2.0,
    "imports": 10, "annotations": 6,
    "controller_deps": 0, "service_deps": 0, "repository_deps": 1,
    "entity_deps": 0, "adapter_deps": 0, "port_deps": 0,
    "usecase_deps": 0, "gateway_deps": 0, "total_cross_layer_deps": 1,
    "has_business_logic": True, "has_data_access": True,
    "has_http_handling": False, "has_validation": False,
    "has_transaction": True, "violates_layer_separation": False,
}

CLEAN_REPO = {
    "file_name": "UserRepository.java",
    "file_path": "src/main/java/repository/UserRepository.java",
    "layer": "repository",
    "architecture_pattern": "layered",
    "architecture_confidence": 0.85,
    "loc": 45, "methods": 3, "classes": 0, "avg_cc": 1.0,
    "imports": 5, "annotations": 4,
    "controller_deps": 0, "service_deps": 0, "repository_deps": 0,
    "entity_deps": 0, "adapter_deps": 0, "port_deps": 0,
    "usecase_deps": 0, "gateway_deps": 0, "total_cross_layer_deps": 0,
    "has_business_logic": False, "has_data_access": True,
    "has_http_handling": False, "has_validation": False,
    "has_transaction": False, "violates_layer_separation": False,
}

MEDIUM_ENTITY = {
    "file_name": "Order.java",
    "file_path": "src/main/java/entity/Order.java",
    "layer": "entity",
    "architecture_pattern": "layered",
    "architecture_confidence": 0.85,
    "loc": 95, "methods": 8, "classes": 1, "avg_cc": 1.5,
    "imports": 7, "annotations": 8,
    "controller_deps": 0, "service_deps": 0, "repository_deps": 0,
    "entity_deps": 0, "adapter_deps": 0, "port_deps": 0,
    "usecase_deps": 0, "gateway_deps": 0, "total_cross_layer_deps": 0,
    "has_business_logic": True, "has_data_access": False,
    "has_http_handling": False, "has_validation": False,
    "has_transaction": False, "violates_layer_separation": False,
}

ALL_FILES = [BAD_CONTROLLER, GOOD_SERVICE, CLEAN_REPO, MEDIUM_ENTITY]


def sep(title=""):
    print(f"\n{'═'*60}")
    if title: print(f"  {title}")
    print('═'*60)


# ── Test 1: Health check ──────────────────────────────────────────
def test_health():
    sep("TEST 1: Health Check")
    r = requests.get(f"{BASE}/")
    print(json.dumps(r.json(), indent=2))


# ── Test 2: Single file quality score ─────────────────────────────
def test_single_quality():
    sep("TEST 2: Single File Quality Score — Bad Controller")
    payload = {k: v for k, v in BAD_CONTROLLER.items()
               if k not in ('file_name','file_path','architecture_pattern',
                             'architecture_confidence','entity_deps',
                             'usecase_deps','gateway_deps')}
    r = requests.post(f"{BASE}/predict-quality-score", json=payload)
    print(json.dumps(r.json(), indent=2))

    sep("TEST 2b: Single File Quality Score — Good Service")
    payload2 = {k: v for k, v in GOOD_SERVICE.items()
                if k not in ('file_name','file_path','architecture_pattern',
                              'architecture_confidence','entity_deps',
                              'usecase_deps','gateway_deps')}
    r2 = requests.post(f"{BASE}/predict-quality-score", json=payload2)
    print(json.dumps(r2.json(), indent=2))


# ── Test 3: Multi-file quality analysis ───────────────────────────
def test_quality_analysis():
    sep("TEST 3: Multi-File Quality Analysis")
    r = requests.post(f"{BASE}/analyze-quality", json={"files": ALL_FILES})
    data = r.json()
    print(f"Overall Score   : {data['overall_display']}")
    print(f"Files Analyzed  : {data['total_files_analyzed']}")
    print(f"Total Issues    : {data['total_issues_found']}")
    print(f"Projected Score : {data['projected_score_after_fixes']}")
    print(f"\nLayer Scores:")
    for ls in data['layer_scores']:
        print(f"  {ls['layer']:<15} {ls['quality_display']}")
    print(f"\nFile Details (worst first):")
    for f in data['files']:
        print(f"  {f['file_name']:<35} {f['quality_display']}")
        for issue in f['issues']:
            print(f"    ⚠️  {issue}")


# ── Test 4: Anti-pattern analysis (existing) ──────────────────────
def test_antipattern():
    sep("TEST 4: Anti-Pattern Analysis (existing endpoint)")
    r = requests.post(f"{BASE}/analyze-project", json={"files": ALL_FILES})
    data = r.json()
    print(f"Architecture    : {data['architecture_pattern']}")
    print(f"Total Violations: {data['total_violations']}")
    print(f"Summary:\n{data['summary']}")
    for ap in data['anti_patterns']:
        print(f"\n  [{ap['severity']}] {ap['type']}")
        print(f"    Files: {ap['files']}")
        print(f"    Recommendation: {ap['recommendation']}")


# ── Test 5: COMBINED analysis (main IntelliJ endpoint) ────────────
def test_combined():
    sep("TEST 5: COMBINED Analysis — /analyze-project-full")
    r = requests.post(f"{BASE}/analyze-project-full", json={"files": ALL_FILES})
    data = r.json()

    print(f"\n{'─'*60}")
    print(f"  SPRINGFORGE CODE QUALITY ANALYSIS REPORT")
    print(f"{'─'*60}")
    print(f"  Architecture : {data['architecture_pattern']}")
    print(f"  Files        : {data['total_files_analyzed']}")
    print(f"  Date         : {data['analysis_date']}")
    print(f"  Violations   : {data['total_violations']}")

    print(f"\n  QUALITY SCORE DASHBOARD")
    print(f"  Overall: {data['overall_display']}")
    for ls in data['layer_scores']:
        bar   = '█' * int(ls['mean_score'] / 5)
        empty = '░' * (20 - int(ls['mean_score'] / 5))
        print(f"  {ls['layer']:<15} {bar}{empty}  {ls['mean_score']:.0f}/100  {ls['quality_emoji']}")

    print(f"\n  QUALITY SUMMARY")
    print(f"  {data['quality_summary']}")

    print(f"\n  ARCHITECTURAL VIOLATIONS")
    if data['anti_patterns']:
        for ap in data['anti_patterns']:
            print(f"  [{ap['severity']:<8}] {ap['type']}")
            print(f"             Files: {', '.join(ap['files'])}")
            print(f"             Fix  : {ap['recommendation']}")
    else:
        print("  ✅ No violations detected")

    print(f"\n  CLEAN FILES ({len(data['clean_files'])})")
    for cf in data['clean_files']:
        print(f"    ✅ {cf}")

    print(f"\n  FILE DETAILS (worst → best)")
    for f in data['files']:
        print(f"  {f['file_name']:<35} {f['quality_display']}")
        for issue in f['issues']:
            print(f"    • {issue}")

    print(f"\n  PROJECTED IMPROVEMENT")
    print(f"  Current : {data['overall_display']}")
    print(f"  After fix: 🟢 {data['projected_score_after_fixes']:.0f}/100")
    print(f"\n  VIOLATION SUMMARY")
    print(f"  {data['violation_summary']}")


if __name__ == "__main__":
    print("SpringForge ML Service — Endpoint Tests")
    print("Make sure the server is running: uvicorn app.main:app --reload")

    try:
        test_health()
        test_single_quality()
        test_quality_analysis()
        test_antipattern()
        test_combined()
        print("\n✅ All tests complete!")
    except requests.exceptions.ConnectionError:
        print("\n❌ Cannot connect to server.")
        print("   Start it first: uvicorn app.main:app --reload")