# app/main.py 
from fastapi import FastAPI
from typing import List
from app.schemas import AntiPatternInput, FileAnalysisInput, EnhancedPredictionResult
from app.model_loader import AntiPatternModel

app = FastAPI(title="SpringForge AI-Driven Code Quality ML Service")

# Load ML model at startup
model = AntiPatternModel()

@app.get("/")
def home():
    return {"status": "SpringForge ML Server Running"}

@app.post("/predict-antipattern")
def predict_antipattern(input_data: AntiPatternInput):
    """Single file prediction (backward compatible)"""
    features = input_data.dict()
    prediction = model.predict(features)
    
    return {
        "anti_pattern": prediction
    }

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
    results = model.analyze_project(input_data.files)
    return results