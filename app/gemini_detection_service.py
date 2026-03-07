"""
app/gemini_detection_service.py
----------------------------------------------------------------------
Three-tier anti-pattern detection pipeline:
  ML Model (primary) -> Gemini AI (fallback) -> Rule-based (last resort)

When the ML model's prediction is suspicious (low confidence, clean but
suspicious metrics, or layer-prediction mismatch), this service takes
over and uses Gemini AI to re-analyze the file. If Gemini is unavailable,
rule-based heuristics provide a last-resort detection.

Every detection is tagged with `detection_source`:
  - "ml_model"   : ML model prediction accepted as-is
  - "gemini_ai"  : Gemini AI overrode or corrected the ML prediction
  - "rule_based" : Rule-based heuristics used (Gemini unavailable)
----------------------------------------------------------------------
"""

import json
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.gemini_fix_service import (
    ANTI_PATTERN_CONTEXT,
    DISPLAY_NAMES,
    _call_gemini,
)
from app.model_loader import ANTI_PATTERN_INFO

# ── Configuration ────────────────────────────────────────────────────────
ML_CONFIDENCE_THRESHOLD = 0.65

# Architecture-specific anti-pattern lists
ARCHITECTURE_ANTIPATTERNS = {
    "layered": [
        "no_validation",
        "business_logic_in_controller_layered",
        "layer_skip_in_layered",
        "reversed_dependency_in_layered",
        "missing_transaction_in_layered",
        "tight_coupling_new_keyword",
        "broad_catch",
    ],
    "mvc": [
        "no_validation",
        "business_logic_in_controller_layered",
        "layer_skip_in_layered",
        "reversed_dependency_in_layered",
        "missing_transaction_in_layered",
        "tight_coupling_new_keyword",
        "broad_catch",
    ],
    "hexagonal": [
        "missing_port_adapter_in_hexagonal",
        "framework_dependency_in_domain_hexagonal",
        "adapter_without_port_hexagonal",
        "no_validation",
        "tight_coupling_new_keyword",
        "broad_catch",
    ],
    "clean": [
        "outer_depends_on_inner_clean",
        "usecase_framework_coupling_clean",
        "entity_framework_coupling_clean",
        "missing_gateway_interface_clean",
        "no_validation",
        "tight_coupling_new_keyword",
        "broad_catch",
    ],
    "clean_architecture": [
        "outer_depends_on_inner_clean",
        "usecase_framework_coupling_clean",
        "entity_framework_coupling_clean",
        "missing_gateway_interface_clean",
        "no_validation",
        "tight_coupling_new_keyword",
        "broad_catch",
    ],
}


# ═══════════════════════════════════════════════════════════════════════
# SUSPICION CHECKS — decide whether to invoke Gemini
# ═══════════════════════════════════════════════════════════════════════

def should_use_fallback(ml_prediction: str, ml_confidence: float, features: dict) -> bool:
    """
    Decide whether a file's ML prediction should be verified by Gemini.

    Returns True when:
      1. ML confidence is below threshold (model is uncertain)
      2. ML predicted "clean" but metrics look suspicious
      3. ML prediction contradicts obvious metric signals
    """
    layer = str(features.get("layer", "")).lower().strip()

    # Case 1: Low confidence
    if ml_confidence < ML_CONFIDENCE_THRESHOLD:
        return True

    # Case 2: Predicted "clean" but metrics are suspicious
    if ml_prediction == "clean" and _has_suspicious_metrics(layer, features):
        return True

    # Case 3: Prediction contradicts layer/metric signals
    if ml_prediction != "clean" and _prediction_contradicts_metrics(ml_prediction, layer, features):
        return True

    return False


