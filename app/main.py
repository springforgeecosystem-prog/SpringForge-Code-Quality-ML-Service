"""
main.py
──────────────────────────────────────────────────────────────────
SpringForge AI-Driven Code Quality ML Service
FastAPI application exposing:

  EXISTING (Anti-Pattern Classification):
    GET  /                          Health check
    POST /predict-antipattern       Single file anti-pattern prediction
    POST /analyze-project           Multi-file anti-pattern analysis

  NEW (Quality Score Regression):
    POST /predict-quality-score     Single file quality score prediction
    POST /analyze-quality           Multi-file quality score analysis

  NEW (Combined — drives IntelliJ plugin):
    POST /analyze-project-full      Combined anti-pattern + quality score
                                    for all files in a project
──────────────────────────────────────────────────────────────────
"""

from datetime import datetime
from typing  import List
from collections import defaultdict

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
)
from app.model_loader         import AntiPatternModel
from app.quality_model_loader import QualityScoreModel

# ── Startup: load both models once ────────────────────────────────
app = FastAPI(
    title       = "SpringForge AI-Driven Code Quality ML Service",
    description = "Anti-Pattern Classification + Quality Score Prediction",
    version     = "2.0.0",
)

antipattern_model  = AntiPatternModel()
quality_model      = QualityScoreModel()


@app.get("/")
def home():
    return {
        "status"  : "SpringForge ML Service Running",
        "version" : "2.0.0",
        "models"  : ["Anti-Pattern Classifier", "Quality Score Regressor"],
    }


@app.post("/predict-antipattern")
def predict_antipattern(input_data: AntiPatternInput):
    """Single file anti-pattern prediction (backward compatible)."""
    features    = input_data.dict()
    prediction  = antipattern_model.predict(features)
    return {"anti_pattern": prediction}


@app.post("/analyze-project", response_model=EnhancedPredictionResult)
def analyze_project(input_data: FileAnalysisInput):
    """
    Analyze multiple files and return detailed results with:
    - Anti-pattern types
    - Severity levels
    - Affected layers
    - Confidence scores
    - File-level details
    """
    return antipattern_model.analyze_project(input_data.files)


# ─────────────────────────────────────────────────────────────────
# QUALITY SCORE ENDPOINTS
# ─────────────────────────────────────────────────────────────────

@app.post("/predict-quality-score", response_model=QualityScoreResult)
def predict_quality_score(input_data: QualityScoreInput):
    """
    Predict quality score (0–100) for a single Java file.

    Example request body:
    {
      "layer": "controller",
      "loc": 250, "methods": 8, "classes": 1, "avg_cc": 3.0,
      "imports": 15, "annotations": 8,
      "controller_deps": 0, "service_deps": 2, "repository_deps": 1,
      "adapter_deps": 0, "port_deps": 0, "total_cross_layer_deps": 3,
      "has_business_logic": true, "has_data_access": false,
      "has_http_handling": true, "has_validation": false,
      "has_transaction": false, "violates_layer_separation": true
    }
    """
    result = quality_model.predict(input_data.dict())
    return QualityScoreResult(**result)


