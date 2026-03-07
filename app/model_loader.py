"""
app/model_loader.py  — UPDATED v3.1
──────────────────────────────────────────────────────────────────
KEY FIXES IN THIS VERSION vs previous:

  FIX 1 (CRITICAL): Apply log1p() to dependency columns before prediction.
         Training notebook Cell 2 transforms all 9 dependency columns with
         np.log1p(). The previous model_loader sent raw values, causing
         the model to see values 1.4x–2.8x larger than it was trained on.
         This caused ~10 test failures including:
           - missing_transaction_in_layered (predicted clean)
           - reversed_dependency_in_layered (predicted clean)
           - missing_port_adapter_in_hexagonal (predicted adapter_without_port)
           - business_logic_in_controller_layered (predicted clean)
           - missing_gateway_interface_clean (predicted clean)

  FIX 2: Build layer_arch interaction feature (layer + '_' + architecture)
          matching Cell 2 of the training notebook exactly.

  FIX 3: Load feature_columns from the saved joblib bundle instead of
          hardcoding, so the feature list always matches what was trained.

  FIX 4: Resolve layer from the input dict before building the row,
          with a sensible inference fallback.

  FIX 5: Add predict_with_confidence() method for use by analyze_project_full.
──────────────────────────────────────────────────────────────────
"""

import numpy as np
import pandas as pd
import joblib
from typing import Tuple

# ── Compatibility shim for models saved with scikit-learn 1.6.x ────────────
# sklearn 1.8+ removed _RemainderColsList; patching it prevents
# AttributeError when unpickling ColumnTransformer from older versions.
import sklearn.compose._column_transformer as _ct
if not hasattr(_ct, '_RemainderColsList'):
    class _RemainderColsList(list):
        """Drop-in stub so pickled ColumnTransformers from sklearn 1.6.x load."""
        def __reduce__(self):
            return (_RemainderColsList, (list(self),))
    _ct._RemainderColsList = _RemainderColsList

DEPENDENCY_COLS = [
    'controller_deps', 'service_deps', 'repository_deps', 'entity_deps',
    'adapter_deps',    'port_deps',    'usecase_deps',    'gateway_deps',
    'total_cross_layer_deps',
]

# ── Anti-pattern metadata (severity, description, recommendation) ──────────
ANTI_PATTERN_INFO = {
    "no_validation": {
        "severity": "MEDIUM",
        "description": "Controller endpoints accept @RequestBody without @Valid.",
        "recommendation": "Add @Valid to @RequestBody params and use @ControllerAdvice for error handling.",
    },
    "business_logic_in_controller_layered": {
        "severity": "HIGH",
        "description": "Business logic embedded in Controller instead of Service layer.",
        "recommendation": "Move all conditionals, loops, and calculations to the Service layer.",
    },
    "layer_skip_in_layered": {
        "severity": "CRITICAL",
        "description": "Controller directly injects Repository, bypassing Service layer.",
        "recommendation": "Inject only Service into Controller; wrap all repository calls in Service.",
    },
    "reversed_dependency_in_layered": {
        "severity": "HIGH",
        "description": "Service layer injects a Controller, reversing the dependency direction.",
        "recommendation": "Remove all Controller imports from Service. Use events if cross-layer notification is needed.",
    },
    "missing_transaction_in_layered": {
        "severity": "HIGH",
        "description": "Service methods write to the database without @Transactional.",
        "recommendation": "Annotate all data-modifying Service methods with @Transactional.",
    },
    "missing_port_adapter_in_hexagonal": {
        "severity": "CRITICAL",
        "description": "Domain/Service directly references Spring Data Repository (infrastructure).",
        "recommendation": "Create a Port interface in domain. Implement with an Adapter in infrastructure.",
    },
    "framework_dependency_in_domain_hexagonal": {
        "severity": "HIGH",
        "description": "Domain/Service imports Spring or JPA framework annotations.",
        "recommendation": "Remove all @Service, @Entity, @Autowired from domain classes.",
    },
    "adapter_without_port_hexagonal": {
        "severity": "MEDIUM",
        "description": "Adapter class does not implement a Port interface.",
        "recommendation": "Create a Port interface in the domain package and have the Adapter implement it.",
    },
    "outer_depends_on_inner_clean": {
        "severity": "CRITICAL",
        "description": "Outer layer (Controller) depends on inner layer details (Entity/Repository).",
        "recommendation": "Controllers must depend only on Use Case interfaces. Use DTOs at boundaries.",
    },
    "usecase_framework_coupling_clean": {
        "severity": "HIGH",
        "description": "Use Case is coupled with Spring/JPA framework annotations.",
        "recommendation": "Remove all framework annotations from Use Case classes.",
    },
    "entity_framework_coupling_clean": {
        "severity": "MEDIUM",
        "description": "Domain Entity has JPA annotations (@Entity, @Table, @Column).",
        "recommendation": "Keep @Entity classes only in the infrastructure layer.",
    },
    "missing_gateway_interface_clean": {
        "severity": "HIGH",
        "description": "Use Case accesses Repository directly without a Gateway interface.",
        "recommendation": "Create a Gateway interface in the Use Case layer. Implement in infrastructure.",
    },
    "tight_coupling_new_keyword": {
        "severity": "MEDIUM",
        "description": "Dependencies instantiated with 'new' instead of injection.",
        "recommendation": "Replace new-instantiation with constructor injection.",
    },
    "broad_catch": {
        "severity": "LOW",
        "description": "Catching generic Exception or Throwable swallows unexpected errors.",
        "recommendation": "Catch only specific exception types. Let unknowns propagate to @ControllerAdvice.",
    },
    "clean": {
        "severity": "NONE",
        "description": "No anti-patterns detected.",
        "recommendation": "No action required.",
    },
}