def _has_suspicious_metrics(layer: str, features: dict) -> bool:
    """Check if a file predicted 'clean' has metrics suggesting violations."""

    if features.get("violates_layer_separation"):
        return True

    if features.get("total_cross_layer_deps", 0) >= 3:
        return True

    # Controller accessing repository directly
    if layer == "controller" and features.get("repository_deps", 0) > 0:
        return True

    # Service depending on controller (reversed dependency)
    if layer == "service" and features.get("controller_deps", 0) > 0:
        return True

    # Business logic in controller
    if layer == "controller" and features.get("has_business_logic"):
        return True

    # Service writing without transaction
    if layer == "service" and features.get("has_data_access") and not features.get("has_transaction"):
        return True

    # Tight coupling signal
    if features.get("uses_new_keyword"):
        return True

    # Broad catch signal
    if features.get("has_broad_catch"):
        return True

    # Controller without input validation
    if layer == "controller" and features.get("has_http_handling") and not features.get("has_validation"):
        return True

    return False


def _prediction_contradicts_metrics(ml_prediction: str, layer: str, features: dict) -> bool:
    """Check if the ML prediction doesn't match what the metrics clearly show."""

    # Controller-specific patterns predicted for non-controller files
    controller_patterns = {
        "business_logic_in_controller_layered",
        "layer_skip_in_layered",
        "no_validation",
        "outer_depends_on_inner_clean",
    }
    if ml_prediction in controller_patterns and layer not in ("controller", "unknown", ""):
        return True

    # Service-specific patterns predicted for non-service files
    service_patterns = {
        "missing_transaction_in_layered",
        "reversed_dependency_in_layered",
        "missing_port_adapter_in_hexagonal",
        "usecase_framework_coupling_clean",
        "missing_gateway_interface_clean",
    }
    if ml_prediction in service_patterns and layer not in ("service", "usecase", "unknown", ""):
        return True

    # Entity pattern predicted for non-entity files
    if ml_prediction == "entity_framework_coupling_clean" and layer not in ("entity", "unknown", ""):
        return True

    # Adapter pattern predicted for non-adapter files
    if ml_prediction == "adapter_without_port_hexagonal" and layer not in ("adapter", "unknown", ""):
        return True

    return False


# ═══════════════════════════════════════════════════════════════════════
# GEMINI AI DETECTION
# ═══════════════════════════════════════════════════════════════════════

