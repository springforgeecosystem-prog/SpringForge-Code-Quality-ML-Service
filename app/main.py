"""
app/main.py
──────────────────────────────────────────────────────────────────
SpringForge AI-Driven Code Quality ML Service
FastAPI application exposing:

  EXISTING (Anti-Pattern Classification):
    GET  /                          Health check
    POST /predict-antipattern       Single file anti-pattern prediction
    POST /analyze-project           Multi-file anti-pattern analysis

  EXISTING (Quality Score Regression):
    POST /predict-quality-score     Single file quality score prediction
    POST /analyze-quality           Multi-file quality score analysis

  EXISTING (Combined):
    POST /analyze-project-full      Combined anti-pattern + quality score

  NEW (AI Fix Suggestions — Gemini):
    POST /generate-fix              Fix suggestion for one anti-pattern
    POST /generate-fixes            Fix suggestions for full project
──────────────────────────────────────────────────────────────────
"""

import os
from datetime import datetime
from typing  import List
from collections import defaultdict

# Load .env file for local development (ignored in production where env vars
# are set directly in the platform — e.g. Railway, Render, Docker).
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException

from app.schemas import (
    # existing
    AntiPatternInput, FileAnalysisInput, EnhancedPredictionResult,
    # quality score
    QualityScoreInput, QualityScoreResult,
    FileQualityResult, LayerQualitySummary, ProjectQualityResult,
    # combined
    CombinedAnalysisResult,
    # shared
    FileFeatures, AntiPatternDetail,
    # fix suggestions
    SingleFixRequest, FixRequest, FixSuggestion, ProjectFixResult,
)
from app.model_loader              import AntiPatternModel
from app.quality_model_loader      import QualityScoreModel
from app.gemini_fix_service        import generate_project_fixes, generate_fix_suggestion
from app.gemini_detection_service  import (
    detect_antipattern,
    detect_antipatterns_batch,
    adjust_quality_for_detections,
    should_use_fallback,
)

# ── Startup ────────────────────────────────────────────────────────────────
app = FastAPI(
    title       = "SpringForge AI-Driven Code Quality ML Service",
    description = "Anti-Pattern Classification + Quality Score + Gemini Fix Suggestions",
    version     = "2.1.0",
)

antipattern_model = AntiPatternModel()
quality_model     = QualityScoreModel()


# ── Health check ───────────────────────────────────────────────────────────
@app.get("/")
def home():
    gemini_configured = bool(os.getenv("GEMINI_API_KEY"))
    return {
        "status"           : "SpringForge ML Service Running",
        "version"          : "2.1.0",
        "gemini_configured": gemini_configured,
        "models"           : [
            "Anti-Pattern Classifier",
            "Quality Score Regressor",
            "Gemini Fix Suggestion Generator",
        ],
    }


# ─────────────────────────────────────────────────────────────────
# ANTI-PATTERN ENDPOINTS
# ─────────────────────────────────────────────────────────────────

@app.post("/predict-antipattern")
def predict_antipattern(input_data: AntiPatternInput):
    features = input_data.dict()
    ml_pred, ml_conf = antipattern_model.predict_with_confidence(features)
    architecture = features.get("architecture_pattern", "layered")

    detections = detect_antipattern(features, ml_pred, ml_conf, architecture)
    # Return primary detection (highest confidence non-clean, or first)
    primary = detections[0]
    return {
        "anti_pattern": primary["anti_pattern"],
        "confidence": round(primary["confidence"], 2),
        "detection_source": primary["detection_source"],
    }