class AntiPatternModel:
    """
    Wraps the trained RandomForest anti-pattern classifier.

    Usage:
        model = AntiPatternModel()
        prediction = model.predict(features_dict)
        prediction, confidence = model.predict_with_confidence(features_dict)
    """

    def __init__(self, model_path: str = "models/architecture_aware_antipattern_model.joblib"):
        print("🔧 Loading Anti-Pattern model...")
        bundle = joblib.load(model_path)

        self.model         = bundle["model"]           # full sklearn Pipeline
        self.encoder       = bundle["label_encoder"]
        # Load the exact feature list saved at training time
        self.feature_order = bundle.get("feature_columns", self._default_features())
        self.ANTI_PATTERN_INFO = ANTI_PATTERN_INFO

        real_acc = bundle.get("real_test_accuracy")
        if real_acc:
            print(f"✅ Anti-Pattern model loaded  "
                  f"(real-file test accuracy: {real_acc*100:.1f}%,  "
                  f"features: {len(self.feature_order)})")
        else:
            print(f"✅ Anti-Pattern model loaded  (features: {len(self.feature_order)})")

    # ── Public API ─────────────────────────────────────────────────────────

    def predict(self, features: dict) -> str:
        """Return the predicted anti-pattern label for a single file."""
        df  = self._build_row(features)
        enc = self.model.predict(df)[0]
        return self.encoder.inverse_transform([enc])[0]

    def predict_with_confidence(self, features: dict) -> Tuple[str, float]:
        """Return (anti_pattern_label, confidence_0_to_1)."""
        df = self._build_row(features)
        # RandomForest supports predict_proba; LinearSVC does not
        if hasattr(self.model, "predict_proba"):
            proba = self.model.predict_proba(df)[0]
            idx   = int(proba.argmax())
            conf  = float(proba[idx])
        else:
            enc  = self.model.predict(df)[0]
            idx  = int(enc)
            conf = 1.0
        label = self.encoder.inverse_transform([idx])[0]
        return label, conf

    def analyze_project(self, files: list) -> dict:
        """Analyze a list of FileFeatures objects and return a summary."""
        from collections import defaultdict

        violations = defaultdict(lambda: {"files": [], "layers": set(), "confidences": []})
        clean_files = []

        for f in files:
            features       = f.dict() if hasattr(f, "dict") else dict(f)
            ap, conf       = self.predict_with_confidence(features)
            if ap == "clean":
                clean_files.append(f.file_name)
            else:
                layer = self.detect_layer(features)
                violations[ap]["files"].append(f.file_name)
                violations[ap]["layers"].add(layer)
                violations[ap]["confidences"].append(conf)

        ap_details = []
        for ap, data in violations.items():
            info     = ANTI_PATTERN_INFO.get(ap, {
                "severity": "UNKNOWN", "description": ap,
                "recommendation": "Review manually"})
            avg_conf = sum(data["confidences"]) / len(data["confidences"])
            ap_details.append({
                "type":           ap,
                "severity":       info["severity"],
                "affected_layer": ", ".join(sorted(data["layers"])),
                "confidence":     round(avg_conf, 2),
                "files":          data["files"],
                "description":    info["description"],
                "recommendation": info["recommendation"],
            })

        severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "NONE": 4}
        ap_details.sort(key=lambda x: severity_order.get(x["severity"], 5))

        total_viol = sum(len(d["files"]) for d in violations.values())
        arch       = files[0].architecture_pattern if files else "unknown"

        summary = (
            f"✅ No violations in {len(files)} files"
            if total_viol == 0
            else f"⚠️ {total_viol} violations across {len(files)} files"
        )

        return {
            "architecture_pattern": arch,
            "total_files_analyzed": len(files),
            "total_violations":     total_viol,
            "anti_patterns":        ap_details,
            "summary":              summary,
        }

    def detect_layer(self, features: dict) -> str:
        """Infer the layer name from available feature signals."""
        layer = str(features.get("layer", "")).lower().strip()
        if layer and layer not in ("unknown", "none", ""):
            return layer
        # Inference fallback
        if features.get("has_http_handling"):
            return "controller"
        if features.get("repository_deps", 0) > 0 and features.get("has_data_access"):
            return "service"
        if features.get("has_data_access") and not features.get("has_http_handling"):
            return "repository"
        return "service"

    # ── Row builder ────────────────────────────────────────────────────────

    def _build_row(self, features: dict) -> pd.DataFrame:
        """
        Build a single-row DataFrame matching the feature_order saved in the
        training bundle.

        *** CRITICAL: apply log1p to dependency columns ***
        Training Cell 2 transforms all 9 dependency columns with np.log1p().
        We must do the same here or the model receives out-of-distribution values.
        """
        row = {}

        # Resolve layer and layer_arch FIRST (needed below)
        layer = self.detect_layer(features)
        arch  = str(features.get("architecture_pattern", "layered"))
        layer_arch = f"{layer}_{arch}"

        for col in self.feature_order:
            if col in DEPENDENCY_COLS:
                # ── FIX 1: apply log1p to match training transformation ──
                raw = float(features.get(col, 0))
                row[col] = float(np.log1p(raw))

            elif col == "layer":
                row[col] = layer

            elif col == "architecture_pattern":
                row[col] = arch

            elif col == "layer_arch":
                # ── FIX 2: build interaction feature exactly as training Cell 2 ──
                row[col] = layer_arch

            elif col in ("uses_new_keyword", "has_broad_catch",
                         "has_business_logic", "has_data_access",
                         "has_http_handling", "has_validation",
                         "has_transaction", "violates_layer_separation"):
                row[col] = bool(features.get(col, False))

            elif col == "architecture_confidence":
                row[col] = float(features.get(col, 0.8))

            else:
                # All remaining numeric features
                row[col] = float(features.get(col, 0))

        df = pd.DataFrame([row], columns=self.feature_order)
        return df

    @staticmethod
    def _default_features():
        """Fallback feature list if bundle has no 'feature_columns' key."""
        return [
            'layer', 'architecture_pattern', 'architecture_confidence',
            'loc', 'methods', 'classes', 'avg_cc', 'imports', 'annotations',
            'controller_deps', 'service_deps', 'repository_deps', 'entity_deps',
            'adapter_deps', 'port_deps', 'usecase_deps', 'gateway_deps',
            'total_cross_layer_deps',
            'has_business_logic', 'has_data_access', 'has_http_handling',
            'has_validation', 'has_transaction',
            'uses_new_keyword', 'has_broad_catch',
            'violates_layer_separation',
            'layer_arch',
        ]
    
    
    
    # """
