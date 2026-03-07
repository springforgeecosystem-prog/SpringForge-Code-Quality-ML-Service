"""
app/gemini_validation_service.py
──────────────────────────────────────────────────────────────────
LLM-powered validation of ML anti-pattern predictions.

When the IDE plugin sends actual Java source code alongside metrics,
this module asks Gemini to:
  1. Validate whether the ML-predicted anti-pattern is genuinely present
     in the code (filters false positives).
  2. Generate a detailed violation description referencing actual
     class names, field names, and method names from the code.
  3. Produce a context-aware fix suggestion using real project code.

Falls back gracefully — if Gemini is unavailable or source code is
not provided, the pipeline returns ML-only results unchanged.
──────────────────────────────────────────────────────────────────
"""

import json
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.gemini_fix_service import (
    _call_gemini,
    ANTI_PATTERN_CONTEXT,
    DISPLAY_NAMES,
)


# ── Prompt builders ────────────────────────────────────────────────────────

def _truncate_source(code: str, max_lines: int = 300) -> str:
    """Keep source code to a reasonable size for the prompt."""
    lines = code.splitlines()
    if len(lines) <= max_lines:
        return code
    return "\n".join(lines[:max_lines]) + f"\n// ... ({len(lines) - max_lines} more lines truncated)"


def _display_name(anti_pattern: str) -> str:
    return DISPLAY_NAMES.get(anti_pattern, anti_pattern.replace("_", " ").title())


def build_validation_prompt(
    anti_pattern: str,
    source_files: dict,        # {file_name: source_code}
    architecture: str,
    layer: str,
    confidence: float,
    severity: str,
    ml_description: str,
) -> str:
    """
    Build a prompt that asks Gemini to validate an ML prediction
    against the actual source code.
    """
    display = _display_name(anti_pattern)
    ctx = ANTI_PATTERN_CONTEXT.get(anti_pattern, {})

    # Build file source code section
    file_sections = []
    for fname, code in source_files.items():
        truncated = _truncate_source(code)
        file_sections.append(f"=== {fname} ===\n{truncated}")
    source_block = "\n\n".join(file_sections)

    # What to look for — architecture-specific guidance
    pattern_guidance = ctx.get("problem", ml_description)

    return f"""You are a senior Spring Boot code reviewer specializing in {architecture} architecture.

An ML model has analyzed a Java project and predicted the following anti-pattern:

PREDICTED ANTI-PATTERN: {display}
ANTI-PATTERN TYPE: {anti_pattern}
ARCHITECTURE: {architecture}
AFFECTED LAYER: {layer}
ML CONFIDENCE: {confidence:.0%}
SEVERITY: {severity}
ML DESCRIPTION: {ml_description}

WHAT THIS ANTI-PATTERN MEANS:
{pattern_guidance}

HERE IS THE ACTUAL SOURCE CODE OF THE AFFECTED FILES:

{source_block}

YOUR TASK:
1. Carefully examine the actual source code above.
2. Determine whether the predicted anti-pattern "{display}" is GENUINELY PRESENT in this code.
3. Pay special attention to:
   - For "no_validation": Check if @Valid is ALREADY present on @RequestBody parameters. If @Valid is already there, this is a FALSE POSITIVE.
   - For "missing_transaction_in_layered": Check if @Transactional is ALREADY present on service methods. If it is, this is a FALSE POSITIVE.
   - For "layer_skip_in_layered": Check if the controller ACTUALLY injects a Repository directly. If it only injects Services, this is a FALSE POSITIVE.
   - For "business_logic_in_controller_layered": Check if the controller ACTUALLY contains business logic (loops, calculations, conditionals beyond simple delegation). Simple request delegation is NOT business logic.
   - For hexagonal/clean patterns: Check if the actual imports and dependencies match the violation claim.
4. If the anti-pattern IS genuinely present: provide a detailed description and fix suggestion using the ACTUAL class names, method names, and field names from the source code.
5. If the anti-pattern is NOT present (false positive): explain exactly why the code is actually correct.

RESPOND WITH ONLY THIS JSON (no markdown, no code fences, no extra text):
{{
  "is_valid": true or false,
  "reasoning": "Brief explanation of why the prediction is correct or incorrect, referencing specific code elements",
  "description": "If is_valid=true: Detailed violation description using actual class/method names from the code. If is_valid=false: empty string",
  "recommendation": "If is_valid=true: Specific actionable fix recommendation using actual class/method names. If is_valid=false: empty string",
  "before_code": "If is_valid=true: The actual problematic code snippet from the source. If is_valid=false: empty string",
  "after_code": "If is_valid=true: The corrected code using actual class names from the project. If is_valid=false: empty string",
  "severity": "{severity}"
}}"""