def _build_detection_prompt(features: dict, ml_prediction: str, ml_confidence: float, architecture: str) -> str:
    """Build a Gemini prompt for single-file anti-pattern detection."""
    valid_patterns = ARCHITECTURE_ANTIPATTERNS.get(architecture, ARCHITECTURE_ANTIPATTERNS["layered"])

    pattern_descriptions = []
    for p in valid_patterns:
        info = ANTI_PATTERN_INFO.get(p, {})
        display = DISPLAY_NAMES.get(p, p.replace("_", " ").title())
        pattern_descriptions.append(f'  - "{p}": {display} -- {info.get("description", "")}')

    layer = features.get("layer", "unknown")

    return f"""You are a senior Spring Boot architect analyzing code metrics for anti-pattern detection in a **{architecture}** architecture project.

The ML model predicted this file as "{ml_prediction}" with {ml_confidence:.0%} confidence, but this prediction may be incorrect. Analyze the metrics independently and determine the CORRECT anti-pattern(s).

FILE METRICS:
  File: {features.get('file_name', 'unknown')}
  Layer: {layer}
  LOC: {features.get('loc', 0)}, Methods: {features.get('methods', 0)}, Classes: {features.get('classes', 0)}
  Imports: {features.get('imports', 0)}, Annotations: {features.get('annotations', 0)}
  Avg Cyclomatic Complexity: {features.get('avg_cc', 1.0)}
  Dependencies: controller={features.get('controller_deps', 0)}, service={features.get('service_deps', 0)}, repository={features.get('repository_deps', 0)}, entity={features.get('entity_deps', 0)}, adapter={features.get('adapter_deps', 0)}, port={features.get('port_deps', 0)}, usecase={features.get('usecase_deps', 0)}, gateway={features.get('gateway_deps', 0)}
  Total cross-layer deps: {features.get('total_cross_layer_deps', 0)}
  Flags: has_business_logic={features.get('has_business_logic', False)}, has_data_access={features.get('has_data_access', False)}, has_http_handling={features.get('has_http_handling', False)}, has_validation={features.get('has_validation', False)}, has_transaction={features.get('has_transaction', False)}, violates_layer_separation={features.get('violates_layer_separation', False)}, uses_new_keyword={features.get('uses_new_keyword', False)}, has_broad_catch={features.get('has_broad_catch', False)}

ML MODEL PREDICTION: "{ml_prediction}" (confidence: {ml_confidence:.0%})

VALID ANTI-PATTERNS for {architecture} architecture:
{chr(10).join(pattern_descriptions)}

ANALYSIS RULES:
- A controller with repository_deps > 0 -> "layer_skip_in_layered" (layered/mvc) or "outer_depends_on_inner_clean" (clean)
- A controller with has_business_logic=True -> "business_logic_in_controller_layered" (layered/mvc)
- A controller with has_http_handling=True but has_validation=False -> "no_validation"
- A service with has_data_access=True but has_transaction=False -> "missing_transaction_in_layered" (layered/mvc)
- A service with controller_deps > 0 -> "reversed_dependency_in_layered" (layered/mvc)
- uses_new_keyword=True -> "tight_coupling_new_keyword"
- has_broad_catch=True -> "broad_catch"
- For hexagonal: service with repository_deps > 0 and no port_deps -> "missing_port_adapter_in_hexagonal"
- For hexagonal: domain class with many framework annotations -> "framework_dependency_in_domain_hexagonal"
- For clean: usecase/service with repository_deps > 0 -> "missing_gateway_interface_clean"
- For clean: entity with annotations > 3 -> "entity_framework_coupling_clean"
- A file can have MULTIPLE anti-patterns simultaneously
- If the file is genuinely clean (no violations indicated by metrics), return "clean"

IMPORTANT: Only detect anti-patterns CLEARLY indicated by the metrics. Do not guess.

Respond with ONLY a valid JSON array. Each element must have:
- "anti_pattern": one of the valid anti-pattern IDs above, or "clean"
- "confidence": float 0.0-1.0
- "reasoning": one sentence explaining which metrics led to this detection

Example:
[
  {{"anti_pattern": "layer_skip_in_layered", "confidence": 0.92, "reasoning": "Controller has repository_deps=2 indicating direct repository access"}},
  {{"anti_pattern": "no_validation", "confidence": 0.85, "reasoning": "Controller has has_http_handling=True but has_validation=False"}}
]

If the file is clean:
[{{"anti_pattern": "clean", "confidence": 0.90, "reasoning": "No violation signals detected in metrics"}}]"""


def _parse_json_response(text: str) -> list:
    """Parse a JSON array from Gemini response, handling markdown fences."""
    if not text:
        return []

    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines).strip()

    try:
        result = json.loads(cleaned)
        if isinstance(result, list):
            return result
        return []
    except json.JSONDecodeError as e:
        print(f"  [GeminiDetection] JSON parse error: {e}")
        print(f"  [GeminiDetection] Raw text: {cleaned[:500]}")
        return []


def detect_with_gemini(features: dict, ml_prediction: str, ml_confidence: float, architecture: str) -> list:
    """
    Call Gemini to detect anti-patterns for a single file.

    Returns list of dicts: [{anti_pattern, confidence, reasoning, detection_source}, ...]
    Returns empty list on failure (caller should fall through to rule-based).
    """
    print(f"\n  [GeminiDetection] Calling Gemini for '{features.get('file_name', 'unknown')}' "
          f"(ML said '{ml_prediction}' @ {ml_confidence:.0%})...")

    prompt = _build_detection_prompt(features, ml_prediction, ml_confidence, architecture)
    raw_response = _call_gemini(prompt)

    if not raw_response:
        print("  [GeminiDetection] Gemini returned empty response")
        return []

    detections = _parse_json_response(raw_response)
    if not detections:
        return []

    # Validate against valid pattern list + "clean"
    valid_patterns = set(ARCHITECTURE_ANTIPATTERNS.get(architecture, ARCHITECTURE_ANTIPATTERNS["layered"]))
    valid_patterns.add("clean")

    validated = []
    for d in detections:
        ap = d.get("anti_pattern", "")
        if ap not in valid_patterns:
            print(f"  [GeminiDetection] Skipping invalid pattern '{ap}'")
            continue
        validated.append({
            "anti_pattern": ap,
            "confidence": float(d.get("confidence", 0.7)),
            "reasoning": d.get("reasoning", ""),
            "detection_source": "gemini_ai",
        })

    print(f"  [GeminiDetection] Gemini returned {len(validated)} detection(s)")
    return validated


