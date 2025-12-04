import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split
import pickle


class FPLPredictor:
    def __init__(self, data_path='fpl_cleaned_data.csv', models_path='fpl_models.pkl'):
        self.data_path = data_path
        self.models_path = models_path
        self.df = None               # raw dataframe
        self.models = {}             # {'FWD': {'model': ..., 'feature_cols': [...]}, ...}

    # -------------------- I/O --------------------

    def load_data(self):
        """Load CSV and create a standardized position column."""
        self.df = pd.read_csv(self.data_path)
        print("CSV file loaded successfully")
        self._standardize_positions()
        return self.df

    def save_models(self, filepath=None):
        """Persist trained models."""
        path = filepath or self.models_path
        with open(path, 'wb') as f:
            pickle.dump(self.models, f)
        print(f"Models saved to {path}")

    def load_models(self, filepath=None):
        """Load pre-trained models if present."""
        path = filepath or self.models_path
        try:
            with open(path, 'rb') as f:
                self.models = pickle.load(f)
            print(f"Models loaded from {path}. Keys: {list(self.models.keys())}")
            return True
        except FileNotFoundError:
            print("No saved models found. Training new models...")
            return False

    # -------------------- Training --------------------

    def train_models(self, target_col='total_points'):
        """
        Train separate XGBoost models for each position (GK/DEF/MID/FWD).
        Uses all numeric columns except the target as features.
        """
        if self.df is None:
            raise ValueError("Call load_data() before train_models().")

        if target_col not in self.df.columns:
            raise KeyError(f"Target column '{target_col}' not found in data.")

        self.models = {}

        # Train per standardized position
        for pos_name in ['FWD', 'MID', 'DEF', 'GK']:
            pos_df = self.df[self.df['pos_std'] == pos_name]
            if pos_df.empty:
                print(f"⚠️  No rows for position {pos_name}; skipping.")
                continue

            # Features = numeric columns except target
            X = pos_df.drop(columns=[target_col], errors='ignore').select_dtypes(include=['number'])
            if X.empty:
                raise ValueError(f"No numeric features available for position {pos_name}.")

            y = pos_df[target_col]

            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42
            )

            model = xgb.XGBRegressor(
                random_state=42,
                n_estimators=200,
                max_depth=6,
                learning_rate=0.1,
                subsample=0.9,
                colsample_bytree=0.9,
            )
            model.fit(X_train, y_train)

            # ✅ store INSIDE the loop
            self.models[pos_name] = {
                'model': model,
                'feature_cols': X.columns.tolist()
            }
            print(f"✓ Trained model for {pos_name} (n={len(pos_df)})")

        if not self.models:
            raise ValueError("No models were trained. Check your data and columns.")
        return self.models

    # -------------------- Prediction --------------------

    def predict_all_players(self):
        """
        Add a 'predicted_points' column using the trained/loaded models.
        Iterates over whatever keys/models exist (no hardcoding assumptions).
        """
        if self.df is None:
            raise ValueError("Call load_data() before predict_all_players().")
        if not self.models:
            raise ValueError("No models loaded. Train or load models first.")

        frames = []
        for pos_name, model_info in self.models.items():
            pos_df = self.df[self.df['pos_std'] == pos_name].copy()
            if pos_df.empty:
                continue

            feature_cols = model_info['feature_cols']
            # keep only available columns (defensive)
            available = [c for c in feature_cols if c in pos_df.columns]
            if not available:
                raise ValueError(f"No matching feature columns for position {pos_name}.")

            X = pos_df[available]
            pred = model_info['model'].predict(X)
            pos_df['predicted_points'] = np.clip(pred, 0, None)   # min=0, no max

            frames.append(pos_df)

        if not frames:
            raise ValueError("No predictions produced. Check features/positions.")
        self.df = pd.concat(frames, ignore_index=True)
        print("✓ Predictions generated for all players")
        return self.df

    # -------------------- Optimizer adapter --------------------

    def get_optimizer_format(self):
        """
        Return list rows as:
        [player_id, name, position, team, cost, predicted_points]
        """
        if self.df is None or 'predicted_points' not in self.df.columns:
            raise ValueError("Run predict_all_players() before get_optimizer_format().")

        data = []
        for idx, row in self.df.iterrows():
            # name: prefer 'name'; else compose from first/second
            if 'name' in self.df.columns:
                name = str(row['name'])
            else:
                first = str(row.get('first_name', '')).strip()
                second = str(row.get('second_name', '')).strip()
                name = (first + ' ' + second).strip() or f"Player_{idx}"

            # team: try common variants
            team_val = row.get('team', row.get('team_name', 'Unknown'))

            # cost: now_cost (tenths) or value (tenths)
            if 'now_cost' in self.df.columns:
                cost_gbp = float(row['now_cost']) / 10.0
            elif 'value' in self.df.columns:
                cost_gbp = float(row['value']) / 10.0
            else:
                raise KeyError("No cost column found (expected 'now_cost' or 'value').")

            data.append([
                idx,                       # player_id (index as fallback)
                name,                      # name
                row['pos_std'],            # standardized position
                team_val,                  # team identifier/name
                cost_gbp,                  # cost in £
                float(row['predicted_points'])
            ])
        return data

    # -------------------- Internals --------------------

    def _standardize_positions(self):
        """
        Create df['pos_std'] with values in {'GK','DEF','MID','FWD'}
    from either numeric or string position columns. Adds helpful debugging.
        """
    # --- 1) Find the source column robustly ---
    # Normalize column names for safety (strip spaces)
        self.df.columns = [c.strip() for c in self.df.columns]

        candidates = ['element_type', 'position', 'pos', 'elementType']
        source_col = next((c for c in candidates if c in self.df.columns), None)
        if source_col is None:
            raise KeyError(f"No position column found (looked for {candidates}).")

        s = self.df[source_col]
        print(f"\n[Positions] Using source column: '{source_col}'")
        print("Raw unique values (first 20):", pd.Series(s.unique()).head(20).tolist())

    # --- 2) Build numeric + string normalized series ---
    # Numeric mapping (works when values are numeric)
        num_map = {1: 'GK', 2: 'DEF', 3: 'MID', 4: 'FWD'}
        s_num = s.map(num_map)

    # Also handle numeric-as-string like "1","2","3","4"
        str_to_num = {'1': 'GK', '2': 'DEF', '3': 'MID', '4': 'FWD'}

    # String normalization: strip, uppercase, map synonyms
        s_str = (
            s.astype(str)
            .str.strip()
            .str.upper()
            .replace({
                **str_to_num,
                'GKP': 'GK', 'GK': 'GK', 'GOALKEEPER': 'GK',
                'DEF': 'DEF', 'DEFENDER': 'DEF',
                'MID': 'MID', 'MIDFIELDER': 'MID',
                'FWD': 'FWD', 'FORWARD': 'FWD', 'STRIKER': 'FWD'
            })
        )

    # --- 3) Prefer numeric mapping, then cleaned string mapping ---
        pos_std = s_num.fillna(s_str)

    # --- 4) Final clamp to allowed set; anything else -> NaN (and warn) ---
        allowed = {'GK', 'DEF', 'MID', 'FWD'}
        pos_std = pos_std.where(pos_std.isin(allowed), other=pd.NA)

        self.df['pos_std'] = pos_std

    # --- 5) Debug summary ---
        print("Standardized position counts:\n", self.df['pos_std'].value_counts(dropna=False))
        if self.df['pos_std'].isna().any():
            bad = self.df.loc[self.df['pos_std'].isna(), source_col].unique()
            print("⚠️  Unmapped raw values found (showing up to 20):", pd.Series(bad).head(20).tolist())
            print("   → Update the mapping above to include these.")
