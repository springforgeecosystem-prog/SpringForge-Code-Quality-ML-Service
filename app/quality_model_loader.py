"""
quality_model_loader.py
────────────────────────────────────────────────────────────────────
Loads the trained XGBoost quality score regression model and exposes
a single predict() method that accepts raw file metrics and returns
a quality score (0–100) with label and display string.

Feature engineering inside this file EXACTLY mirrors the training
notebook (Cells 3–5) so predictions are consistent.
────────────────────────────────────────────────────────────────────
"""

import pickle
import json
import numpy as np
import pandas as pd
from typing import Optional


# ── Exact 33 feature columns produced by the training notebook ────
QUALITY_FEATURE_COLS = [
    'loc', 'methods', 'classes', 'avg_cc', 'imports', 'annotations',
    'controller_deps', 'service_deps', 'repository_deps',
    'adapter_deps', 'port_deps', 'total_cross_layer_deps',
    'has_business_logic', 'has_data_access', 'has_http_handling',
    'has_validation', 'has_transaction', 'violates_layer_separation',
    # engineered
    'import_ratio', 'annotation_density', 'method_density', 'dep_per_loc',
    'violation_score',
    # layer-specific flags
    'controller_has_repo_dep', 'service_missing_tx',
    'entity_too_complex', 'controller_biz_logic',
    # one-hot layer
    'layer_adapter', 'layer_controller', 'layer_entity',
    'layer_port', 'layer_repository', 'layer_service',
]


