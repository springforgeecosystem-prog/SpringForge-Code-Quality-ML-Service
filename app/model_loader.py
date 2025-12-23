import joblib
import pandas as pd

class AntiPatternModel:

    def __init__(self):
        print("🔧 Loading ML model...")
        bundle = joblib.load("models/architecture_aware_antipattern_model.joblib")
        self.model = bundle["model"]
        self.encoder = bundle["label_encoder"]
        print("✅ Model loaded successfully!")

        # Required training feature order
        self.feature_order = [
            'architecture_pattern',
            'architecture_confidence',
            'loc',
            'methods',
            'classes',
            'avg_cc',
            'imports',
            'annotations',
            'controller_deps',
            'service_deps',
            'repository_deps',
            'entity_deps',
            'adapter_deps',
            'port_deps',
            'usecase_deps',
            'gateway_deps',
            'total_cross_layer_deps',
            'has_business_logic',
            'has_data_access',
            'has_http_handling',
            'has_validation',
            'has_transaction',
            'violates_layer_separation'
        ]

    def predict(self, features: dict):

        # Build dataframe with correct column order
        df = pd.DataFrame([[features[col] for col in self.feature_order]],
                          columns=self.feature_order)

        # Predict encoded label
        pred_encoded = self.model.predict(df)[0]

        # Decode label
        anti_pattern = self.encoder.inverse_transform([pred_encoded])[0]

        return anti_pattern