# app/model_loader.py  — v3  (CRITICAL BUG FIX)
# ──────────────────────────────────────────────────────────────────
# Architecture-Aware Anti-Pattern Classification Model loader.

# ROOT CAUSE OF 47.9% ACCURACY — NOW FIXED:
#   Training notebook Cell 2 applies np.log1p() to ALL dependency columns
#   before fitting the model.  The v2 loader passed RAW integer values,
#   so every prediction that relied on dependency counts landed on the
#   wrong side of every decision-tree split threshold.

#   Example: repo_deps=2  →  model expected log1p(2)=1.099, got raw 2.0
#            The model's split thresholds were learned on 0–1.1 scale,
#            so raw integer 2 looked like an extreme outlier and sent
#            the prediction down the wrong branch.

# CHANGES FROM v2:
#   1. ✅ CRITICAL: _build_row() now applies np.log1p() to all 9 dep cols
#      before passing them to the pipeline (matches training Cell 2)
#   2. ✅ layer_arch value uses EXACT same format as training: 'layer_architecture'
#   3. ✅ Feature columns list matches EXACTLY the order saved in the .joblib
#      (training Column order: layer first, then architecture_pattern, etc.)
#   4. ✅ No other changes — all other model_loader logic was correct
# ──────────────────────────────────────────────────────────────────
# """

