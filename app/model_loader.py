"""
model_loader.py
──────────────────────────────────────────────────────────────────
Anti-Pattern Classification Model loader.
──────────────────────────────────────────────────────────────────
"""

import joblib
import pandas as pd
from typing import List, Dict
from collections import defaultdict
from app.schemas import FileFeatures, AntiPatternDetail, EnhancedPredictionResult


class AntiPatternModel:
    
    # Anti-pattern metadata
    ANTI_PATTERN_INFO = {
        "layer_skip_in_layered": {
            "severity": "HIGH",
            "description": "Controller directly accesses Repository, bypassing Service layer",
            "recommendation": "Introduce Service layer to handle business logic and coordinate Repository access"
        },
        "reversed_dependency_in_layered": {
            "severity": "HIGH",
            "description": "Service layer depends on Controller, violating layered architecture",
            "recommendation": "Remove Controller dependencies from Service layer"
        },
        "business_logic_in_controller_layered": {
            "severity": "MEDIUM",
            "description": "Business logic found in Controller layer instead of Service layer",
            "recommendation": "Move business logic to Service layer, keep Controllers thin"
        },
        "missing_transaction_in_layered": {
            "severity": "HIGH",
            "description": "Service performs database operations without @Transactional annotation",
            "recommendation": "Add @Transactional annotation to methods with database operations"
        },
        "missing_port_adapter_in_hexagonal": {
            "severity": "CRITICAL",
            "description": "Domain layer accesses infrastructure without Port/Adapter pattern",
            "recommendation": "Implement Port interfaces and Adapter classes for infrastructure access"
        },
        "framework_dependency_in_domain_hexagonal": {
            "severity": "CRITICAL",
            "description": "Domain layer has framework dependencies (Spring, JPA)",
            "recommendation": "Remove framework annotations from domain layer, use interfaces"
        },
        "adapter_without_port_hexagonal": {
            "severity": "MEDIUM",
            "description": "Adapter class doesn't implement a Port interface",
            "recommendation": "Create Port interface and implement it in Adapter"
        },
        "outer_depends_on_inner_clean": {
            "severity": "CRITICAL",
            "description": "Outer layer (Controller) depends on inner layer details (Entity/Repository)",
            "recommendation": "Use DTOs and interfaces to maintain dependency rule"
        },
        "usecase_framework_coupling_clean": {
            "severity": "CRITICAL",
            "description": "Use case layer is coupled with framework annotations",
            "recommendation": "Keep use cases framework-agnostic, use interfaces"
        },
        "entity_framework_coupling_clean": {
            "severity": "MEDIUM",
            "description": "Domain entities have framework annotations (JPA)",
            "recommendation": "Separate domain entities from persistence entities"
        },
        "missing_gateway_interface_clean": {
            "severity": "HIGH",
            "description": "Use case accesses Repository without Gateway interface",
            "recommendation": "Create Gateway interface for Repository access"
        },
        "broad_catch": {
            "severity": "MEDIUM",
            "description": "Generic exception catching (Exception, Throwable)",
            "recommendation": "Catch specific exceptions and handle them appropriately"
        },
        "no_validation": {
            "severity": "MEDIUM",
            "description": "Missing input validation in Controller endpoint",
            "recommendation": "Add @Valid annotation to @RequestBody parameters"
        },
        "tight_coupling_new_keyword": {
            "severity": "MEDIUM",
            "description": "Dependencies created using 'new' keyword instead of DI",
            "recommendation": "Use constructor injection for dependencies"
        },
        "clean": {
            "severity": "NONE",
            "description": "No anti-patterns detected",
            "recommendation": "Code follows architectural best practices"
        }
    }

    def __init__(self):
        print("🔧 Loading Anti-Pattern Classification model...")
        bundle = joblib.load("models/architecture_aware_antipattern_model.joblib")
        self.model   = bundle["model"]
        self.encoder = bundle["label_encoder"]
        print("✅ Anti-Pattern model loaded!")

        self.feature_order = [
            'architecture_pattern', 'architecture_confidence',
            'loc', 'methods', 'classes', 'avg_cc', 'imports', 'annotations',
            'controller_deps', 'service_deps', 'repository_deps', 'entity_deps',
            'adapter_deps', 'port_deps', 'usecase_deps', 'gateway_deps',
            'total_cross_layer_deps',
            'has_business_logic', 'has_data_access', 'has_http_handling',
            'has_validation', 'has_transaction', 'violates_layer_separation',
        ]

    def predict(self, features: dict) -> str:
        df = pd.DataFrame([[features[col] for col in self.feature_order]],
                          columns=self.feature_order)
        pred_encoded = self.model.predict(df)[0]
        return self.encoder.inverse_transform([pred_encoded])[0]

    def predict_with_confidence(self, features: dict) -> tuple:
        df = pd.DataFrame([[features[col] for col in self.feature_order]],
                          columns=self.feature_order)
        pred_encoded = self.model.predict(df)[0]
        anti_pattern = self.encoder.inverse_transform([pred_encoded])[0]
        if hasattr(self.model, 'predict_proba'):
            probabilities = self.model.predict_proba(df)[0]
            confidence = float(probabilities[pred_encoded])
        else:
            confidence = 0.85
        return anti_pattern, confidence

    def detect_layer(self, features: dict) -> str:
        # Prefer explicit layer field
        layer = features.get('layer', '').strip().lower()
        if layer and layer != 'unknown':
            return layer.capitalize()
        if features.get('has_http_handling', False):
            return "Controller"
        elif features.get('has_data_access', False):
            return "Repository"
        elif features.get('has_business_logic', False):
            return "Service"
        elif features.get('annotations', 0) > 5:
            return "Entity"
        return "Unknown"

    def analyze_project(self, files: List[FileFeatures]) -> EnhancedPredictionResult:
        violations  = defaultdict(lambda: {'files': [], 'layers': set(), 'confidences': []})
        architecture = files[0].architecture_pattern if files else "unknown"

        for file_data in files:
            features     = file_data.dict()
            anti_pattern, confidence = self.predict_with_confidence(features)
            if anti_pattern == "clean":
                continue
            layer = self.detect_layer(features)
            violations[anti_pattern]['files'].append(file_data.file_name)
            violations[anti_pattern]['layers'].add(layer)
            violations[anti_pattern]['confidences'].append(confidence)

        anti_pattern_details = []
        for anti_pattern, data in violations.items():
            info = self.ANTI_PATTERN_INFO.get(anti_pattern, {
                "severity": "UNKNOWN",
                "description": "Unknown anti-pattern",
                "recommendation": "Review code manually"
            })
            avg_conf = sum(data['confidences']) / len(data['confidences'])
            anti_pattern_details.append(AntiPatternDetail(
                type           = anti_pattern,
                severity       = info['severity'],
                affected_layer = ", ".join(sorted(data['layers'])),
                confidence     = round(avg_conf, 2),
                files          = data['files'],
                description    = info['description'],
                recommendation = info['recommendation'],
            ))

        severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "NONE": 4}
        anti_pattern_details.sort(key=lambda x: severity_order.get(x.severity, 5))

        total_violations = sum(len(d['files']) for d in violations.values())
        if total_violations == 0:
            summary = f"✅ No architectural violations detected in {len(files)} files"
        else:
            critical = sum(1 for ap in anti_pattern_details if ap.severity == "CRITICAL")
            high     = sum(1 for ap in anti_pattern_details if ap.severity == "HIGH")
            medium   = sum(1 for ap in anti_pattern_details if ap.severity == "MEDIUM")
            summary  = f"⚠️ Found {total_violations} violations across {len(files)} files\n"
            if critical: summary += f"🔴 {critical} CRITICAL issues\n"
            if high:     summary += f"🟠 {high} HIGH severity issues\n"
            if medium:   summary += f"🟡 {medium} MEDIUM severity issues"

        return EnhancedPredictionResult(
            architecture_pattern = architecture,
            total_files_analyzed = len(files),
            total_violations     = total_violations,
            anti_patterns        = anti_pattern_details,
            summary              = summary,
        )