def build_clean_check_prompt(
    file_name: str,
    source_code: str,
    architecture: str,
    layer: str,
) -> str:
    """
    For files predicted 'clean' with low confidence, ask Gemini
    if any anti-patterns were missed by the ML model.
    """
    truncated = _truncate_source(source_code)

    return f"""You are a senior Spring Boot code reviewer specializing in {architecture} architecture.

An ML model predicted this file as CLEAN (no anti-patterns), but the confidence was low.
Please review the code and check if any architectural anti-patterns were missed.

FILE: {file_name}
ARCHITECTURE: {architecture}
LAYER: {layer}

SOURCE CODE:
{truncated}

ANTI-PATTERNS TO CHECK FOR ({architecture}):
- no_validation: Missing @Valid on @RequestBody parameters in controllers
- layer_skip: Controller directly injecting Repository (bypassing Service)
- missing_transaction: Service methods doing DB writes without @Transactional
- business_logic_in_controller: Complex logic (loops, calculations) in controller instead of service
- reversed_dependency: Service depending on Controller
- tight_coupling: Using 'new' keyword to instantiate dependencies instead of injection
- broad_catch: Catching generic Exception/Throwable instead of specific exceptions

RESPOND WITH ONLY THIS JSON (no markdown, no code fences, no extra text):
{{
  "has_issues": true or false,
  "anti_patterns": [
    {{
      "type": "anti_pattern_type_from_list_above",
      "severity": "CRITICAL|HIGH|MEDIUM|LOW",
      "description": "Description referencing actual code",
      "recommendation": "Fix recommendation using actual class names",
      "before_code": "Problematic code snippet",
      "after_code": "Fixed code snippet"
    }}
  ]
}}

If the code is genuinely clean, return: {{"has_issues": false, "anti_patterns": []}}"""


# ── JSON response parser ──────────────────────────────────────────────────

def _parse_gemini_json(text: str) -> dict:
    """
    Parse JSON from Gemini response, handling markdown fences and
    other formatting artifacts.
    """
    if not text:
        return {}

    # Strip markdown code fences if present
    cleaned = text.strip()
    if cleaned.startswith("```"):
        # Remove opening fence (```json or ```)
        first_newline = cleaned.index("\n") if "\n" in cleaned else len(cleaned)
        cleaned = cleaned[first_newline + 1:]
        # Remove closing fence
        if cleaned.rstrip().endswith("```"):
            cleaned = cleaned.rstrip()[:-3].rstrip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Try to find JSON object in the text
        start = cleaned.find("{")
        end = cleaned.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(cleaned[start:end])
            except json.JSONDecodeError:
                pass
        print(f"  [Validation] ❌ Could not parse Gemini JSON response: {text[:200]}")
        return {}


# ── Single prediction validator ───────────────────────────────────────────

def validate_prediction(
    anti_pattern_type: str,
    files_with_code: dict,     # {file_name: source_code}
    architecture: str,
    layer: str,
    confidence: float,
    severity: str,
    ml_description: str,
) -> dict:
    """
    Validate a single ML prediction against actual source code using Gemini.

    Returns:
        {
            "is_valid": bool,
            "reasoning": str,
            "description": str,       # rich description if valid
            "recommendation": str,    # context-aware recommendation if valid
            "before_code": str,       # actual problematic code if valid
            "after_code": str,        # fixed code if valid
            "severity": str,
            "llm_validated": True,
        }

    On Gemini failure, returns a fallback dict with llm_validated=False.
    """
    prompt = build_validation_prompt(
        anti_pattern=anti_pattern_type,
        source_files=files_with_code,
        architecture=architecture,
        layer=layer,
        confidence=confidence,
        severity=severity,
        ml_description=ml_description,
    )

    print(f"\n  [Validation] Validating '{anti_pattern_type}' "
          f"(conf={confidence:.0%}, files={list(files_with_code.keys())})")

    gemini_text = _call_gemini(prompt)
    parsed = _parse_gemini_json(gemini_text)

    if not parsed:
        # Gemini failed — return unvalidated (ML-only result stands)
        print(f"  [Validation] ⚠️ Gemini returned no parseable result for '{anti_pattern_type}' — keeping ML prediction")
        return {
            "is_valid": True,          # keep the ML prediction when we can't validate
            "reasoning": "LLM validation unavailable — ML prediction retained as-is",
            "description": "",
            "recommendation": "",
            "before_code": "",
            "after_code": "",
            "severity": severity,
            "llm_validated": False,
        }

    return {
        "is_valid": parsed.get("is_valid", True),
        "reasoning": parsed.get("reasoning", ""),
        "description": parsed.get("description", ""),
        "recommendation": parsed.get("recommendation", ""),
        "before_code": parsed.get("before_code", ""),
        "after_code": parsed.get("after_code", ""),
        "severity": parsed.get("severity", severity),
        "llm_validated": True,
    }


# ── Batch validator (parallel) ────────────────────────────────────────────