# ═══════════════════════════════════════════════════════════════════════
# RULE-BASED FALLBACK (last resort)
# ═══════════════════════════════════════════════════════════════════════

def detect_with_rules(features: dict, architecture: str) -> list:
    """
    Rule-based anti-pattern detection from metrics alone.
    Used when both ML model is suspicious AND Gemini is unavailable.
    """
    detections = []
    layer = str(features.get("layer", "")).lower().strip()
    valid_patterns = set(ARCHITECTURE_ANTIPATTERNS.get(architecture, ARCHITECTURE_ANTIPATTERNS["layered"]))

    # Controller with repository deps -> layer skip / outer depends on inner
    if layer == "controller" and features.get("repository_deps", 0) > 0:
        if "layer_skip_in_layered" in valid_patterns:
            detections.append({
                "anti_pattern": "layer_skip_in_layered",
                "confidence": 0.85,
                "reasoning": f"Controller has repository_deps={features.get('repository_deps', 0)} indicating direct repository access",
                "detection_source": "rule_based",
            })
        elif "outer_depends_on_inner_clean" in valid_patterns:
            detections.append({
                "anti_pattern": "outer_depends_on_inner_clean",
                "confidence": 0.85,
                "reasoning": f"Controller has repository_deps={features.get('repository_deps', 0)} violating dependency rule",
                "detection_source": "rule_based",
            })

    # Controller with business logic
    if layer == "controller" and features.get("has_business_logic"):
        if "business_logic_in_controller_layered" in valid_patterns:
            detections.append({
                "anti_pattern": "business_logic_in_controller_layered",
                "confidence": 0.80,
                "reasoning": "Controller has has_business_logic=True",
                "detection_source": "rule_based",
            })

    # Controller without validation
    if layer == "controller" and features.get("has_http_handling") and not features.get("has_validation"):
        if "no_validation" in valid_patterns:
            detections.append({
                "anti_pattern": "no_validation",
                "confidence": 0.80,
                "reasoning": "Controller has has_http_handling=True but has_validation=False",
                "detection_source": "rule_based",
            })

    # Service with reversed dependency
    if layer == "service" and features.get("controller_deps", 0) > 0:
        if "reversed_dependency_in_layered" in valid_patterns:
            detections.append({
                "anti_pattern": "reversed_dependency_in_layered",
                "confidence": 0.90,
                "reasoning": f"Service has controller_deps={features.get('controller_deps', 0)}",
                "detection_source": "rule_based",
            })

    # Service writes without transaction
    if layer == "service" and features.get("has_data_access") and not features.get("has_transaction"):
        if "missing_transaction_in_layered" in valid_patterns:
            detections.append({
                "anti_pattern": "missing_transaction_in_layered",
                "confidence": 0.85,
                "reasoning": "Service has has_data_access=True but has_transaction=False",
                "detection_source": "rule_based",
            })

    # Hexagonal: service with repository deps
    if layer == "service" and features.get("repository_deps", 0) > 0:
        if "missing_port_adapter_in_hexagonal" in valid_patterns:
            detections.append({
                "anti_pattern": "missing_port_adapter_in_hexagonal",
                "confidence": 0.85,
                "reasoning": f"Service has repository_deps={features.get('repository_deps', 0)} without port abstraction",
                "detection_source": "rule_based",
            })

    # Hexagonal: framework dependency in domain
    if layer in ("service", "entity") and features.get("annotations", 0) > 3:
        if "framework_dependency_in_domain_hexagonal" in valid_patterns:
            detections.append({
                "anti_pattern": "framework_dependency_in_domain_hexagonal",
                "confidence": 0.75,
                "reasoning": f"Domain layer file has {features.get('annotations', 0)} annotations suggesting framework coupling",
                "detection_source": "rule_based",
            })

    # Clean: usecase/service with repository deps
    if layer in ("service", "usecase") and features.get("repository_deps", 0) > 0:
        if "missing_gateway_interface_clean" in valid_patterns:
            detections.append({
                "anti_pattern": "missing_gateway_interface_clean",
                "confidence": 0.85,
                "reasoning": f"UseCase/Service has repository_deps={features.get('repository_deps', 0)} without gateway interface",
                "detection_source": "rule_based",
            })

    # Clean: entity framework coupling
    if layer == "entity" and features.get("annotations", 0) > 3:
        if "entity_framework_coupling_clean" in valid_patterns:
            detections.append({
                "anti_pattern": "entity_framework_coupling_clean",
                "confidence": 0.80,
                "reasoning": f"Entity has {features.get('annotations', 0)} annotations suggesting JPA coupling",
                "detection_source": "rule_based",
            })

    # Clean: usecase framework coupling
    if layer in ("service", "usecase") and features.get("annotations", 0) > 3:
        if "usecase_framework_coupling_clean" in valid_patterns:
            detections.append({
                "anti_pattern": "usecase_framework_coupling_clean",
                "confidence": 0.70,
                "reasoning": f"UseCase has {features.get('annotations', 0)} framework annotations",
                "detection_source": "rule_based",
            })

    # Adapter without port
    if layer == "adapter" and features.get("port_deps", 0) == 0:
        if "adapter_without_port_hexagonal" in valid_patterns:
            detections.append({
                "anti_pattern": "adapter_without_port_hexagonal",
                "confidence": 0.75,
                "reasoning": "Adapter has port_deps=0 suggesting no Port interface implemented",
                "detection_source": "rule_based",
            })

    # Tight coupling
    if features.get("uses_new_keyword"):
        if "tight_coupling_new_keyword" in valid_patterns:
            detections.append({
                "anti_pattern": "tight_coupling_new_keyword",
                "confidence": 0.90,
                "reasoning": "File uses 'new' keyword for dependency instantiation",
                "detection_source": "rule_based",
            })

    # Broad catch
    if features.get("has_broad_catch"):
        if "broad_catch" in valid_patterns:
            detections.append({
                "anti_pattern": "broad_catch",
                "confidence": 0.90,
                "reasoning": "File has broad exception catch (Exception/Throwable)",
                "detection_source": "rule_based",
            })

    if not detections:
        detections.append({
            "anti_pattern": "clean",
            "confidence": 0.50,
            "reasoning": "No clear violation signals in metrics (rule-based fallback)",
            "detection_source": "rule_based",
        })

    print(f"  [RuleBased] Detected {len(detections)} pattern(s) for '{features.get('file_name', 'unknown')}'")
    return detections


