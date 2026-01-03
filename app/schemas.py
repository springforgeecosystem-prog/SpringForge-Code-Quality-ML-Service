# app/schemas.py 
from pydantic import BaseModel
from typing import List, Optional

class AntiPatternInput(BaseModel):
    """Single file analysis input"""
    architecture_pattern: str
    architecture_confidence: float
    loc: float
    methods: float
    classes: float
    avg_cc: float
    imports: float
    annotations: float
    controller_deps: float
    service_deps: float
    repository_deps: float
    entity_deps: float
    adapter_deps: float
    port_deps: float
    usecase_deps: float
    gateway_deps: float
    total_cross_layer_deps: float
    has_business_logic: bool
    has_data_access: bool
    has_http_handling: bool
    has_validation: bool
    has_transaction: bool
    violates_layer_separation: bool

class FileFeatures(AntiPatternInput):
    """Extended input with file metadata"""
    file_name: str
    file_path: str
    layer: Optional[str] = "unknown"

class FileAnalysisInput(BaseModel):
    """Input for analyzing multiple files"""
    files: List[FileFeatures]

class AntiPatternDetail(BaseModel):
    """Detailed anti-pattern information"""
    type: str
    severity: str
    affected_layer: str
    confidence: float
    files: List[str]
    description: str
    recommendation: str

class EnhancedPredictionResult(BaseModel):
    """Enhanced result with detailed information"""
    architecture_pattern: str
    total_files_analyzed: int
    total_violations: int
    anti_patterns: List[AntiPatternDetail]
    summary: str