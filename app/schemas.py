"""
# app/schemas.py 
──────────────────────────────────────────────────────────────────
Pydantic schemas for the SpringForge ML Service.
Supports both:
  • Anti-pattern classification  
  • Quality score regression      
──────────────────────────────────────────────────────────────────
"""

from pydantic import BaseModel, Field
from typing import List, Optional


# ════════════════════════════════════════════════════════════════
# SHARED BASE — raw metrics sent for every file
# ════════════════════════════════════════════════════════════════

class AntiPatternInput(BaseModel):
    """Single file analysis input — used by both models."""
    architecture_pattern    : str
    architecture_confidence : float
    loc                     : float
    methods                 : float
    classes                 : float
    avg_cc                  : float
    imports                 : float
    annotations             : float
    controller_deps         : float
    service_deps            : float
    repository_deps         : float
    entity_deps             : float
    adapter_deps            : float
    port_deps               : float
    usecase_deps            : float
    gateway_deps            : float
    total_cross_layer_deps  : float
    has_business_logic      : bool
    has_data_access         : bool
    has_http_handling       : bool
    has_validation          : bool
    has_transaction         : bool
    violates_layer_separation: bool


class FileFeatures(AntiPatternInput):
    """Extended input with file metadata — used for project analysis."""
    file_name : str
    file_path : str
    layer     : Optional[str] = "unknown"


class FileAnalysisInput(BaseModel):
    """Input for analyzing multiple files (project-level)."""
    files: List[FileFeatures]


# ════════════════════════════════════════════════════════════════
# ANTI-PATTERN MODEL — response schemas 
# ════════════════════════════════════════════════════════════════

class AntiPatternDetail(BaseModel):
    """Detailed anti-pattern information"""
    type           : str
    severity       : str
    affected_layer : str
    confidence     : float
    files          : List[str]
    description    : str
    recommendation : str


class EnhancedPredictionResult(BaseModel):
    """Enhanced result with detailed information"""
    architecture_pattern  : str
    total_files_analyzed  : int
    total_violations      : int
    anti_patterns         : List[AntiPatternDetail]
    summary               : str


# ════════════════════════════════════════════════════════════════
# QUALITY SCORE MODEL — request / response schemas  
# ════════════════════════════════════════════════════════════════

class QualityScoreInput(BaseModel):
    """
    Input for quality score prediction for a single file.
    Identical fields to AntiPatternInput plus 'layer'.
    """
    layer                   : str   = Field(default="controller",
                                            description="Spring layer: controller / service / repository / entity / adapter / port")
    loc                     : float = 0
    methods                 : float = 0
    classes                 : float = 0
    avg_cc                  : float = 1.0
    imports                 : float = 0
    annotations             : float = 0
    controller_deps         : float = 0
    service_deps            : float = 0
    repository_deps         : float = 0
    adapter_deps            : float = 0
    port_deps               : float = 0
    total_cross_layer_deps  : float = 0
    has_business_logic      : bool  = False
    has_data_access         : bool  = False
    has_http_handling       : bool  = False
    has_validation          : bool  = False
    has_transaction         : bool  = False
    violates_layer_separation: bool = False


class QualityScoreResult(BaseModel):
    """Quality score result for a single file."""
    quality_score   : float = Field(description="Predicted quality score 0–100")
    quality_label   : str   = Field(description="Excellent / Good / Fair / Poor / Critical")
    quality_emoji   : str   = Field(description="🟢 / 🟠 / 🔴")
    quality_display : str   = Field(description="Human-readable display string")


class FileQualityResult(BaseModel):
    """Quality score result enriched with file metadata."""
    file_name       : str
    file_path       : str
    layer           : str
    quality_score   : float
    quality_label   : str
    quality_emoji   : str
    quality_display : str
    issues          : List[str] = Field(default_factory=list,
                                        description="Human-readable issue list for this file")


class LayerQualitySummary(BaseModel):
    """Aggregated quality stats for one architecture layer."""
    layer           : str
    file_count      : int
    mean_score      : float
    quality_label   : str
    quality_emoji   : str
    quality_display : str
    files           : List[FileQualityResult]


class ProjectQualityResult(BaseModel):
    """
    Full project-level quality analysis result.
    Returned by POST /analyze-quality.
    Designed to drive the IntelliJ IDEA report panel.
    """
    architecture_pattern  : str
    total_files_analyzed  : int
    analysis_date         : str

    # Overall score
    overall_score         : float
    overall_label         : str
    overall_emoji         : str
    overall_display       : str

    # Per-layer breakdown
    layer_scores          : List[LayerQualitySummary]

    # Actionable file list (worst files first)
    files                 : List[FileQualityResult]

    # Code health metrics
    avg_loc               : float
    avg_imports           : float
    avg_cross_layer_deps  : float
    files_with_violations : int
    total_issues_found    : int

    # Improvement projection
    projected_score_after_fixes : float
    summary                     : str


# ════════════════════════════════════════════════════════════════
# COMBINED ANALYSIS — both models together  
# ════════════════════════════════════════════════════════════════

class CombinedAnalysisResult(BaseModel):
    """
    Full combined output: anti-pattern violations + quality scores.
    Returned by POST /analyze-project-full.
    This is the payload that drives the IntelliJ "Analyze Code Quality"
    report panel described in the project brief.
    """
    # ── Project metadata ──────────────────────────────────────────
    architecture_pattern  : str
    total_files_analyzed  : int
    analysis_date         : str

    # ── Quality Score section ──────────────────────────────────────
    overall_score         : float
    overall_label         : str
    overall_display       : str
    layer_scores          : List[LayerQualitySummary]

    # ── Anti-pattern section ───────────────────────────────────────
    total_violations      : int
    anti_patterns         : List[AntiPatternDetail]
    clean_files           : List[str]

    # ── Per-file details ───────────────────────────────────────────
    files                 : List[FileQualityResult]

    # ── Code health metrics ────────────────────────────────────────
    avg_loc               : float
    avg_cross_layer_deps  : float
    files_with_violations : int

    # ── Improvement projection ─────────────────────────────────────
    projected_score_after_fixes : float

    # ── Summaries ──────────────────────────────────────────────────
    quality_summary       : str
    violation_summary     : str