# ═══════════════════════════════════════════════════════════════════════
# MAIN ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════════════

def detect_antipattern(features: dict, ml_prediction: str, ml_confidence: float, architecture: str) -> list:
    """
    Three-tier anti-pattern detection for a single file.

    Returns a list of dicts, each with:
      - anti_pattern: str
      - confidence: float
      - detection_source: "ml_model" | "gemini_ai" | "rule_based"
      - reasoning: str (only for gemini_ai and rule_based)
    """
    # If ML prediction looks trustworthy, accept it
    if not should_use_fallback(ml_prediction, ml_confidence, features):
        return [{
            "anti_pattern": ml_prediction,
            "confidence": ml_confidence,
            "detection_source": "ml_model",
            "reasoning": None,
        }]

    print(f"\n  [Fallback] ML prediction '{ml_prediction}' ({ml_confidence:.0%}) flagged as suspicious "
          f"for '{features.get('file_name', 'unknown')}' — invoking Gemini fallback...")

    # Tier 2: Gemini AI
    gemini_results = detect_with_gemini(features, ml_prediction, ml_confidence, architecture)
    if gemini_results:
        return gemini_results

    # Tier 3: Rule-based heuristics
    print(f"  [Fallback] Gemini failed — falling back to rule-based detection")
    return detect_with_rules(features, architecture)