# import joblib
# import numpy as np
# import pandas as pd
# from typing import List, Dict, Optional
# from collections import defaultdict
# from app.schemas import FileFeatures, AntiPatternDetail, EnhancedPredictionResult


# # Dependency columns that were log-transformed in training Cell 2.
# # MUST match the list in the training notebook exactly.
# _DEP_COLS_TO_LOG1P = [
#     'controller_deps', 'service_deps', 'repository_deps', 'entity_deps',
#     'adapter_deps', 'port_deps', 'usecase_deps', 'gateway_deps',
#     'total_cross_layer_deps',
# ]


# class AntiPatternModel:

#     # ── Anti-pattern metadata for all 4 architectures ─────────────────
#     ANTI_PATTERN_INFO = {
#         # ── LAYERED / MVC ──────────────────────────────────────────────
#         "layer_skip_in_layered": {
#             "severity": "HIGH",
#             "description": "Controller directly accesses Repository, bypassing the Service layer.",
#             "recommendation": "Remove the Repository dependency from the Controller. Introduce a Service class that wraps Repository operations and inject only the Service into the Controller."
#         },
#         "reversed_dependency_in_layered": {
#             "severity": "HIGH",
#             "description": "Service layer depends on Controller, violating the direction of layered architecture.",
#             "recommendation": "Remove all Controller imports and dependencies from the Service layer. Services should never depend on Controllers."
#         },
#         "business_logic_in_controller_layered": {
#             "severity": "MEDIUM",
#             "description": "Business logic (conditionals, calculations, loops) found in Controller layer instead of Service layer.",
#             "recommendation": "Move business logic into the Service layer. Controllers should only parse requests, call one Service method, and return the response."
#         },
#         "missing_transaction_in_layered": {
#             "severity": "HIGH",
#             "description": "Service method performs database write operations without @Transactional, risking partial writes.",
#             "recommendation": "Add @Transactional to all data-modifying Service methods. Use @Transactional(readOnly=true) for read-only methods."
#         },

#         # ── HEXAGONAL ──────────────────────────────────────────────────
#         "missing_port_adapter_in_hexagonal": {
#             "severity": "CRITICAL",
#             "description": "Domain/Service layer directly references Spring Data Repository (infrastructure), breaking the Hexagonal boundary.",
#             "recommendation": "Create a Port interface in the domain package. Implement it with an Adapter in the infrastructure package. Inject the Port (not the Adapter) into the domain service."
#         },
#         "framework_dependency_in_domain_hexagonal": {
#             "severity": "CRITICAL",
#             "description": "Domain/Service class imports Spring or JPA framework annotations, violating Hexagonal Architecture's dependency rule.",
#             "recommendation": "Remove all framework annotations (@Service, @Entity, @Autowired, @Column) from domain classes. Keep domain classes as plain Java objects."
#         },
#         "adapter_without_port_hexagonal": {
#             "severity": "MEDIUM",
#             "description": "Adapter class does not implement a Port interface, breaking the hexagonal contract.",
#             "recommendation": "Create a Port interface and make the Adapter implement it. This allows the domain to depend only on the Port abstraction."
#         },