@app.post("/analyze-quality", response_model=ProjectQualityResult)
def analyze_quality(input_data: FileAnalysisInput):
    """
    Quality score analysis for all files in a project.
    Returns per-file scores, per-layer summaries, and overall project score.
    """
    files = input_data.files
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    architecture = files[0].architecture_pattern
    now          = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ── Score every file ──────────────────────────────────────────
    file_results: List[FileQualityResult] = []
    for f in files:
        metrics  = f.dict()
        qs       = quality_model.predict(metrics)
        issues   = _derive_issues(metrics)
        file_results.append(FileQualityResult(
            file_name       = f.file_name,
            file_path       = f.file_path,
            layer           = f.layer or "unknown",
            quality_score   = qs['quality_score'],
            quality_label   = qs['quality_label'],
            quality_emoji   = qs['quality_emoji'],
            quality_display = qs['quality_display'],
            issues          = issues,
        ))

    # ── Per-layer aggregation ─────────────────────────────────────
    layer_map: dict = defaultdict(list)
    for fr in file_results:
        layer_map[fr.layer].append(fr)

    layer_scores: List[LayerQualitySummary] = []
    for layer_name, layer_files in layer_map.items():
        mean_score = sum(f.quality_score for f in layer_files) / len(layer_files)
        label, emoji = quality_model._score_label(mean_score)
        layer_scores.append(LayerQualitySummary(
            layer           = layer_name,
            file_count      = len(layer_files),
            mean_score      = round(mean_score, 1),
            quality_label   = label,
            quality_emoji   = emoji,
            quality_display = f"{emoji} {label} ({mean_score:.0f}/100)",
            files           = sorted(layer_files, key=lambda x: x.quality_score),
        ))
    layer_scores.sort(key=lambda x: x.mean_score, reverse=True)

    # ── Overall score ─────────────────────────────────────────────
    overall = sum(f.quality_score for f in file_results) / len(file_results)
    o_label, o_emoji = quality_model._score_label(overall)

    # ── Code health metrics ───────────────────────────────────────
    total_issues   = sum(len(f.issues) for f in file_results)
    files_violated = sum(1 for f in file_results if len(f.issues) > 0)
    avg_loc        = sum(f.loc   for f in files) / len(files)
    avg_deps       = sum(f.total_cross_layer_deps for f in files) / len(files)
    avg_imports    = sum(f.imports for f in files) / len(files)

    # ── Projected score (rough: assume high-severity issues fixed) ─
    projected = min(100.0, overall + total_issues * 1.5)

    summary = _build_quality_summary(overall, o_label, layer_scores,
                                     total_issues, files_violated)

    return ProjectQualityResult(
        architecture_pattern        = architecture,
        total_files_analyzed        = len(files),
        analysis_date               = now,
        overall_score               = round(overall, 1),
        overall_label               = o_label,
        overall_emoji               = o_emoji,
        overall_display             = f"{o_emoji} {o_label} ({overall:.0f}/100)",
        layer_scores                = layer_scores,
        files                       = sorted(file_results,
                                             key=lambda x: x.quality_score),
        avg_loc                     = round(avg_loc, 1),
        avg_imports                 = round(avg_imports, 1),
        avg_cross_layer_deps        = round(avg_deps, 2),
        files_with_violations       = files_violated,
        total_issues_found          = total_issues,
        projected_score_after_fixes = round(projected, 1),
        summary                     = summary,
    )


# ─────────────────────────────────────────────────────────────────
# NEW: COMBINED ENDPOINT  (drives IntelliJ "Analyze Code Quality")
# ─────────────────────────────────────────────────────────────────

