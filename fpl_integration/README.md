# FPL Predictor Backend

A Fantasy Premier League team optimization system that combines XGBoost machine learning predictions with OR-Tools mathematical optimization to generate optimal 15-player squads.

## 🏗️ Architecture

```
Backend Flow:
CSV Data → XGBoost Models → Predictions → OR-Tools Optimizer → Optimal Squad
```

## 📁 File Structure

### Core Files

#### `main.py`
**Purpose:** FastAPI application server and API endpoints

**What it does:**
- Serves REST API endpoints for the frontend
- Connects to Neon PostgreSQL database (optional)
- Initializes the FPL Predictor on startup
- Loads pre-trained XGBoost models
- Provides endpoints for:
  - `/api/v1/players` - Get all players from database
  - `/api/v1/teams` - Get all teams
  - `/api/v1/fixtures` - Get fixture information
  - `/api/v1/gameweeks` - Get player gameweek history
  - `/api/v1/optimize-team` - **Main endpoint** that generates optimal squad

**Key Functions:**
- `read_root()` - Health check endpoint
- `get_optimized_team()` - Runs ML predictions + optimization pipeline

---

#### `predictor.py`
**Purpose:** XGBoost machine learning predictor class

**What it does:**
- Loads player data from CSV files
- Trains position-specific XGBoost models (GK, DEF, MID, FWD)
- Generates predicted points for all players
- Formats predictions for the optimizer

**Key Methods:**
- `load_data()` - Loads CSV and standardizes position column
- `train_models()` - Trains separate XGBoost model for each position
- `predict_all_players()` - Generates predictions using trained models
- `get_optimizer_format()` - Converts predictions to optimizer input format
- `save_models()` / `load_models()` - Persist/load trained models

**Features Used:**
Models train on all numeric columns including:
- Performance stats: goals_scored, assists, minutes, clean_sheets
- Advanced metrics: creativity, influence, threat, ict_index, bps
- Game context: difficulty, was_home
- Player info: now_cost, selected_by_percent

---

#### `optimizer.py`
**Purpose:** OR-Tools constraint-based optimization

**What it does:**
- Takes predicted points from ML models
- Applies FPL constraints:
  - Budget limit (£100m)
  - Position requirements (2 GK, 5 DEF, 5 MID, 3 FWD)
  - Max 3 players per team
  - Must select valid starting XI formation
  - Captain selection (2x points)
- Uses Mixed Integer Programming (MIP) to find optimal squad
- Brute-force searches through starting XI combinations

**Key Function:**
- `pick_fpl_team_with_predictions(data)` - Main optimization function

**Returns:**
- `squad_ids` - List of 15 player indices for full squad
- `xi_ids` - List of 11 player indices for starting lineup
- `captain_id` - Index of captain (highest predicted points in XI)

---

#### `coefficients.py`
**Purpose:** Statistical analysis for feature importance

**What it does:**
- Analyzes correlation between features and total_points
- Calculates Variance Inflation Factor (VIF) for multicollinearity
- Identifies top 10 most predictive features per position
- Generates correlation heatmaps

**Output:**
- Top correlated features for each position
- VIF scores to detect redundant features
- Visualization of feature relationships

**Note:** Currently analytical only - not integrated into prediction pipeline

---

### Data Files

#### `data/fixed_merged_gw.csv`
**Purpose:** Training and prediction data

**Required Columns:**
- `name` - Player name
- `position` - Player position (GK/DEF/MID/FWD)
- `team` - Team name
- `now_cost` - Player price (in tenths, e.g., 55 = £5.5m)
- `selected_by_percent` - Ownership percentage
- Performance stats: `goals_scored`, `assists`, `minutes`, `clean_sheets`, `goals_conceded`
- Advanced metrics: `creativity`, `influence`, `threat`, `bonus`, `bps`, `ict_index`
- Cards: `yellow_cards`, `red_cards`
- Context: `difficulty`, `was_home`, `opponent`

---

#### `models/fpl_models.pkl`
**Purpose:** Serialized trained XGBoost models

**Contents:**
```python
{
    'GK': {'model': XGBRegressor, 'feature_cols': [...]},
    'DEF': {'model': XGBRegressor, 'feature_cols': [...]},
    'MID': {'model': XGBRegressor, 'feature_cols': [...]},
    'FWD': {'model': XGBRegressor, 'feature_cols': [...]}
}
```

---

### Configuration Files

#### `.env`
**Purpose:** Environment variables (DO NOT COMMIT TO GIT)

**Required Variables:**
```
NEON_DATABASE_URL=postgresql://user:password@host/database
```

**Note:** Database is optional - system works with CSV-only mode

---

## 🚀 Local Development Setup

### Prerequisites
- Python 3.8 or higher
- Node.js 16 or higher
- npm or yarn

### Backend Setup

#### 1. Install Python Dependencies

```bash
cd backend
pip install -r requirements.txt
```

#### 2. Configure Environment