@app.post("/analyze-project", response_model=EnhancedPredictionResult)
def analyze_project(input_data: FileAnalysisInput):
    files = input_data.files
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    architecture = files[0].architecture_pattern
    gemini_fallback_used = False

    # Step 1: ML predictions for all files
    files_with_preds = []
    for f in files:
        features = f.dict()
        ml_pred, ml_conf = antipattern_model.predict_with_confidence(features)
        features["_ml_prediction"] = ml_pred
        features["_ml_confidence"] = ml_conf
        files_with_preds.append(features)

    # Step 2: Run fallback detection (parallel Gemini for suspicious files)
    all_detections = detect_antipatterns_batch(files_with_preds, architecture)

    # Step 3: Aggregate violations
    ap_violations: dict = defaultdict(lambda: {
        'files': [], 'layers': set(), 'confidences': [],
        'detection_source': 'ml_model', 'reasoning': None
    })
    clean_files: List[str] = []

    for f in files:
        fname = f.file_name
        detections = all_detections.get(fname, [])
        file_is_clean = True

        for d in detections:
            ap = d["anti_pattern"]
            if ap == "clean":
                continue
            file_is_clean = False
            layer = antipattern_model.detect_layer(f.dict())
            ap_violations[ap]['files'].append(fname)
            ap_violations[ap]['layers'].add(layer)
            ap_violations[ap]['confidences'].append(d["confidence"])
            # Track detection source (gemini_ai/rule_based take priority over ml_model)
            if d["detection_source"] in ("gemini_ai", "rule_based"):
                ap_violations[ap]['detection_source'] = d["detection_source"]
                ap_violations[ap]['reasoning'] = d.get("reasoning")
                gemini_fallback_used = True

        if file_is_clean:
            clean_files.append(fname)

    # Step 4: Build response
    ap_details: List[AntiPatternDetail] = []
    for ap, data in ap_violations.items():
        info = antipattern_model.ANTI_PATTERN_INFO.get(ap, {
            "severity": "UNKNOWN", "description": "Unknown anti-pattern",
            "recommendation": "Review manually"})
        avg_conf = sum(data['confidences']) / len(data['confidences'])
        ap_details.append(AntiPatternDetail(
            type=ap, severity=info['severity'],
            affected_layer=", ".join(sorted(data['layers'])),
            confidence=round(avg_conf, 2), files=data['files'],
            description=info['description'], recommendation=info['recommendation'],
            detection_source=data['detection_source'],
            reasoning=data['reasoning'],
        ))

    severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "NONE": 4}
    ap_details.sort(key=lambda x: severity_order.get(x.severity, 5))

    total_viol = sum(len(d['files']) for d in ap_violations.values())
    summary = (
        f"✅ No violations in {len(files)} files"
        if total_viol == 0
        else f"⚠️ {total_viol} violations across {len(files)} files"
    )

    return EnhancedPredictionResult(
        architecture_pattern=architecture,
        total_files_analyzed=len(files),
        total_violations=total_viol,
        anti_patterns=ap_details,
        summary=summary,
        gemini_fallback_used=gemini_fallback_used,
    )


# ─────────────────────────────────────────────────────────────────
# QUALITY SCORE ENDPOINTS
# ─────────────────────────────────────────────────────────────────

@app.post("/predict-quality-score", response_model=QualityScoreResult)
def predict_quality_score(input_data: QualityScoreInput):
    result = quality_model.predict(input_data.dict())
    return QualityScoreResult(**result)


@app.post("/analyze-quality", response_model=ProjectQualityResult)
def analyze_quality(input_data: FileAnalysisInput):
    files = input_data.files
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    architecture = files[0].architecture_pattern
    now          = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    file_results: List[FileQualityResult] = []
    for f in files:
        metrics = f.dict()
        qs      = quality_model.predict(metrics)
        issues  = _derive_issues(metrics)
        file_results.append(FileQualityResult(
            file_name=f.file_name, file_path=f.file_path,
            layer=f.layer or "unknown",
            quality_score=qs['quality_score'], quality_label=qs['quality_label'],
            quality_emoji=qs['quality_emoji'], quality_display=qs['quality_display'],
            issues=issues,
        ))

    layer_map: dict = defaultdict(list)
    for fr in file_results:
        layer_map[fr.layer].append(fr)

    layer_scores: List[LayerQualitySummary] = []
    for layer_name, layer_files in layer_map.items():
        mean_score = sum(f.quality_score for f in layer_files) / len(layer_files)
        label, emoji = quality_model._score_label(mean_score)
        layer_scores.append(LayerQualitySummary(
            layer=layer_name, file_count=len(layer_files),
            mean_score=round(mean_score, 1), quality_label=label, quality_emoji=emoji,
            quality_display=f"{emoji} {label} ({mean_score:.0f}/100)", files=layer_files,
        ))
    layer_scores.sort(key=lambda x: x.mean_score, reverse=True)

    overall = sum(f.quality_score for f in file_results) / len(file_results)
    o_label, o_emoji = quality_model._score_label(overall)
    total_issues   = sum(len(f.issues) for f in file_results)
    files_violated = sum(1 for f in file_results if f.issues)
    avg_loc        = sum(f.loc   for f in files) / len(files)
    avg_deps       = sum(f.total_cross_layer_deps for f in files) / len(files)
    avg_imports    = sum(f.imports for f in files) / len(files)
    projected      = min(100.0, overall + total_issues * 1.5)

    return ProjectQualityResult(
        architecture_pattern=architecture, total_files_analyzed=len(files),
        analysis_date=now, overall_score=round(overall, 1),
        overall_label=o_label, overall_emoji=o_emoji,
        overall_display=f"{o_emoji} {o_label} ({overall:.0f}/100)",
        layer_scores=layer_scores,
        files=sorted(file_results, key=lambda x: x.quality_score),
        avg_loc=round(avg_loc, 1), avg_imports=round(avg_imports, 1),
        avg_cross_layer_deps=round(avg_deps, 2),
        files_with_violations=files_violated, total_issues_found=total_issues,
        projected_score_after_fixes=round(projected, 1),
        summary=_build_quality_summary(overall, o_label, layer_scores, total_issues, files_violated),
    )


