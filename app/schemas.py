"""
app/schemas.py  — UPDATED v2
──────────────────────────────────────────────────────────────────
Pydantic schemas for the SpringForge ML Service.

CHANGES FROM v1:
  1. AntiPatternInput gains 'uses_new_keyword' and 'has_broad_catch' fields
  2. FileFeatures inherits the new fields automatically
  3. Both fields are Optional with defaults so existing API clients
     that don't send them will still work (backward compatible)
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

    # ── NEW in v2 — textual signal features ──────────────────────
    # Optional with defaults for backward compatibility.
    # When the IDE plugin sends these, the model uses them directly.
    # When old clients don't send them, defaults kick in.
    uses_new_keyword : Optional[bool] = Field(
        default=False,
        description="True if 'new ServiceName()' / 'new RepositoryName()' pattern found in source"
    )
    has_broad_catch  : Optional[bool] = Field(
        default=False,
        description="True if 'catch(Exception e)' or 'catch(Throwable t)' found in source"
    )


class FileFeatures(AntiPatternInput):
    """Extended input with file metadata — used for project analysis."""
    file_name : str
    file_path : str
    layer     : Optional[str] = Field(
        default="unknown",
        description="Architecture layer: controller / service / repository / entity / adapter / port / usecase / gateway"
    )


class FileAnalysisInput(BaseModel):
    """Input for analyzing multiple files (project-level)."""
    files: List[FileFeatures]


# ════════════════════════════════════════════════════════════════
# ANTI-PATTERN MODEL — response schemas
# ════════════════════════════════════════════════════════════════

class AntiPatternDetail(BaseModel):
    type             : str
    severity         : str
    affected_layer   : str
    confidence       : float
    files            : List[str]
    description      : str
    recommendation   : str
    detection_source : Optional[str] = Field(
        default="ml_model",
        description="How this anti-pattern was detected: ml_model | gemini_ai | rule_based"
    )
    reasoning        : Optional[str] = Field(
        default=None,
        description="Explanation when detected by Gemini AI or rule-based fallback"
    )


class EnhancedPredictionResult(BaseModel):
    architecture_pattern  : str
    total_files_analyzed  : int
    total_violations      : int
    anti_patterns         : List[AntiPatternDetail]
    summary               : str
    gemini_fallback_used  : Optional[bool] = Field(
        default=False,
        description="True if Gemini AI or rule-based fallback was used for any detection"
    )


# ════════════════════════════════════════════════════════════════
# QUALITY SCORE MODEL — request / response schemas (unchanged)
# ════════════════════════════════════════════════════════════════

class QualityScoreInput(BaseModel):
    layer                   : str   = Field(default="controller")
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
    quality_score   : float
    quality_label   : str
    quality_emoji   : str
    quality_display : str


class FileQualityResult(BaseModel):
    file_name         : str
    file_path         : str
    layer             : str
    quality_score     : float
    quality_label     : str
    quality_emoji     : str
    quality_display   : str
    issues            : List[str] = Field(default_factory=list)
    quality_adjusted  : Optional[bool] = Field(
        default=False,
        description="True if quality score was adjusted due to Gemini/rule-based detected patterns"
    )
    adjustment_reason : Optional[str] = Field(
        default=None,
        description="Explanation of quality score adjustment"
    )


class LayerQualitySummary(BaseModel):
    layer           : str
    file_count      : int
    mean_score      : float
    quality_label   : str
    quality_emoji   : str
    quality_display : str
    files           : List[FileQualityResult]


class ProjectQualityResult(BaseModel):
    architecture_pattern  : str
    total_files_analyzed  : int
    analysis_date         : str
    overall_score         : float
    overall_label         : str
    overall_emoji         : str
    overall_display       : str
    layer_scores          : List[LayerQualitySummary]
    files                 : List[FileQualityResult]
    avg_loc               : float
    avg_imports           : float
    avg_cross_layer_deps  : float
    files_with_violations : int
    total_issues_found    : int
    projected_score_after_fixes : float
    summary               : str


# ════════════════════════════════════════════════════════════════
# COMBINED ANALYSIS
# ════════════════════════════════════════════════════════════════

class CombinedAnalysisResult(BaseModel):
    architecture_pattern  : str
    total_files_analyzed  : int
    analysis_date         : str
    overall_score         : float
    overall_label         : str
    overall_display       : str
    layer_scores          : List[LayerQualitySummary]
    total_violations      : int
    anti_patterns         : List[AntiPatternDetail]
    clean_files           : List[str]
    files                 : List[FileQualityResult]
    avg_loc               : float
    avg_cross_layer_deps  : float
    files_with_violations : int
    projected_score_after_fixes : float
    quality_summary       : str
    violation_summary     : str
    gemini_fallback_used  : Optional[bool] = Field(
        default=False,
        description="True if Gemini AI or rule-based fallback was used for any detection"
    )
    quality_adjusted      : Optional[bool] = Field(
        default=False,
        description="True if quality scores were adjusted due to fallback-detected patterns"
    )
    original_overall_score: Optional[float] = Field(
        default=None,
        description="Original overall score before Gemini/rule-based adjustment"
    )


# ════════════════════════════════════════════════════════════════
# AI-POWERED FIX SUGGESTIONS
# ════════════════════════════════════════════════════════════════

class SingleFixRequest(BaseModel):
    anti_pattern         : str
    files                : List[str] = []
    architecture_pattern : str       = "layered"
    affected_layer       : str       = "unknown"
    severity             : str       = "MEDIUM"
    description          : str       = ""
    detection_source     : Optional[str] = Field(
        default="ml_model",
        description="How the anti-pattern was detected: ml_model | gemini_ai | rule_based"
    )


class FixRequest(BaseModel):
    anti_patterns        : List[AntiPatternDetail]
    architecture_pattern : str = "layered"


class FixSuggestion(BaseModel):
    anti_pattern    : str
    layer           : str
    severity        : str
    impact_points   : int
    problem         : str
    recommendation  : str
    files           : List[str]
    before_code     : str
    after_code      : str
    gemini_fix      : str
    ai_powered      : bool
    detection_source: Optional[str] = Field(
        default="ml_model",
        description="How the anti-pattern was originally detected: ml_model | gemini_ai | rule_based"
    )


class ProjectFixResult(BaseModel):
    architecture_pattern : str
    total_fixes          : int
    suggestions          : List[FixSuggestion]