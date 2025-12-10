# 🧠 AI-Powered Fantasy Premier League Predictor & Optimizer

This project is an end-to-end AI system that predicts Fantasy Premier League (FPL) player points, builds an optimal squad under FPL constraints, and generates natural-language explanations using an LLM.  
Built as part of UIUC's SIGAIDA.

---

## 🚀 Features

- **Machine Learning Models**  
  - Trained multiple regression models: XGBoost, Linear Regression, Random Forest  
  - Predicts expected FPL points for all players each gameweek  
  - Custom feature engineering (fixtures, form, minutes, difficulty, etc.)

- **Squad Optimization (OR-Tools CP-SAT)**  
  - Integer Linear Programming solver  
  - Maximizes expected points  
  - Enforces FPL constraints: budget, formations, positions, max-3-per-team  
  - Produces optimal 15-man squad + starting XI in <1 second

- **LLM Integration (GPT-4 API)**  
  - Generates explanations for optimized squads  
  - Uses structured, grounded prompts for deterministic JSON output  
  - Provides reasoning, constraint impact, and risk/variance scoring

- **Full-Stack System**  
  - **Backend:** FastAPI (Python)  
  - **Frontend:** React + TypeScript  
  - **Data Layer:** Player stats, fixtures, engineered features  
  - Clear modular architecture for ML → Optimization → Explanation

---
