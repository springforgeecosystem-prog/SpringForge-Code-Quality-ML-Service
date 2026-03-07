"""
app/gemini_scoring_service.py
──────────────────────────────────────────────────────────────────
Hybrid quality scoring: ML model baseline + Gemini LLM assessment.

When anti-pattern validation results are available, this module asks
Gemini to evaluate the project's overall code quality considering:
  - Validated violations (type, severity, affected files)
  - Clean files confirmed by LLM
  - False positives filtered out
  - Architecture pattern and layering

Produces a hybrid score blending ML predictions with LLM analysis.
Falls back to ML-only scoring when source code is unavailable or
when the Gemini call fails.
──────────────────────────────────────────────────────────────────
"""

import json
import traceback
from typing import Dict, List, Optional

from app.gemini_fix_service import _call_gemini


# ── Severity penalties for rule-based per-file adjustments ─────────────────
SEVERITY_PENALTIES = {
    "CRITICAL": 15,
    "HIGH":     10,
    "MEDIUM":    5,
    "LOW":       2,
}
CLEAN_VALIDATED_BONUS  = 5   # file confirmed clean by LLM
FALSE_POSITIVE_BONUS   = 3   # ML was wrong, LLM cleared it


# ── Score label helper (mirrors quality_model_loader) ──────────────────────

def _score_label(score: float):
    for threshold, label, emoji in [
        (90, 'Excellent', '🟢'),
        (75, 'Good',      '🟢'),
        (60, 'Fair',      '🟠'),
        (40, 'Poor',      '🔴'),
        (0,  'Critical',  '🔴'),
    ]:
        if score >= threshold:
            return label, emoji
    return 'Critical', '🔴'


# ── Prompt builder ─────────────────────────────────────────────────────────

def _build_scoring_prompt(
    architecture: str,
    file_summaries: List[dict],
    validated_violations: List[dict],
    clean_files: List[str],
    false_positives_filtered: int,
    ml_overall_score: float,
) -> str:
    """Build a prompt for Gemini to assess project quality."""

    files_section = []
    for fs in file_summaries:
        entry = f"- {fs['file_name']} (layer: {fs['layer']}, ML score: {fs['ml_score']:.0f}/100)"
        if fs.get('violations'):
            entry += f" — violations: {', '.join(fs['violations'])}"
        else:
            entry += " — clean"
        files_section.append(entry)

    violations_section = []
    for v in validated_violations:
        violations_section.append(
            f"- {v['type']} [severity: {v['severity']}] → files: {', '.join(v['files'])}"
            f"  (LLM validated: {v.get('llm_validated', False)})"
        )

    return f"""You are a senior Java architect evaluating the quality of a Spring Boot project.
Your task: assess the code quality based on the analysis findings below and provide accurate quality scores.

PROJECT ANALYSIS:
  Architecture: {architecture}
  Total files: {len(file_summaries)}
  ML model overall score: {ml_overall_score:.0f}/100
  Confirmed violations: {len(validated_violations)}
  Clean files: {len(clean_files)}
  False positives filtered: {false_positives_filtered}

FILES:
{chr(10).join(files_section)}

CONFIRMED VIOLATIONS:
{chr(10).join(violations_section) if violations_section else "None — all files passed validation."}

SCORING GUIDELINES:
- If there are NO violations and the architecture is clean, score should be 90-100
- Each CRITICAL violation: roughly -15 points from perfect
- Each HIGH violation: roughly -10 points
- Each MEDIUM violation: roughly -5 points
- Each LOW violation: roughly -2 points
- Good layering and separation of concerns should boost the score
- The ML score of {ml_overall_score:.0f}/100 is a baseline from static metrics only — adjust it based on actual violation findings
- If the ML model says 80 but there are NO violations, the true quality is likely higher (85-95+)
- If the ML model says 80 but there are CRITICAL violations, the true quality is likely lower (50-70)

Respond in this EXACT JSON format only (no markdown fences, no extra text):
{{
  "overall_score": <number 0-100>,
  "reasoning": "<one paragraph explaining the score>",
  "file_scores": {{
    "<file_name>": <number 0-100>,
    ...
  }},
  "strengths": ["<strength1>", "<strength2>"],
  "improvements": ["<improvement1>", "<improvement2>"]
}}"""


# ── JSON response parser ──────────────────────────────────────────────────

def _parse_scoring_response(raw: str) -> Optional[dict]:
    """Parse Gemini's quality scoring JSON response."""
    text = raw.strip()
    # Strip markdown fences
    if "```" in text:
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end   = text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass
    return None