# ─────────────────────────────────────────────────────────────────
# COMBINED ENDPOINT
# ─────────────────────────────────────────────────────────────────

@app.post("/analyze-project-full", response_model=CombinedAnalysisResult)
def analyze_project_full(input_data: FileAnalysisInput):
    files = input_data.files
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    architecture = files[0].architecture_pattern
    now          = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    gemini_fallback_used = False
    quality_adjusted     = False
    original_overall     = None

    # ── Step 1: ML quality scores for all files ─────────────────────────
    file_results: List[FileQualityResult] = []
    for f in files:
        metrics = f.dict()
        qs      = quality_model.predict(metrics)
        issues  = _derive_issues(metrics)
        file_results.append(FileQualityResult(
            file_name=f.file_name, file_path=f.file_path,
            layer=f.layer or "unknown",
            quality_score=qs['quality_score'], quality_label=qs['quality_label'],
            quality_emoji=qs['quality_emoji'], quality_display=qs['quality_display'],
            issues=issues,
        ))

    # ── Step 2: ML predictions + fallback detection ─────────────────────
    files_with_preds = []
    for f in files:
        features = f.dict()
        ml_pred, ml_conf = antipattern_model.predict_with_confidence(features)
        features["_ml_prediction"] = ml_pred
        features["_ml_confidence"] = ml_conf
        files_with_preds.append(features)

    all_detections = detect_antipatterns_batch(files_with_preds, architecture)

    # ── Step 3: Aggregate violations with detection_source ──────────────
    ap_violations: dict = defaultdict(lambda: {
        'files': [], 'layers': set(), 'confidences': [],
        'detection_source': 'ml_model', 'reasoning': None
    })
    clean_files: List[str] = []
    # Track per-file fallback detections for quality adjustment
    file_fallback_detections: dict = {}  # fname -> list of detections

    for f in files:
        fname = f.file_name
        detections = all_detections.get(fname, [])
        file_is_clean = True
        fallback_dets = []

        for d in detections:
            ap = d["anti_pattern"]
            if ap == "clean":
                continue
            file_is_clean = False
            layer = antipattern_model.detect_layer(f.dict())
            ap_violations[ap]['files'].append(fname)
            ap_violations[ap]['layers'].add(layer)
            ap_violations[ap]['confidences'].append(d["confidence"])
            if d["detection_source"] in ("gemini_ai", "rule_based"):
                ap_violations[ap]['detection_source'] = d["detection_source"]
                ap_violations[ap]['reasoning'] = d.get("reasoning")
                gemini_fallback_used = True
                fallback_dets.append(d)

        if file_is_clean:
            clean_files.append(fname)
        if fallback_dets:
            file_fallback_detections[fname] = fallback_dets

    # ── Step 4: Adjust quality scores for fallback-detected patterns ────
    if file_fallback_detections:
        quality_adjusted = True
        original_overall = round(
            sum(fr.quality_score for fr in file_results) / len(file_results), 1
        )
        for fr in file_results:
            if fr.file_name in file_fallback_detections:
                adj_score, adj_reason = adjust_quality_for_detections(
                    fr.quality_score, file_fallback_detections[fr.file_name]
                )
                if adj_reason:
                    fr.quality_score = adj_score
                    fr.quality_adjusted = True
                    fr.adjustment_reason = adj_reason
                    label, emoji = quality_model._score_label(adj_score)
                    fr.quality_label = label
                    fr.quality_emoji = emoji
                    fr.quality_display = f"{emoji} {label} ({adj_score:.0f}/100)"

    # ── Step 5: Build anti-pattern details ──────────────────────────────
    ap_details: List[AntiPatternDetail] = []
    for ap, data in ap_violations.items():
        info = antipattern_model.ANTI_PATTERN_INFO.get(ap, {
            "severity": "UNKNOWN", "description": "Unknown anti-pattern",
            "recommendation": "Review manually"})
        avg_conf = sum(data['confidences']) / len(data['confidences'])
        ap_details.append(AntiPatternDetail(
            type=ap, severity=info['severity'],
            affected_layer=", ".join(sorted(data['layers'])),
            confidence=round(avg_conf, 2), files=data['files'],
            description=info['description'], recommendation=info['recommendation'],
            detection_source=data['detection_source'],
            reasoning=data['reasoning'],
        ))
    severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "NONE": 4}
    ap_details.sort(key=lambda x: severity_order.get(x.severity, 5))

    # ── Step 6: Layer scores & summary ──────────────────────────────────
    layer_map: dict = defaultdict(list)
    for fr in file_results:
        layer_map[fr.layer].append(fr)

    layer_scores: List[LayerQualitySummary] = []
    for layer_name, lfiles in layer_map.items():
        mean_score = sum(f.quality_score for f in lfiles) / len(lfiles)
        label, emoji = quality_model._score_label(mean_score)
        layer_scores.append(LayerQualitySummary(
            layer=layer_name, file_count=len(lfiles),
            mean_score=round(mean_score, 1), quality_label=label, quality_emoji=emoji,
            quality_display=f"{emoji} {label} ({mean_score:.0f}/100)",
            files=sorted(lfiles, key=lambda x: x.quality_score),
        ))
    layer_scores.sort(key=lambda x: x.mean_score, reverse=True)

    overall = sum(f.quality_score for f in file_results) / len(file_results)
    o_label, o_emoji = quality_model._score_label(overall)
    total_issues   = sum(len(f.issues) for f in file_results)
    files_violated = sum(1 for f in file_results if f.issues)
    total_viol     = sum(len(d['files']) for d in ap_violations.values())
    avg_loc        = sum(f.loc for f in files) / len(files)
    avg_deps       = sum(f.total_cross_layer_deps for f in files) / len(files)
    projected      = min(100.0, overall + total_issues * 1.5)

    return CombinedAnalysisResult(
        architecture_pattern=architecture, total_files_analyzed=len(files),
        analysis_date=now, overall_score=round(overall, 1),
        overall_label=o_label, overall_display=f"{o_emoji} {o_label} ({overall:.0f}/100)",
        layer_scores=layer_scores, total_violations=total_viol,
        anti_patterns=ap_details, clean_files=clean_files,
        files=sorted(file_results, key=lambda x: x.quality_score),
        avg_loc=round(avg_loc, 1), avg_cross_layer_deps=round(avg_deps, 2),
        files_with_violations=files_violated,
        projected_score_after_fixes=round(projected, 1),
        quality_summary=_build_quality_summary(overall, o_label, layer_scores, total_issues, files_violated),
        violation_summary=_build_violation_summary(total_viol, len(files), ap_details),
        gemini_fallback_used=gemini_fallback_used,
        quality_adjusted=quality_adjusted,
        original_overall_score=original_overall,
    )


