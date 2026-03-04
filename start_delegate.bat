@echo off
set API_URL=http://127.0.0.1:8080
echo Starting QE Delegate on http://localhost:8502
streamlit run quality_engineering_agentic_framework\web\ui\delegate.py --server.port 8502
