import os
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import logging

# --- CONFIGURATION ---
# Make sure your merged_gw.csv file is in the same folder and named this
CSV_FILE_NAME = "merged_gw - merged_gw.csv.csv" 
TABLE_NAME = "player_gameweek_history"

def load_csv_to_db():
    """
    Loads the historical gameweek data from the CSV file into the database.
    This is a one-time operation to populate the history table.
    """
    print(f"Starting to load {CSV_FILE_NAME} into {TABLE_NAME}...")

    # Load database URL
    load_dotenv()
    db_url = os.getenv("NEON_DATABASE_URL")
    if not db_url:
        print("Error: NEON_DATABASE_URL not found in .env file.")
        return

    try:
        engine = create_engine(db_url)

        # Load the CSV file
        print(f"Reading {CSV_FILE_NAME}...")
        # Check if file exists
        if not os.path.exists(CSV_FILE_NAME):
            print(f"Error: File not found at {os.path.abspath(CSV_FILE_NAME)}")
            print("Please make sure your CSV file is in the root FPLpredict folder.")
            return

        df = pd.read_csv(CSV_FILE_NAME)
        print(f"Successfully read {len(df)} rows from CSV.")

        # --- Column Name Mapping ---
        # Map CSV column names to your database column names
        df.columns = df.columns.str.strip()  # Remove any leading/trailing spaces

        column_mapping = {
            'element': 'player_id',
            'fixture': 'fixture_id',
            'opponent_team': 'opponent_team_id',
            'GW': 'gameweek',
            'starts': 'starts',
            'value': 'player_value',
            'xP': 'expected_points',
            'playerteamposition': 'player_team_position',
            'difficulty': 'difficulty',
            'was_home': 'was_home',
            'kickoff_time': 'kickoff_time',
            # Additional columns present in the CSV that map directly
            'minutes': 'minutes',
            'goals_scored': 'goals_scored',
            'assists': 'assists',
            'clean_sheets': 'clean_sheets',
            'goals_conceded': 'goals_conceded',
            'own_goals': 'own_goals',
            'penalties_saved': 'penalties_saved',
            'penalties_missed': 'penalties_missed',
            'yellow_cards': 'yellow_cards',
            'red_cards': 'red_cards',
            'saves': 'saves',
            'total_points': 'total_points',
            'bonus': 'bonus',
            'bps': 'bps',
            'influence': 'influence',
            'creativity': 'creativity',
            'threat': 'threat',
            'ict_index': 'ict_index',
            'expected_goals': 'expected_goals',
            'expected_assists': 'expected_assists',
            'expected_goal_involvements': 'expected_goal_involvements',
            'expected_goals_conceded': 'expected_goals_conceded',
            'transfers_in': 'transfers_in',
            'transfers_out': 'transfers_out',
            'transfers_balance': 'transfers_balance',
            'selected': 'selected',
        }

        df = df.rename(columns=column_mapping)

        # Filter only to columns that actually exist in the database table
        db_columns = list(column_mapping.values())
        df_to_load = df[[col for col in db_columns if col in df.columns]]

        # --- Foreign key safety: filter rows that reference missing parents ---
        def filter_by_fk(df_in: pd.DataFrame, fk_col: str, parent_table: str, parent_id_col: str = 'id') -> pd.DataFrame:
            """Fetch valid IDs from parent table and drop rows with missing FK references."""
            if fk_col not in df_in.columns:
                return df_in
            try:
                with engine.connect() as conn:
                    rows = conn.execute(text(f"SELECT {parent_id_col} FROM {parent_table}")).fetchall()
                valid_ids = {r[0] for r in rows}
            except Exception as ex:
                print(f"Warning: Could not fetch {parent_table}.{parent_id_col} — skipping FK filter for {fk_col}. Error: {ex}")
                return df_in

            before = len(df_in)
            if before == 0:
                return df_in
            unique_fk = set(df_in[fk_col].dropna().unique().tolist())
            missing = sorted(unique_fk - valid_ids)
            if missing:
                print(f"Filtering out {len(missing)} missing {fk_col} values not present in {parent_table}: sample {missing[:10]}")
            df_out = df_in[df_in[fk_col].isin(valid_ids)].copy()
            dropped = before - len(df_out)
            if dropped:
                print(f"Dropped {dropped} rows due to missing {fk_col} foreign keys.")
            return df_out

        # Apply FK filters for known relations
        df_to_load = filter_by_fk(df_to_load, 'player_id', 'players')
        df_to_load = filter_by_fk(df_to_load, 'fixture_id', 'fixtures')
        # opponent_team_id may or may not be constrained; safe to filter if parent exists
        df_to_load = filter_by_fk(df_to_load, 'opponent_team_id', 'teams')

        # Normalize dtypes for readability/consistency
        if 'was_home' in df_to_load.columns:
            try:
                df_to_load['was_home'] = df_to_load['was_home'].astype('bool')
            except Exception:
                # If conversion fails, keep original
                pass

        # --- Load to Database ---
        print(f"Loading {len(df_to_load)} rows into {TABLE_NAME}...")
        # Use multi-row inserts for performance and chunk to avoid oversized statements
        df_to_load.to_sql(TABLE_NAME, engine, if_exists='append', index=False, method='multi', chunksize=1000)

        print(f"Successfully loaded historical data into {TABLE_NAME}.")

    except Exception as e:
        print(f"An error occurred: {e}")
        logging.error("Failed to load historical data", exc_info=True)

if __name__ == "__main__":
    load_csv_to_db()