#         # ── CLEAN ARCHITECTURE ─────────────────────────────────────────
#         "outer_depends_on_inner_clean": {
#             "severity": "CRITICAL",
#             "description": "Outer layer (Controller/Interface Adapter) directly depends on inner layer details (Entity or Repository), violating the Dependency Rule.",
#             "recommendation": "Use DTOs and Gateway/Use Case interfaces to cross layer boundaries. Controllers should only depend on Use Case input/output ports."
#         },
#         "usecase_framework_coupling_clean": {
#             "severity": "CRITICAL",
#             "description": "Use Case layer is coupled with framework annotations (@Service, @Repository, etc.), making it framework-dependent.",
#             "recommendation": "Remove all framework annotations from Use Case classes. Use Cases should be plain Java classes with no dependency on Spring or JPA."
#         },
#         "entity_framework_coupling_clean": {
#             "severity": "MEDIUM",
#             "description": "Domain Entity has JPA framework annotations (@Entity, @Table, @Column), coupling domain to persistence.",
#             "recommendation": "Separate domain entities from JPA persistence entities. Keep domain entities as pure Java objects; create separate @Entity classes in the infrastructure layer."
#         },
#         "missing_gateway_interface_clean": {
#             "severity": "HIGH",
#             "description": "Use Case accesses Repository directly without a Gateway interface, violating the Dependency Rule.",
#             "recommendation": "Create a Gateway interface in the Use Case/domain layer. Implement it in the infrastructure layer. The Use Case should depend only on the Gateway interface."
#         },

#         # ── COMMON (all architectures) ─────────────────────────────────
#         "broad_catch": {
#             "severity": "MEDIUM",
#             "description": "Generic exception catching (Exception or Throwable) swallows unexpected errors and hides failures.",
#             "recommendation": "Catch only specific, expected exception types. Let unexpected exceptions propagate to a global @ControllerAdvice handler. Always log the full stack trace."
#         },
#         "no_validation": {
#             "severity": "MEDIUM",
#             "description": "Controller endpoint accepts @RequestBody without @Valid annotation, allowing malformed data into business logic.",
#             "recommendation": "Add @Valid annotation to all @RequestBody parameters. Annotate DTO fields with constraints (@NotNull, @NotBlank, @Size, @Email)."
#         },
#         "tight_coupling_new_keyword": {
#             "severity": "MEDIUM",
#             "description": "Dependencies are instantiated with 'new' instead of constructor injection, preventing testability.",
#             "recommendation": "Replace 'new' instantiation with constructor injection. Declare dependencies as final fields and let Spring manage object creation."
#         },
#         "clean": {
#             "severity": "NONE",
#             "description": "No anti-patterns detected.",
#             "recommendation": "Code follows architectural best practices."
#         }
#     }

#     def __init__(self):
#         print("🔧 Loading Anti-Pattern Classification model...")
#         bundle = joblib.load("models/architecture_aware_antipattern_model.joblib")
#         self.model         = bundle["model"]
#         self.encoder       = bundle["label_encoder"]
#         self.model_version = bundle.get("model_version", "v2")

#         # ── Use the EXACT feature columns saved during training ────────
#         # These were saved in Cell 14 as X_train.columns.tolist()
#         # and must be used here to guarantee the DataFrame passed to
#         # the pipeline has columns in the correct order and names.
#         self._saved_feature_cols = bundle.get("feature_columns", None)

#         # Fallback: manually match Cell 3 output column order
#         # (only used if model was saved without 'feature_columns' key)
#         self._fallback_feature_cols = [
#             'layer', 'architecture_pattern', 'architecture_confidence',
#             'loc', 'methods', 'classes', 'avg_cc', 'imports', 'annotations',
#             'controller_deps', 'service_deps', 'repository_deps', 'entity_deps',
#             'adapter_deps', 'port_deps', 'usecase_deps', 'gateway_deps',
#             'total_cross_layer_deps',
#             'has_business_logic', 'has_data_access', 'has_http_handling',
#             'has_validation', 'has_transaction', 'uses_new_keyword',
#             'has_broad_catch', 'violates_layer_separation',
#             'layer_arch',
#         ]

#         if self._saved_feature_cols:
#             self.feature_cols = self._saved_feature_cols
#             print(f"   Feature columns: loaded from model ({len(self.feature_cols)} cols)")
#         else:
#             self.feature_cols = self._fallback_feature_cols
#             print(f"   Feature columns: using fallback order ({len(self.feature_cols)} cols)")

#         print(f"✅ Anti-Pattern model loaded! (version={self.model_version})")
#         print(f"   Classes: {list(self.encoder.classes_)}")

#     # ── Core prediction ────────────────────────────────────────────────