# ─────────────────────────────────────────────────────────────────
# AI FIX SUGGESTION ENDPOINTS  (Gemini)
# ─────────────────────────────────────────────────────────────────

@app.post("/generate-fix", response_model=FixSuggestion)
def generate_fix(input_data: SingleFixRequest):
    """
    Generate an AI-powered fix suggestion for ONE anti-pattern.
    Falls back to static recommendation if GEMINI_API_KEY is not configured.

    Example request:
    {
      "anti_pattern": "no_validation",
      "files": ["UserController.java", "OrderController.java"],
      "architecture_pattern": "layered",
      "affected_layer": "Controller",
      "severity": "MEDIUM",
      "description": "Missing @Valid on @RequestBody parameters"
    }
    """
    result = generate_fix_suggestion(
        anti_pattern     = input_data.anti_pattern,
        files            = input_data.files,
        architecture     = input_data.architecture_pattern,
        layer            = input_data.affected_layer,
        severity         = input_data.severity,
        description      = input_data.description,
        use_gemini       = True,
        detection_source = getattr(input_data, 'detection_source', 'ml_model') or 'ml_model',
    )
    return FixSuggestion(**result)


@app.post("/generate-fixes", response_model=ProjectFixResult)
def generate_fixes(input_data: FixRequest):
    """
    Generate AI-powered fix suggestions for ALL violations in a project.
    Falls back to static recommendations if GEMINI_API_KEY is not configured.
    """
    ap_dicts = []
    for ap in input_data.anti_patterns:
        d = ap.dict()
        # Ensure detection_source propagates to fix generation
        if not d.get("detection_source"):
            d["detection_source"] = "ml_model"
        ap_dicts.append(d)

    suggestions_raw = generate_project_fixes(
        anti_patterns = ap_dicts,
        architecture  = input_data.architecture_pattern,
    )
    suggestions = [FixSuggestion(**s) for s in suggestions_raw]
    return ProjectFixResult(
        architecture_pattern = input_data.architecture_pattern,
        total_fixes          = len(suggestions),
        suggestions          = suggestions,
    )