@app.post("/analyze-project-full", response_model=CombinedAnalysisResult)
def analyze_project_full(input_data: FileAnalysisInput):
    """
    MAIN ENDPOINT for the IntelliJ plugin "Analyze Code Quality" button.

    Runs BOTH models on every file and returns:
      • Quality score dashboard (overall + per-layer)
      • Anti-pattern violations (sorted by severity)
      • Per-file details with issues
      • Code health metrics
      • Improvement projection

    The IntelliJ plugin calls this single endpoint and renders the
    full SPRINGFORGE CODE QUALITY ANALYSIS REPORT from the response.
    """
    files = input_data.files
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    architecture = files[0].architecture_pattern
    now          = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ── 1. Run Quality Score model on every file ──────────────────
    file_results: List[FileQualityResult] = []
    for f in files:
        metrics = f.dict()
        qs      = quality_model.predict(metrics)
        issues  = _derive_issues(metrics)
        file_results.append(FileQualityResult(
            file_name       = f.file_name,
            file_path       = f.file_path,
            layer           = f.layer or "unknown",
            quality_score   = qs['quality_score'],
            quality_label   = qs['quality_label'],
            quality_emoji   = qs['quality_emoji'],
            quality_display = qs['quality_display'],
            issues          = issues,
        ))

    # ── 2. Run Anti-Pattern model on every file ───────────────────
    ap_violations: dict = defaultdict(
        lambda: {'files': [], 'layers': set(), 'confidences': []})
    clean_files: List[str] = []

    for f in files:
        features     = f.dict()
        ap, conf     = antipattern_model.predict_with_confidence(features)
        if ap == "clean":
            clean_files.append(f.file_name)
        else:
            layer = antipattern_model.detect_layer(features)
            ap_violations[ap]['files'].append(f.file_name)
            ap_violations[ap]['layers'].add(layer)
            ap_violations[ap]['confidences'].append(conf)

    # Build AntiPatternDetail list
    ap_details: List[AntiPatternDetail] = []
    for ap, data in ap_violations.items():
        info     = antipattern_model.ANTI_PATTERN_INFO.get(ap, {
            "severity": "UNKNOWN", "description": "Unknown anti-pattern",
            "recommendation": "Review manually"})
        avg_conf = sum(data['confidences']) / len(data['confidences'])
        ap_details.append(AntiPatternDetail(
            type           = ap,
            severity       = info['severity'],
            affected_layer = ", ".join(sorted(data['layers'])),
            confidence     = round(avg_conf, 2),
            files          = data['files'],
            description    = info['description'],
            recommendation = info['recommendation'],
        ))
    severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "NONE": 4}
    ap_details.sort(key=lambda x: severity_order.get(x.severity, 5))

    # ── 3. Aggregate quality scores per layer ─────────────────────
    layer_map: dict = defaultdict(list)
    for fr in file_results:
        layer_map[fr.layer].append(fr)

    layer_scores: List[LayerQualitySummary] = []
    for layer_name, lfiles in layer_map.items():
        mean_score = sum(f.quality_score for f in lfiles) / len(lfiles)
        label, emoji = quality_model._score_label(mean_score)
        layer_scores.append(LayerQualitySummary(
            layer           = layer_name,
            file_count      = len(lfiles),
            mean_score      = round(mean_score, 1),
            quality_label   = label,
            quality_emoji   = emoji,
            quality_display = f"{emoji} {label} ({mean_score:.0f}/100)",
            files           = sorted(lfiles, key=lambda x: x.quality_score),
        ))
    layer_scores.sort(key=lambda x: x.mean_score, reverse=True)

    # ── 4. Overall score ──────────────────────────────────────────
    overall = sum(f.quality_score for f in file_results) / len(file_results)
    o_label, o_emoji = quality_model._score_label(overall)

    # ── 5. Code health metrics ────────────────────────────────────
    total_issues   = sum(len(f.issues) for f in file_results)
    files_violated = sum(1 for f in file_results if f.issues)
    total_viol     = sum(len(d['files']) for d in ap_violations.values())
    avg_loc        = sum(f.loc   for f in files) / len(files)
    avg_deps       = sum(f.total_cross_layer_deps for f in files) / len(files)
    projected      = min(100.0, overall + total_issues * 1.5)

    return CombinedAnalysisResult(
        architecture_pattern        = architecture,
        total_files_analyzed        = len(files),
        analysis_date               = now,
        overall_score               = round(overall, 1),
        overall_label               = o_label,
        overall_display             = f"{o_emoji} {o_label} ({overall:.0f}/100)",
        layer_scores                = layer_scores,
        total_violations            = total_viol,
        anti_patterns               = ap_details,
        clean_files                 = clean_files,
        files                       = sorted(file_results,
                                             key=lambda x: x.quality_score),
        avg_loc                     = round(avg_loc, 1),
        avg_cross_layer_deps        = round(avg_deps, 2),
        files_with_violations       = files_violated,
        projected_score_after_fixes = round(projected, 1),
        quality_summary             = _build_quality_summary(
                                          overall, o_label, layer_scores,
                                          total_issues, files_violated),
        violation_summary           = _build_violation_summary(
                                          total_viol, len(files), ap_details),
    )


# ─────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────

def _derive_issues(metrics: dict) -> List[str]:
    """
    Convert raw file metrics into human-readable issue strings.
    These are used in the per-file detail table in the IntelliJ report.
    """
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


def _build_quality_summary(overall: float, label: str,
                            layer_scores: List[LayerQualitySummary],
                            total_issues: int, files_violated: int) -> str:
    worst  = layer_scores[-1] if layer_scores else None
    best   = layer_scores[0]  if layer_scores else None
    lines  = [
        f"Overall project quality: {label} ({overall:.0f}/100)",
    ]
    if best:
        lines.append(f"✅ Strongest layer: {best.layer} ({best.mean_score:.0f}/100 {best.quality_emoji})")
    if worst and worst != best:
        lines.append(f"⚠️  Weakest layer: {worst.layer} ({worst.mean_score:.0f}/100 {worst.quality_emoji})")
    lines.append(f"📋 {total_issues} issues found across {files_violated} files")
    return "\n".join(lines)


def _build_violation_summary(total: int, file_count: int,
                              details: List[AntiPatternDetail]) -> str:
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