#     def _build_row(self, features: dict) -> pd.DataFrame:
#         """
#         Build a single-row DataFrame with all required features.

#         CRITICAL: Dependency columns are log1p-transformed here to match
#         the preprocessing applied in training notebook Cell 2:
#             df[dependency_cols] = np.log1p(df[dependency_cols])
#         """
#         layer = self._resolve_layer(features)
#         arch  = features.get('architecture_pattern', 'layered')

#         # ── 1. Read raw dependency values ──────────────────────────────
#         raw_controller_deps      = float(features.get('controller_deps',       0))
#         raw_service_deps         = float(features.get('service_deps',          0))
#         raw_repository_deps      = float(features.get('repository_deps',       0))
#         raw_entity_deps          = float(features.get('entity_deps',           0))
#         raw_adapter_deps         = float(features.get('adapter_deps',          0))
#         raw_port_deps            = float(features.get('port_deps',             0))
#         raw_usecase_deps         = float(features.get('usecase_deps',          0))
#         raw_gateway_deps         = float(features.get('gateway_deps',          0))
#         raw_total_cross_layer    = float(features.get('total_cross_layer_deps', 0))

#         # ── 2. Apply log1p — MATCHES TRAINING CELL 2 ──────────────────
#         #   Training: df[dependency_cols] = np.log1p(df[dependency_cols])
#         #   This is the fix for the 47.9% → expected 70%+ accuracy jump
#         controller_deps      = np.log1p(raw_controller_deps)
#         service_deps         = np.log1p(raw_service_deps)
#         repository_deps      = np.log1p(raw_repository_deps)
#         entity_deps          = np.log1p(raw_entity_deps)
#         adapter_deps         = np.log1p(raw_adapter_deps)
#         port_deps            = np.log1p(raw_port_deps)
#         usecase_deps         = np.log1p(raw_usecase_deps)
#         gateway_deps         = np.log1p(raw_gateway_deps)
#         total_cross_layer    = np.log1p(raw_total_cross_layer)

#         # ── 3. Assemble full row ───────────────────────────────────────
#         row = {
#             # Categorical
#             'layer'                  : layer,
#             'architecture_pattern'   : arch,
#             'layer_arch'             : f"{layer}_{arch}",

#             # Boolean
#             'has_business_logic'     : bool(features.get('has_business_logic',      False)),
#             'has_data_access'        : bool(features.get('has_data_access',         False)),
#             'has_http_handling'      : bool(features.get('has_http_handling',       False)),
#             'has_validation'         : bool(features.get('has_validation',          False)),
#             'has_transaction'        : bool(features.get('has_transaction',         False)),
#             'violates_layer_separation': bool(features.get('violates_layer_separation', False)),
#             'uses_new_keyword'       : bool(features.get('uses_new_keyword',        False)),
#             'has_broad_catch'        : bool(features.get('has_broad_catch',         False)),

#             # Numeric (not log-transformed)
#             'architecture_confidence': float(features.get('architecture_confidence', 0.5)),
#             'loc'                    : float(features.get('loc',     0)),
#             'methods'                : float(features.get('methods', 0)),
#             'classes'                : float(features.get('classes', 0)),
#             'avg_cc'                 : float(features.get('avg_cc',  1.0)),
#             'imports'                : float(features.get('imports', 0)),
#             'annotations'            : float(features.get('annotations', 0)),

#             # Dependency columns — LOG1P TRANSFORMED ✅
#             'controller_deps'        : controller_deps,
#             'service_deps'           : service_deps,
#             'repository_deps'        : repository_deps,
#             'entity_deps'            : entity_deps,
#             'adapter_deps'           : adapter_deps,
#             'port_deps'              : port_deps,
#             'usecase_deps'           : usecase_deps,
#             'gateway_deps'           : gateway_deps,
#             'total_cross_layer_deps' : total_cross_layer,
#         }

#         df = pd.DataFrame([row])

#         # Ensure every column the model expects exists (fill 0 for any gaps)
#         for col in self.feature_cols:
#             if col not in df.columns:
#                 df[col] = 0

#         # Return columns in the exact order the model was trained on
#         return df[[c for c in self.feature_cols if c in df.columns]]

#     def predict(self, features: dict) -> str:
#         df       = self._build_row(features)
#         pred_enc = self.model.predict(df)[0]
#         return self.encoder.inverse_transform([pred_enc])[0]

