from fastapi import FastAPI
from app.schemas import AntiPatternInput
from app.model_loader import AntiPatternModel

app = FastAPI(title="SpringForge AI-Driven Code Quality ML Service")

# Load ML model at startup (only once)
model = AntiPatternModel()

@app.get("/")
def home():
    return {"status": "SpringForge ML Server Running"}

@app.post("/predict-antipattern")
def predict_antipattern(input_data: AntiPatternInput):

    features = input_data.dict()
    prediction = model.predict(features)

    return {
        "anti_pattern": prediction
    }