Create a `.env` file in the `backend/` directory:
```bash
# Optional - only needed for database features
NEON_DATABASE_URL=your_neon_database_url_here
```

#### 3. Prepare Data

Place your player data CSV in:
```
backend/data/fixed_merged_gw.csv
```

Ensure it has the required columns listed above.

#### 4. Train Models (First Time Only)

```python
from predictor import FPLPredictor

predictor = FPLPredictor(
    data_path='data/fixed_merged_gw.csv',
    models_path='models/fpl_models.pkl'
)

predictor.load_data()
predictor.train_models()
predictor.save_models()
```

This creates `models/fpl_models.pkl` with trained models.

#### 5. Run the Backend Server

```bash
cd backend
uvicorn main:app --reload --port 8000
```

The backend API will be available at:
- **API:** `http://localhost:8000`
- **Interactive Docs:** `http://localhost:8000/docs` (Swagger UI)

---

### Frontend Setup

#### 1. Install Node Dependencies

```bash
cd frontend
npm install
```

#### 2. Run the Frontend Development Server

```bash
npm run dev
```

The frontend will be available at:
- **App:** `http://localhost:5173`

---

### Running Both Together

**Terminal 1 - Backend:**
```bash
cd backend
uvicorn main:app --reload --port 8000
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm run dev
```

Then open your browser to `http://localhost:5173`

The frontend will automatically connect to the backend at `http://localhost:8000`

---

### Accessing the Application

1. **Start both servers** (backend on port 8000, frontend on port 5173)
2. **Open browser** to `http://localhost:5173`
3. **Navigate to Optimizer** tab in the UI
4. **Click "Generate Optimal Squad"** to see ML-powered team optimization in action

---

## 🔧 How It Works

### Optimization Pipeline

1. **Load Data**
   ```python
   predictor.load_data()  # Load CSV
   ```

2. **Generate Predictions**
   ```python
   df = predictor.predict_all_players()  # ML predictions
   optimizer_data = predictor.get_optimizer_format()
   ```

3. **Run Optimizer**
   ```python
   squad_ids, xi_ids, captain_id = pick_fpl_team_with_predictions(optimizer_data)
   ```

4. **Format Response**
   ```python
   # Transform to frontend format
   return {
       'squad': [...],  # 15 players
       'xi_ids': [...],  # 11 starters
       'captain_id': ...  # Captain
   }
   ```

---

## 📊 Model Training Details

### XGBoost Configuration

```python
XGBRegressor(
    n_estimators=200,      # Number of trees
    max_depth=6,           # Tree depth
    learning_rate=0.1,     # Step size
    subsample=0.9,         # Row sampling
    colsample_bytree=0.9,  # Column sampling
    random_state=42        # Reproducibility
)
```

### Training Strategy

- **Separate models per position:** Different stats matter for different positions
- **80/20 train/test split:** Standard validation approach
- **All numeric features:** Uses every numeric column except target
- **Target variable:** `total_points` from historical gameweeks

---

## 🔍 API Endpoints

### Main Optimization Endpoint

**GET** `/api/v1/optimize-team`

**Response:**
```json
{
    "squad": [
        {
            "id": 123,
            "first_name": "Mohamed",
            "second_name": "Salah",
            "web_name": "Salah",
            "team_id": 10,
            "position": 3,
            "now_cost": 130
        },
        // ... 14 more players
    ],
    "xi_ids": [123, 456, 789, ...],
    "captain_id": 123
}
```

### Database Endpoints (Optional)

- **GET** `/api/v1/players` - All players
- **GET** `/api/v1/players/paged` - Paginated players with search
- **GET** `/api/v1/teams` - All teams
- **GET** `/api/v1/fixtures` - All fixtures
- **GET** `/api/v1/gameweeks` - Player gameweek history

---

## 🐛 Troubleshooting

### "Feature names mismatch" Error
**Cause:** CSV columns don't match training data  
**Fix:** Ensure CSV has `now_cost` and `selected_by_percent` columns

### "No models found" Warning
**Cause:** Models haven't been trained yet  
**Fix:** Run training script to generate `models/fpl_models.pkl`

### Database Connection Failed
**Cause:** Invalid `NEON_DATABASE_URL` or network issue  
**Fix:** System will continue without database, optimizer still works

### CORS Error in Frontend
**Cause:** Frontend origin not allowed  
**Fix:** Add your frontend URL to `origins` list in `main.py`

---

## 📝 Notes

- **CSV vs Database:** System works with CSV-only. Database is optional for extended features.
- **Model Retraining:** Retrain models when new gameweek data is available
- **Prediction Accuracy:** Models learn from historical patterns, actual results may vary
- **Optimization Time:** Finding optimal squad takes 5-30 seconds depending on data size

---

## 🤝 Contributing

When adding new features:
1. Update this README
2. Add dependencies to `requirements.txt`
3. Document new API endpoints
4. Test with both CSV-only and database modes

---

## 📄 License

[Your License Here]

---

## 👥 Authors

[Your Names Here]