#     def predict_with_confidence(self, features: dict) -> tuple:
#         df       = self._build_row(features)
#         pred_enc = self.model.predict(df)[0]
#         label    = self.encoder.inverse_transform([pred_enc])[0]

#         if hasattr(self.model, 'predict_proba'):
#             probs      = self.model.predict_proba(df)[0]
#             confidence = float(probs[pred_enc])
#         else:
#             confidence = 0.85

#         return label, confidence

#     # ── Layer resolution ───────────────────────────────────────────────

#     def _resolve_layer(self, features: dict) -> str:
#         """
#         Determine the layer for a file.
#         Priority: explicit 'layer' field → inferred from features.
#         """
#         layer = str(features.get('layer', '')).strip().lower()
#         if layer and layer not in ('unknown', 'other', ''):
#             return layer
#         return self._infer_layer(features)

#     def _infer_layer(self, features: dict) -> str:
#         """Infer layer from feature signals when 'layer' is not provided."""
#         arch = features.get('architecture_pattern', 'layered')

#         if features.get('has_http_handling', False):
#             return 'controller'
#         if features.get('repository_deps', 0) > 0 or features.get('has_data_access', False):
#             return 'repository' if arch in ('layered', 'mvc') else 'adapter'
#         if features.get('port_deps', 0) > 0:
#             return 'port' if arch == 'hexagonal' else 'service'
#         if features.get('gateway_deps', 0) > 0 or features.get('usecase_deps', 0) > 0:
#             return 'usecase' if arch == 'clean_architecture' else 'service'
#         if features.get('has_business_logic', False):
#             return 'service'
#         if features.get('annotations', 0) > 5:
#             return 'entity'
#         return 'service'

#     # ── Project-level analysis ─────────────────────────────────────────

#     def analyze_project(self, files: List[FileFeatures]) -> EnhancedPredictionResult:
#         violations   = defaultdict(lambda: {'files': [], 'layers': set(), 'confidences': []})
#         architecture = files[0].architecture_pattern if files else "unknown"

#         for file_data in files:
#             features           = file_data.dict()
#             anti_pattern, conf = self.predict_with_confidence(features)
#             if anti_pattern == "clean":
#                 continue
#             layer = self._resolve_layer(features)
#             violations[anti_pattern]['files'].append(file_data.file_name)
#             violations[anti_pattern]['layers'].add(layer)
#             violations[anti_pattern]['confidences'].append(conf)

#         ap_details = []
#         for ap, data in violations.items():
#             info = self.ANTI_PATTERN_INFO.get(ap, {
#                 "severity":       "UNKNOWN",
#                 "description":    "Unknown anti-pattern",
#                 "recommendation": "Review code manually"
#             })
#             avg_conf = sum(data['confidences']) / len(data['confidences'])
#             ap_details.append(AntiPatternDetail(
#                 type           = ap,
#                 severity       = info['severity'],
#                 affected_layer = ", ".join(sorted(data['layers'])),
#                 confidence     = round(avg_conf, 2),
#                 files          = data['files'],
#                 description    = info['description'],
#                 recommendation = info['recommendation'],
#             ))

#         severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "NONE": 4}
#         ap_details.sort(key=lambda x: severity_order.get(x.severity, 5))

#         total_violations = sum(len(d['files']) for d in violations.values())
#         if total_violations == 0:
#             summary = f"✅ No architectural violations detected in {len(files)} files"
#         else:
#             critical = sum(1 for ap in ap_details if ap.severity == "CRITICAL")
#             high     = sum(1 for ap in ap_details if ap.severity == "HIGH")
#             medium   = sum(1 for ap in ap_details if ap.severity == "MEDIUM")
#             summary  = f"⚠️ Found {total_violations} violations across {len(files)} files\n"
#             if critical: summary += f"🔴 {critical} CRITICAL issues\n"
#             if high:     summary += f"🟠 {high} HIGH severity issues\n"
#             if medium:   summary += f"🟡 {medium} MEDIUM severity issues"

#         return EnhancedPredictionResult(
#             architecture_pattern = architecture,
#             total_files_analyzed = len(files),
#             total_violations     = total_violations,
#             anti_patterns        = ap_details,
#             summary              = summary,
#         )