def validate_all_predictions(
    grouped_predictions: dict,
    files_map: dict,           # {file_name: source_code}
    architecture: str,
) -> dict:
    """
    Validate all ML predictions in parallel using Gemini.

    Args:
        grouped_predictions: {
            anti_pattern_type: {
                "files": [file_name, ...],
                "layers": {layer_set},
                "confidences": [float, ...],
                "severity": str,
                "description": str,
            }
        }
        files_map: {file_name: source_code} for all files with code
        architecture: architecture pattern string

    Returns:
        {
            anti_pattern_type: {
                "is_valid": bool,
                "reasoning": str,
                "description": str,
                "recommendation": str,
                "before_code": str,
                "after_code": str,
                "severity": str,
                "llm_validated": bool,
            }
        }
    """
    if not grouped_predictions:
        return {}

    results = {}

    def _validate_one(ap_type: str, ap_data: dict) -> tuple:
        # Collect source code for affected files
        affected_sources = {}
        for fname in ap_data["files"]:
            if fname in files_map and files_map[fname]:
                affected_sources[fname] = files_map[fname]

        if not affected_sources:
            # No source code for any affected file — skip validation
            print(f"  [Validation] ⚠️ No source code for '{ap_type}' affected files — skipping validation")
            return ap_type, {
                "is_valid": True,
                "reasoning": "No source code available for validation",
                "description": "",
                "recommendation": "",
                "before_code": "",
                "after_code": "",
                "severity": ap_data.get("severity", "MEDIUM"),
                "llm_validated": False,
            }

        avg_conf = sum(ap_data["confidences"]) / len(ap_data["confidences"])
        layer = ", ".join(sorted(ap_data["layers"])) if isinstance(ap_data["layers"], set) else str(ap_data.get("layers", "unknown"))

        result = validate_prediction(
            anti_pattern_type=ap_type,
            files_with_code=affected_sources,
            architecture=architecture,
            layer=layer,
            confidence=avg_conf,
            severity=ap_data.get("severity", "MEDIUM"),
            ml_description=ap_data.get("description", ""),
        )
        return ap_type, result

    max_workers = min(5, len(grouped_predictions))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_ap = {
            executor.submit(_validate_one, ap_type, ap_data): ap_type
            for ap_type, ap_data in grouped_predictions.items()
        }
        for future in as_completed(future_to_ap):
            ap_type = future_to_ap[future]
            try:
                _, result = future.result()
                results[ap_type] = result
            except Exception as exc:
                print(f"  [Validation] ❌ Worker error for '{ap_type}': {exc}")
                traceback.print_exc()
                results[ap_type] = {
                    "is_valid": True,
                    "reasoning": f"Validation worker error: {exc}",
                    "description": "",
                    "recommendation": "",
                    "before_code": "",
                    "after_code": "",
                    "severity": grouped_predictions[ap_type].get("severity", "MEDIUM"),
                    "llm_validated": False,
                }

    return results


# ── Clean file checker ────────────────────────────────────────────────────

def check_clean_predictions(
    clean_files_with_code: dict,    # {file_name: {"source_code": str, "layer": str}}
    architecture: str,
    confidence_threshold: float = 0.70,
    clean_confidences: dict = None, # {file_name: confidence}
) -> list:
    """
    For files predicted 'clean' with low confidence, ask Gemini
    if the ML model missed any anti-patterns.

    Returns a list of newly discovered anti-pattern dicts.
    """
    if not clean_files_with_code:
        return []

    # Only check files with low confidence
    files_to_check = {}
    for fname, fdata in clean_files_with_code.items():
        conf = (clean_confidences or {}).get(fname, 1.0)
        if conf < confidence_threshold:
            files_to_check[fname] = fdata

    if not files_to_check:
        return []

    print(f"  [Validation] Checking {len(files_to_check)} low-confidence 'clean' predictions...")

    discovered = []

    def _check_one(fname: str, fdata: dict) -> list:
        prompt = build_clean_check_prompt(
            file_name=fname,
            source_code=fdata["source_code"],
            architecture=architecture,
            layer=fdata.get("layer", "unknown"),
        )
        gemini_text = _call_gemini(prompt)
        parsed = _parse_gemini_json(gemini_text)

        if not parsed or not parsed.get("has_issues"):
            return []

        results = []
        for ap in parsed.get("anti_patterns", []):
            if ap.get("type"):
                results.append({
                    "type": ap["type"],
                    "severity": ap.get("severity", "MEDIUM"),
                    "file": fname,
                    "layer": fdata.get("layer", "unknown"),
                    "description": ap.get("description", ""),
                    "recommendation": ap.get("recommendation", ""),
                    "before_code": ap.get("before_code", ""),
                    "after_code": ap.get("after_code", ""),
                    "llm_validated": True,
                    "discovered_by_llm": True,
                })
        return results

    max_workers = min(5, len(files_to_check))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_fname = {
            executor.submit(_check_one, fname, fdata): fname
            for fname, fdata in files_to_check.items()
        }
        for future in as_completed(future_to_fname):
            try:
                discovered.extend(future.result())
            except Exception as exc:
                fname = future_to_fname[future]
                print(f"  [Validation] ❌ Clean-check worker error for '{fname}': {exc}")

    if discovered:
        print(f"  [Validation] 🔍 Found {len(discovered)} missed anti-patterns in 'clean' files")
    return discovered