def detect_antipatterns_batch(files_with_predictions: list, architecture: str) -> dict:
    """
    Batch detection for multiple files with parallel Gemini calls.

    Args:
        files_with_predictions: List of dicts, each with:
            - All file features (from FileFeatures.dict())
            - _ml_prediction: str
            - _ml_confidence: float
        architecture: Architecture pattern string

    Returns:
        Dict mapping file_name -> list of detection results
    """
    results = {}
    suspicious_files = []

    for fd in files_with_predictions:
        ml_pred = fd.get("_ml_prediction", "clean")
        ml_conf = fd.get("_ml_confidence", 1.0)
        fname = fd.get("file_name", "unknown")

        if not should_use_fallback(ml_pred, ml_conf, fd):
            results[fname] = [{
                "anti_pattern": ml_pred,
                "confidence": ml_conf,
                "detection_source": "ml_model",
                "reasoning": None,
            }]
        else:
            suspicious_files.append(fd)

    if not suspicious_files:
        return results

    print(f"\n  [Fallback] {len(suspicious_files)}/{len(files_with_predictions)} files flagged — "
          f"running Gemini fallback in parallel...")

    # Parallel Gemini calls for suspicious files
    max_workers = min(5, len(suspicious_files))

    def _detect_one(fd):
        return (
            fd.get("file_name", "unknown"),
            detect_antipattern(fd, fd["_ml_prediction"], fd["_ml_confidence"], architecture)
        )

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_detect_one, fd): fd for fd in suspicious_files}
        for future in as_completed(futures):
            try:
                fname, detections = future.result()
                results[fname] = detections
            except Exception as exc:
                fd = futures[future]
                fname = fd.get("file_name", "unknown")
                print(f"  [Fallback] Worker error for {fname}: {exc}")
                # Last resort: rule-based
                results[fname] = detect_with_rules(fd, architecture)

    return results


# ═══════════════════════════════════════════════════════════════════════
# QUALITY SCORE ADJUSTMENT
# ═══════════════════════════════════════════════════════════════════════

def adjust_quality_for_detections(base_score: float, detections: list) -> tuple:
    """
    Adjust a file's quality score based on fallback-detected anti-patterns.

    Args:
        base_score: Original ML-predicted quality score
        detections: List of detection dicts from detect_antipattern()

    Returns:
        (adjusted_score, adjustment_reason) — score clamped to [0, 100]
    """
    # Only adjust for non-ML detections (Gemini or rule-based found something ML missed)
    fallback_patterns = [
        d for d in detections
        if d["detection_source"] in ("gemini_ai", "rule_based") and d["anti_pattern"] != "clean"
    ]

    if not fallback_patterns:
        return base_score, None

    total_penalty = 0
    pattern_names = []
    for d in fallback_patterns:
        ctx = ANTI_PATTERN_CONTEXT.get(d["anti_pattern"], {})
        impact = ctx.get("impact_pts", -5)
        total_penalty += impact  # impact_pts are negative
        display = DISPLAY_NAMES.get(d["anti_pattern"], d["anti_pattern"])
        pattern_names.append(f"{display} ({impact}pts)")

    adjusted = max(0, min(100, base_score + total_penalty))
    reason = (
        f"Score adjusted from {base_score:.1f} to {adjusted:.1f} due to "
        f"{len(fallback_patterns)} fallback-detected pattern(s): {', '.join(pattern_names)}"
    )

    print(f"  [QualityAdjust] {reason}")
    return round(adjusted, 1), reason
