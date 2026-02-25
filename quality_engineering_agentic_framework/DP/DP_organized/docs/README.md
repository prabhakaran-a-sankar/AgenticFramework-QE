# DefectPredictor - AI-Powered Bug Prediction

ML system that predicts software bugs at story-level with 88.3% accuracy.

## Features
- JIRA Integration (read + write)
- Story-level predictions
- Real-time predictions via AWS Lambda
- Professional Accenture dashboard

## Tech Stack
- Python 3.12
- Scikit-learn (RandomForest)
- AWS Lambda
- JIRA API

## Model Performance
- R²: 88.3%
- MAE: 1.11 bugs
- Training data: 5,024 sprints (24 real + 5,000 synthetic)

## Deployment
- Lambda URL: https://yxdu2uvygeo24efvchw4lvwuhm0engkw.lambda-url.eu-north-1.on.aws/
- Dashboard: https://defect-predictor-models-vijetha.s3.eu-north-1.amazonaws.com/defect-predictor-professional.html