# ─────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────

def _derive_issues(metrics: dict) -> List[str]:
    issues = []
    layer  = str(metrics.get('layer', '')).lower()
    if metrics.get('violates_layer_separation'):
        issues.append("Layer separation violation")
    if layer == 'controller':
        if metrics.get('has_business_logic'):
            issues.append("Business logic in controller")
        if not metrics.get('has_validation') and metrics.get('has_http_handling'):
            issues.append("Missing input validation")
        if metrics.get('repository_deps', 0) > 0:
            issues.append("Direct repository access (layer skip)")
    if layer == 'service':
        if metrics.get('has_data_access') and not metrics.get('has_transaction'):
            issues.append("Missing @Transactional")
        if metrics.get('controller_deps', 0) > 0:
            issues.append("Reverse dependency on Controller")
    if layer == 'entity':
        if metrics.get('methods', 0) > 5:
            issues.append("Entity too complex (>5 methods)")
        if metrics.get('has_business_logic'):
            issues.append("Business logic in entity")
    if metrics.get('total_cross_layer_deps', 0) > 5:
        issues.append(f"High cross-layer deps ({int(metrics['total_cross_layer_deps'])})")
    if metrics.get('imports', 0) > 30:
        issues.append(f"High import count ({int(metrics['imports'])})")
    if metrics.get('loc', 0) > 300:
        issues.append(f"Large file ({int(metrics['loc'])} LOC)")
    return issues


def _build_quality_summary(overall, label, layer_scores, total_issues, files_violated):
    worst = layer_scores[-1] if layer_scores else None
    best  = layer_scores[0]  if layer_scores else None
    lines = [f"Overall project quality: {label} ({overall:.0f}/100)"]
    if best:
        lines.append(f"✅ Strongest layer: {best.layer} ({best.mean_score:.0f}/100 {best.quality_emoji})")
    if worst and worst != best:
        lines.append(f"⚠️  Weakest layer: {worst.layer} ({worst.mean_score:.0f}/100 {worst.quality_emoji})")
    lines.append(f"📋 {total_issues} issues found across {files_violated} files")
    return "\n".join(lines)


def _build_violation_summary(total, file_count, details):
    if total == 0:
        return f"✅ No architectural violations detected in {file_count} files"
    critical = sum(1 for d in details if d.severity == "CRITICAL")
    high     = sum(1 for d in details if d.severity == "HIGH")
    medium   = sum(1 for d in details if d.severity == "MEDIUM")
    parts    = [f"⚠️ {total} violations across {file_count} files"]
    if critical: parts.append(f"🔴 {critical} CRITICAL")
    if high:     parts.append(f"🟠 {high} HIGH")
    if medium:   parts.append(f"🟡 {medium} MEDIUM")
    return "  |  ".join(parts)


@app.get("/debug-gemini")
def debug_gemini():
    import os
    key = os.getenv("GEMINI_API_KEY", "")
    from app.gemini_fix_service import GEMINI_MODEL, GEMINI_API_URL
    return {
        "key_set"      : bool(key),
        "key_prefix"   : key[:8] + "..." if key else "NOT SET",
        "model"        : GEMINI_MODEL,
        "api_url"      : GEMINI_API_URL,
    }