# ── Main entry points ─────────────────────────────────────────────────────

def get_llm_quality_assessment(
    architecture: str,
    file_summaries: List[dict],
    validated_violations: List[dict],
    clean_files: List[str],
    false_positives_filtered: int,
    ml_overall_score: float,
) -> Optional[dict]:
    """
    Call Gemini to assess project quality.

    Returns dict with:
        overall_score  : float (0–100)
        reasoning      : str
        file_scores    : dict {file_name: score}
        strengths      : list[str]
        improvements   : list[str]
    Returns None if the Gemini call fails.
    """
    prompt = _build_scoring_prompt(
        architecture=architecture,
        file_summaries=file_summaries,
        validated_violations=validated_violations,
        clean_files=clean_files,
        false_positives_filtered=false_positives_filtered,
        ml_overall_score=ml_overall_score,
    )

    try:
        print("\n  [★ Hybrid Scoring] Calling Gemini for quality assessment...")
        raw = _call_gemini(prompt)
        if not raw:
            print("  [★ Hybrid Scoring] ⚠️ Gemini returned empty — using ML-only scores")
            return None

        result = _parse_scoring_response(raw)
        if result and "overall_score" in result:
            print(f"  [★ Hybrid Scoring] ✅ Gemini score: {result['overall_score']}/100")
            return result

        print("  [★ Hybrid Scoring] ⚠️ Could not parse Gemini scoring response")
        return None
    except Exception as e:
        print(f"  [★ Hybrid Scoring] ⚠️ Gemini scoring failed: {e}")
        traceback.print_exc()
        return None


def compute_hybrid_file_scores(
    ml_file_scores: Dict[str, float],
    llm_assessment: Optional[dict],
    file_violations: Dict[str, List[str]],
    clean_files: List[str],
    false_positive_files: List[str],
    llm_validated: bool,
    ml_weight: float = 0.4,
    llm_weight: float = 0.6,
) -> Dict[str, dict]:
    """
    Compute per-file hybrid quality scores.

    Parameters
    ----------
    ml_file_scores      : {file_name: ml_score}
    llm_assessment      : Gemini response (may be None)
    file_violations     : {file_name: [severity1, severity2, ...]}
    clean_files         : files confirmed clean
    false_positive_files: files where ML was wrong (cleared by LLM)
    llm_validated       : whether LLM validation was performed
    ml_weight / llm_weight : blending weights (must sum to 1.0)

    Returns
    -------
    {file_name: {quality_score, quality_label, quality_emoji, quality_display, scoring_method}}
    """
    llm_file_scores = {}
    if llm_assessment and "file_scores" in llm_assessment:
        llm_file_scores = llm_assessment["file_scores"]

    results = {}
    for file_name, ml_score in ml_file_scores.items():
        if llm_validated and file_name in llm_file_scores:
            # Full hybrid: blend ML + LLM per-file scores
            try:
                llm_score = float(llm_file_scores[file_name])
            except (ValueError, TypeError):
                llm_score = ml_score
            hybrid = ml_weight * ml_score + llm_weight * llm_score
            method = "hybrid"

        elif llm_validated:
            # LLM didn't score this file individually — rule-based adjustment
            hybrid = ml_score
            if file_name in file_violations:
                for severity in file_violations[file_name]:
                    hybrid -= SEVERITY_PENALTIES.get(severity, 0)
            if file_name in clean_files:
                hybrid += CLEAN_VALIDATED_BONUS
            if file_name in false_positive_files:
                hybrid += FALSE_POSITIVE_BONUS
            method = "ml_adjusted"

        else:
            # No LLM — pure ML score
            hybrid = ml_score
            method = "ml_only"

        hybrid = round(max(0.0, min(100.0, hybrid)), 1)
        label, emoji = _score_label(hybrid)
        results[file_name] = {
            "quality_score":   hybrid,
            "quality_label":   label,
            "quality_emoji":   emoji,
            "quality_display": f"{emoji} {label} ({hybrid:.0f}/100)",
            "scoring_method":  method,
        }

    return results


def compute_hybrid_overall(
    ml_overall: float,
    llm_assessment: Optional[dict],
    ml_weight: float = 0.4,
    llm_weight: float = 0.6,
) -> float:
    """Compute final hybrid overall score from ML + LLM."""
    if llm_assessment and "overall_score" in llm_assessment:
        try:
            llm_score = float(llm_assessment["overall_score"])
            return round(ml_weight * ml_overall + llm_weight * llm_score, 1)
        except (ValueError, TypeError):
            pass
    return round(ml_overall, 1)
