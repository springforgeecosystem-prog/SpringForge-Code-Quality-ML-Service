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
from app.model_loader         import AntiPatternModel
from app.quality_model_loader import QualityScoreModel
from app.gemini_fix_service   import generate_project_fixes, generate_fix_suggestion
from app.gemini_validation_service import (
    validate_all_predictions,
    check_clean_predictions,
)
from app.gemini_scoring_service import (
    get_llm_quality_assessment,
    compute_hybrid_file_scores,
    compute_hybrid_overall,
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
    features   = input_data.dict()
    prediction = antipattern_model.predict(features)
    return {"anti_pattern": prediction}


@app.post("/analyze-project", response_model=EnhancedPredictionResult)
def analyze_project(input_data: FileAnalysisInput):
    return antipattern_model.analyze_project(input_data.files)


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

    # ── Step 1: Quality scoring per file (unchanged) ─────────────────
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

    # ── Step 2: ML anti-pattern prediction per file (unchanged) ─────
    ap_violations: dict = defaultdict(lambda: {'files': [], 'layers': set(), 'confidences': []})
    clean_files: List[str] = []
    clean_confidences: dict = {}   # track confidence for clean predictions
    for f in files:
        features     = f.dict()
        ap, conf     = antipattern_model.predict_with_confidence(features)
        if ap == "clean":
            clean_files.append(f.file_name)
            clean_confidences[f.file_name] = conf
        else:
            layer = antipattern_model.detect_layer(features)
            ap_violations[ap]['files'].append(f.file_name)
            ap_violations[ap]['layers'].add(layer)
            ap_violations[ap]['confidences'].append(conf)

    # ── Step 3: Check if source code is available for LLM validation ──
    source_code_map = {}           # {file_name: source_code}
    file_layer_map  = {}           # {file_name: layer}
    for f in files:
        if f.source_code:
            source_code_map[f.file_name] = f.source_code
        file_layer_map[f.file_name] = f.layer or "unknown"

    has_source_code    = bool(source_code_map)
    llm_enhanced       = False
    false_positives    = 0
    false_positive_files = []   # files cleared by LLM (ML was wrong)
    fix_suggestions_list = []

    if has_source_code and ap_violations:
        # ── Step 4: LLM validation of all ML predictions ─────────────
        print(f"\n  [★ LLM Pipeline] Source code available for {len(source_code_map)}/{len(files)} files — running Gemini validation...")

        # Build grouped predictions with metadata for the validator
        grouped = {}
        for ap_type, data in ap_violations.items():
            info = antipattern_model.ANTI_PATTERN_INFO.get(ap_type, {
                "severity": "UNKNOWN", "description": ap_type})
            grouped[ap_type] = {
                "files": data['files'],
                "layers": data['layers'],
                "confidences": data['confidences'],
                "severity": info.get('severity', 'MEDIUM'),
                "description": info.get('description', ''),
            }

        validation_results = validate_all_predictions(
            grouped_predictions=grouped,
            files_map=source_code_map,
            architecture=architecture,
        )

        # ── Step 4a: Apply validation results ───────────────────────
        validated_violations = {}        # ap_type -> data (only valid ones)
        for ap_type, data in ap_violations.items():
            vr = validation_results.get(ap_type, {})

            if vr.get("is_valid", True):
                # Prediction confirmed — keep it, enrich with LLM data
                validated_violations[ap_type] = data
                validated_violations[ap_type]["_validation"] = vr
            else:
                # False positive — Gemini says code is actually correct
                false_positives += 1
                print(f"  [★ LLM Pipeline] ❌ FILTERED false positive: '{ap_type}' — {vr.get('reasoning', '')}")
                # Move affected files back to clean list
                for fname in data['files']:
                    if fname not in clean_files:
                        clean_files.append(fname)
                    if fname not in false_positive_files:
                        false_positive_files.append(fname)

        # Replace ap_violations with only validated ones
        ap_violations = validated_violations
        llm_enhanced = True

        # ── Step 4b: Check low-confidence clean predictions ─────────
        clean_with_code = {}
        for fname in clean_files:
            if fname in source_code_map:
                clean_with_code[fname] = {
                    "source_code": source_code_map[fname],
                    "layer": file_layer_map.get(fname, "unknown"),
                }

        if clean_with_code:
            discovered = check_clean_predictions(
                clean_files_with_code=clean_with_code,
                architecture=architecture,
                confidence_threshold=0.70,
                clean_confidences=clean_confidences,
            )
            # Incorporate newly discovered anti-patterns
            for d in discovered:
                ap_type = d["type"]
                fname   = d["file"]
                if ap_type not in ap_violations:
                    ap_violations[ap_type] = {
                        'files': [], 'layers': set(), 'confidences': [],
                        '_validation': {
                            'is_valid': True,
                            'llm_validated': True,
                            'description': d.get('description', ''),
                            'recommendation': d.get('recommendation', ''),
                            'before_code': d.get('before_code', ''),
                            'after_code': d.get('after_code', ''),
                            'severity': d.get('severity', 'MEDIUM'),
                            'reasoning': 'Discovered by LLM review of low-confidence clean prediction',
                        }
                    }
                ap_violations[ap_type]['files'].append(fname)
                ap_violations[ap_type]['layers'].add(d.get('layer', 'unknown'))
                ap_violations[ap_type]['confidences'].append(0.0)  # ML missed it
                # Remove from clean_files
                if fname in clean_files:
                    clean_files.remove(fname)

    # ── Step 5: Build anti-pattern details (enriched with LLM data) ───
    ap_details: List[AntiPatternDetail] = []
    for ap, data in ap_violations.items():
        info     = antipattern_model.ANTI_PATTERN_INFO.get(ap, {
            "severity": "UNKNOWN", "description": "Unknown anti-pattern",
            "recommendation": "Review manually"})
        avg_conf = sum(data['confidences']) / len(data['confidences']) if data['confidences'] else 0

        # Get LLM validation data if available
        vr = data.get('_validation', {})
        is_llm_validated = vr.get('llm_validated', False)

        # Use LLM description/recommendation if available, fall back to ML static info
        description    = vr.get('description') or info.get('description', '')
        recommendation = vr.get('recommendation') or info.get('recommendation', '')
        severity       = vr.get('severity') or info.get('severity', 'MEDIUM')

        # Build inline fix suggestion if LLM provided one
        fix_dict = None
        if is_llm_validated and (vr.get('before_code') or vr.get('after_code')):
            from app.gemini_fix_service import ANTI_PATTERN_CONTEXT
            ctx = ANTI_PATTERN_CONTEXT.get(ap, {})
            fix_dict = {
                "problem": description,
                "recommendation": recommendation,
                "before_code": vr.get('before_code', ''),
                "after_code": vr.get('after_code', ''),
                "gemini_fix": f"💡 RECOMMENDATION:\n{recommendation}\n\n🔧 EXAMPLE FIX:\n// ❌ BEFORE\n{vr.get('before_code', '')}\n\n// ✅ AFTER\n{vr.get('after_code', '')}",
                "impact_points": ctx.get('impact_pts', 0),
            }

        ap_details.append(AntiPatternDetail(
            type=ap, severity=severity,
            affected_layer=", ".join(sorted(data['layers'])),
            confidence=round(avg_conf, 2), files=data['files'],
            description=description, recommendation=recommendation,
            llm_validated=is_llm_validated,
            llm_description=vr.get('description', ''),
            fix_suggestion=fix_dict,
        ))
    severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "NONE": 4}
    ap_details.sort(key=lambda x: severity_order.get(x.severity, 5))

    # ── Step 6: Generate fix suggestions inline when source code available ─
    if has_source_code and ap_details:
        print(f"  [★ LLM Pipeline] Generating context-aware fix suggestions for {len(ap_details)} validated violations...")
        fix_raws = generate_project_fixes(
            anti_patterns   = [ap.dict() for ap in ap_details],
            architecture    = architecture,
            source_code_map = source_code_map,
        )
        fix_suggestions_list = [FixSuggestion(**s) for s in fix_raws]

    # ── Step 7: Hybrid quality scoring (ML + LLM) ──────────────────
    scoring_method       = "ml_only"
    quality_reasoning    = ""
    quality_strengths    = []
    quality_improvements = []

    if has_source_code:
        # Collect ML per-file scores
        ml_file_scores = {fr.file_name: fr.quality_score for fr in file_results}
        ml_overall     = sum(ml_file_scores.values()) / len(ml_file_scores)

        # Map each file to its violation severities
        file_violations_map = {}
        for ap in ap_details:
            for fname in ap.files:
                file_violations_map.setdefault(fname, []).append(ap.severity)

        # Build file summaries for the Gemini scoring prompt
        file_summaries = []
        for fr in file_results:
            violations_for_file = []
            for ap in ap_details:
                if fr.file_name in ap.files:
                    violations_for_file.append(f"{ap.type} ({ap.severity})")
            file_summaries.append({
                "file_name":  fr.file_name,
                "layer":      fr.layer,
                "ml_score":   fr.quality_score,
                "violations": violations_for_file,
            })

        # Build validated violation summaries
        violation_summaries = [
            {"type": ap.type, "severity": ap.severity,
             "files": ap.files, "llm_validated": ap.llm_validated}
            for ap in ap_details
        ]

        print(f"\n  [★ Hybrid Scoring] Running Gemini quality assessment "
              f"(ML baseline: {ml_overall:.0f}/100, violations: {len(ap_details)}, "
              f"clean: {len(clean_files)})...")

        llm_assessment = get_llm_quality_assessment(
            architecture=architecture,
            file_summaries=file_summaries,
            validated_violations=violation_summaries,
            clean_files=clean_files,
            false_positives_filtered=false_positives,
            ml_overall_score=ml_overall,
        )

        # Compute hybrid per-file scores
        hybrid_scores = compute_hybrid_file_scores(
            ml_file_scores=ml_file_scores,
            llm_assessment=llm_assessment,
            file_violations=file_violations_map,
            clean_files=clean_files,
            false_positive_files=false_positive_files,
            llm_validated=llm_enhanced or (not ap_details),  # also hybrid when no violations
        )

        # Update file_results with hybrid scores
        updated_results = []
        for fr in file_results:
            if fr.file_name in hybrid_scores:
                hs = hybrid_scores[fr.file_name]
                updated_results.append(FileQualityResult(
                    file_name=fr.file_name, file_path=fr.file_path,
                    layer=fr.layer,
                    quality_score=hs["quality_score"],
                    quality_label=hs["quality_label"],
                    quality_emoji=hs["quality_emoji"],
                    quality_display=hs["quality_display"],
                    issues=fr.issues,
                ))
            else:
                updated_results.append(fr)
        file_results = updated_results

        # Extract LLM assessment metadata
        if llm_assessment:
            scoring_method       = "hybrid"
            quality_reasoning    = llm_assessment.get("reasoning", "")
            quality_strengths    = llm_assessment.get("strengths", [])
            quality_improvements = llm_assessment.get("improvements", [])
        else:
            scoring_method = "ml_adjusted" if llm_enhanced else "ml_only"

    # ── Step 8: Build layer scores ────────────────────────────────
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

    # Compute hybrid overall if source code was available
    overall = sum(f.quality_score for f in file_results) / len(file_results)
    o_label, o_emoji = quality_model._score_label(overall)
    total_issues   = sum(len(f.issues) for f in file_results)
    files_violated = sum(1 for f in file_results if f.issues)
    total_viol     = sum(len(d['files']) for d in ap_violations.values())
    avg_loc        = sum(f.loc   for f in files) / len(files)
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
        # ── LLM fields ──
        llm_enhanced=llm_enhanced,
        false_positives_filtered=false_positives,
        fix_suggestions=fix_suggestions_list,
        # ── Hybrid scoring fields ──
        scoring_method=scoring_method,
        quality_reasoning=quality_reasoning,
        quality_strengths=quality_strengths,
        quality_improvements=quality_improvements,
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
        anti_pattern  = input_data.anti_pattern,
        files         = input_data.files,
        architecture  = input_data.architecture_pattern,
        layer         = input_data.affected_layer,
        severity      = input_data.severity,
        description   = input_data.description,
        use_gemini    = True,
    )
    return FixSuggestion(**result)


@app.post("/generate-fixes", response_model=ProjectFixResult)
def generate_fixes(input_data: FixRequest):
    """
    Generate AI-powered fix suggestions for ALL violations in a project.
    Falls back to static recommendations if GEMINI_API_KEY is not configured.
    Accepts optional file_sources for context-aware fixes.
    """
    # Build source code map from optional file_sources
    source_map = input_data.file_sources if input_data.file_sources else None

    suggestions_raw = generate_project_fixes(
        anti_patterns   = [ap.dict() for ap in input_data.anti_patterns],
        architecture    = input_data.architecture_pattern,
        source_code_map = source_map,
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