class QualityScoreModel:
    """Wraps the trained regression model with full feature engineering."""

    SCORE_LABELS = [
        (90, 'Excellent', '🟢'),
        (75, 'Good',      '🟢'),
        (60, 'Fair',      '🟠'),
        (40, 'Poor',      '🔴'),
        (0,  'Critical',  '🔴'),
    ]

    def __init__(self, model_path: str = "models/quality_score_model.pkl",
                 meta_path:  str = "models/quality_model_meta.json"):
        print("🔧 Loading Quality Score model...")
        with open(model_path, 'rb') as f:
            self.model = pickle.load(f)

        # Load metadata (feature list is the ground truth)
        try:
            with open(meta_path, 'r') as f:
                self.meta = json.load(f)
            self.feature_cols = self.meta.get('feature_names', QUALITY_FEATURE_COLS)
        except FileNotFoundError:
            print("⚠️  quality_model_meta.json not found — using default feature list")
            self.meta = {}
            self.feature_cols = QUALITY_FEATURE_COLS

        print(f"✅ Quality Score model loaded  "
              f"(RMSE={self.meta.get('performance', {}).get('test_rmse', 'N/A')}, "
              f"R²={self.meta.get('performance', {}).get('test_r2', 'N/A')})")

    # ── Public API ────────────────────────────────────────────────

    def predict(self, file_metrics: dict) -> dict:
        """
        Predict quality score for a single Java file.

        Parameters
        ----------
        file_metrics : dict
            Raw metrics from the JavaParser / radon extractor.
            Required keys match the AntiPatternInput schema plus 'layer'.

        Returns
        -------
        dict with keys:
            quality_score   float  0–100
            quality_label   str    e.g. 'Good'
            quality_emoji   str    e.g. '🟢'
            quality_display str    e.g. '🟢 Good (78/100)'
        """
        row = self._build_feature_row(file_metrics)
        raw_score = float(self.model.predict(row)[0])
        score = round(float(np.clip(raw_score, 0, 100)), 1)
        label, emoji = self._score_label(score)
        return {
            'quality_score'  : score,
            'quality_label'  : label,
            'quality_emoji'  : emoji,
            'quality_display': f'{emoji} {label} ({score:.0f}/100)',
        }

    def predict_batch(self, files_metrics: list) -> list:
        """Predict quality scores for a list of file metric dicts."""
        return [self.predict(m) for m in files_metrics]

    # ── Feature engineering (mirrors training notebook Cells 3–5) ─

    def _build_feature_row(self, m: dict) -> pd.DataFrame:
        """Build a single-row DataFrame with all 33 training features."""

        # ── 1. Raw numeric features (clip same as training) ───────
        loc         = float(m.get('loc',         0))
        loc         = min(loc, 1500)
        methods     = min(float(m.get('methods',     0)), 50)
        classes     = float(m.get('classes',     0))
        avg_cc      = float(m.get('avg_cc',      1.0))
        imports     = min(float(m.get('imports',     0)), 80)
        annotations = min(float(m.get('annotations', 0)), 60)

        ctrl_deps   = float(m.get('controller_deps',       0))
        svc_deps    = float(m.get('service_deps',          0))
        repo_deps   = float(m.get('repository_deps',       0))
        adp_deps    = float(m.get('adapter_deps',          0))
        port_deps   = float(m.get('port_deps',             0))
        total_deps  = float(m.get('total_cross_layer_deps', 0))

        # ── 2. Boolean features → int ──────────────────────────────
        def _b(key): return int(bool(m.get(key, False)))
        has_biz   = _b('has_business_logic')
        has_data  = _b('has_data_access')
        has_http  = _b('has_http_handling')
        has_valid = _b('has_validation')
        has_tx    = _b('has_transaction')
        violates  = _b('violates_layer_separation')

        # ── 3. Engineered ratio features ──────────────────────────
        import_ratio       = imports      / (loc + 1)
        annotation_density = annotations  / (loc + 1)
        method_density     = methods      / (loc + 1)
        dep_per_loc        = total_deps   / (loc + 1)

        # ── 4. Composite violation score ──────────────────────────
        violation_score = (
            violates  * 3 +
            has_biz   * 2 +
            (1 - has_valid) * 1 +
            min(total_deps, 5) * 0.5
        )

        # ── 5. Layer-specific anti-pattern flags ──────────────────
        layer = str(m.get('layer', 'controller')).lower()
        ctrl_repo_dep  = int(layer == 'controller' and repo_deps > 0)
        svc_missing_tx = int(layer == 'service'    and has_data == 1
                             and has_tx == 0)
        entity_complex = int(layer == 'entity'     and methods > 5)
        ctrl_biz_logic = int(layer == 'controller' and has_biz == 1)

        # ── 6. One-hot layer encoding ─────────────────────────────
        valid_layers = ['adapter', 'controller', 'entity',
                        'port', 'repository', 'service']
        layer_ohe = {f'layer_{l}': int(layer == l) for l in valid_layers}

        # ── Assemble row ──────────────────────────────────────────
        data = {
            'loc'                    : loc,
            'methods'                : methods,
            'classes'                : classes,
            'avg_cc'                 : avg_cc,
            'imports'                : imports,
            'annotations'            : annotations,
            'controller_deps'        : ctrl_deps,
            'service_deps'           : svc_deps,
            'repository_deps'        : repo_deps,
            'adapter_deps'           : adp_deps,
            'port_deps'              : port_deps,
            'total_cross_layer_deps' : total_deps,
            'has_business_logic'     : has_biz,
            'has_data_access'        : has_data,
            'has_http_handling'      : has_http,
            'has_validation'         : has_valid,
            'has_transaction'        : has_tx,
            'violates_layer_separation': violates,
            'import_ratio'           : import_ratio,
            'annotation_density'     : annotation_density,
            'method_density'         : method_density,
            'dep_per_loc'            : dep_per_loc,
            'violation_score'        : violation_score,
            'controller_has_repo_dep': ctrl_repo_dep,
            'service_missing_tx'     : svc_missing_tx,
            'entity_too_complex'     : entity_complex,
            'controller_biz_logic'   : ctrl_biz_logic,
            **layer_ohe,
        }

        row = pd.DataFrame([data])

        # Ensure every expected column exists (fill 0 for any missing)
        for col in self.feature_cols:
            if col not in row.columns:
                row[col] = 0

        return row[self.feature_cols]

    # ── Helpers ───────────────────────────────────────────────────

    @staticmethod
    def _score_label(score: float):
        labels = [
            (90, 'Excellent', '🟢'),
            (75, 'Good',      '🟢'),
            (60, 'Fair',      '🟠'),
            (40, 'Poor',      '🔴'),
            (0,  'Critical',  '🔴'),
        ]
        for threshold, label, emoji in labels:
            if score >= threshold:
                return label, emoji
        return 'Critical', '🔴'