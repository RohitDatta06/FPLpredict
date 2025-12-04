import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi import Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, text
import logging
import pandas as pd

# ========== NEW IMPORTS FOR INTEGRATION ==========
from predictor import FPLPredictor
from optimizer import pick_fpl_team_with_predictions

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()  # Load variables from your .env file
DB_URL = os.getenv("NEON_DATABASE_URL")

# ========== CHANGED: Make database optional ==========
engine = None
if not DB_URL:
    logger.warning("⚠ NEON_DATABASE_URL not found in .env file - database features will be disabled")
else:
    logger.info("Database URL loaded from .env file.")
    # Create a database engine
    try:
        engine = create_engine(DB_URL)
        logger.info("✓ Database engine created successfully.")
        # Test connection - OPTIONAL NOW
        try:
            with engine.connect() as connection:
                logger.info("✓ Successfully connected to the database.")
        except Exception as conn_err:
            logger.warning(f"⚠ Database connection test failed: {conn_err}")
            logger.warning("⚠ Database endpoints will not work, but optimizer will still function")
    except Exception as e:
        logger.error(f"Failed to create database engine: {e}")
        logger.warning("⚠ Continuing without database - only optimizer endpoint will work")
        engine = None

# ========== UPDATED: Use the fixed CSV file ==========
predictor = FPLPredictor(
    data_path='data/fixed_merged_gw.csv',  # CHANGED: Updated to use fixed CSV
    models_path='models/fpl_models.pkl'
)

# Load models on startup
try:
    if predictor.load_models():
        logger.info("✓ XGBoost models loaded successfully!")
    else:
        logger.warning("⚠ Models not found. You may need to train them first.")
except Exception as e:
    logger.error(f"Failed to load models: {e}")

app = FastAPI(
    title="FPL Predictor API",
    description="API for fetching FPL data and predictions."
)

# Allows your React frontend (running on localhost:5173) to talk to this backend
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    https://fpl-team-generator.onrender.com
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], # Allows all methods (GET, POST, etc.)
    allow_headers=["*"], # Allows all headers
)
logger.info(f"CORS middleware configured for origins: {origins}")


@app.get("/")
def read_root():
    """A simple root endpoint to check if the server is running."""
    logger.info("Root endpoint '/' accessed.")
    return {
        "message": "Welcome to the FPL Predictor API!",
        "database_connected": engine is not None,
        "models_loaded": bool(predictor.models)
    }

@app.get("/api/v1/players")
def get_all_players():
    """
    Fetches all players from the 'players' table in the Neon database.
    """
    if engine is None:
        raise HTTPException(status_code=503, detail="Database not available. Please configure NEON_DATABASE_URL in .env file")
    
    logger.info("'/api/v1/players' endpoint accessed.")
    try:
        with engine.connect() as connection:
            # Query to select all relevant columns from the players table
            query = text("""
                SELECT id, first_name, second_name, web_name, team_id, position, now_cost 
                FROM players 
                ORDER BY now_cost DESC
            """)
            result = connection.execute(query)
            
            # Fetch all rows and convert them using ._mapping for dictionary-like access
            players = [dict(row._mapping) for row in result]
            logger.info(f"Successfully fetched {len(players)} players from the database.")
            
            # Important: FastAPI automatically converts this list of dicts to JSON
            return players
            
    except Exception as e:
        logger.error(f"Error fetching players from database: {e}", exc_info=True)
        # Raise an HTTPException to return a proper error response to the client
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")


@app.get("/api/v1/players/paged")
def get_players_paged(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    sort_by: str = Query("id"),
    sort_dir: str = Query("asc"),
    q: str | None = Query(None)
):
    """
    Paginated players with total count.
    """
    if engine is None:
        raise HTTPException(status_code=503, detail="Database not available. Please configure NEON_DATABASE_URL in .env file")
    
    logger.info(f"'/api/v1/players/paged' accessed with limit={limit}, offset={offset}.")
    try:
        with engine.connect() as connection:
            # Whitelist sortable columns
            allowed = {
                "id": "id",
                "first_name": "first_name",
                "second_name": "second_name",
                "web_name": "web_name",
                "team_id": "team_id",
                "position": "position",
                "now_cost": "now_cost",
            }
            order_col = allowed.get(sort_by.lower(), "id")
            order_dir = "DESC" if sort_dir.lower() == "desc" else "ASC"
            where_clause = ""
            params = {"limit": limit, "offset": offset}
            if q:
                where_clause = (
                    " WHERE (web_name ILIKE :pattern OR first_name ILIKE :pattern OR "
                    " second_name ILIKE :pattern OR CAST(id AS TEXT) ILIKE :pattern OR CAST(team_id AS TEXT) ILIKE :pattern)"
                )
                params["pattern"] = f"%{q}%"

            total_query = text(f"SELECT COUNT(*) AS total FROM players{where_clause}")
            total = connection.execute(total_query, params).scalar() or 0

            data_query = text(
                f"""
                SELECT id, first_name, second_name, web_name, team_id, position, now_cost 
                FROM players
                {where_clause}
                ORDER BY {order_col} {order_dir} NULLS LAST
                LIMIT :limit OFFSET :offset
                """
            )
            result = connection.execute(data_query, params)
            items = [dict(row._mapping) for row in result]
            return {"items": items, "total": total}
    except Exception as e:
        logger.error(f"Error fetching paged players: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")


@app.get("/api/v1/teams")
def get_all_teams():
    """
    Fetches all teams from the 'teams' table in the Neon database.
    """
    if engine is None:
        raise HTTPException(status_code=503, detail="Database not available. Please configure NEON_DATABASE_URL in .env file")
    
    logger.info("'/api/v1/teams' endpoint accessed.")
    try:
        with engine.connect() as connection:
            query = text(
                """
                SELECT id, name, short_name
                FROM teams
                ORDER BY id ASC
                """
            )
            result = connection.execute(query)
            teams = [dict(row._mapping) for row in result]
            logger.info(f"Successfully fetched {len(teams)} teams from the database.")
            return teams
    except Exception as e:
        logger.error(f"Error fetching teams from database: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")


@app.get("/api/v1/teams/paged")
def get_teams_paged(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    sort_by: str = Query("id"),
    sort_dir: str = Query("asc"),
    q: str | None = Query(None)
):
    """
    Paginated teams with total count.
    """
    if engine is None:
        raise HTTPException(status_code=503, detail="Database not available. Please configure NEON_DATABASE_URL in .env file")
    
    logger.info(f"'/api/v1/teams/paged' accessed with limit={limit}, offset={offset}.")
    try:
        with engine.connect() as connection:
            allowed = {
                "id": "id",
                "name": "name",
                "short_name": "short_name",
            }
            order_col = allowed.get(sort_by.lower(), "id")
            order_dir = "DESC" if sort_dir.lower() == "desc" else "ASC"
            where_clause = ""
            params = {"limit": limit, "offset": offset}
            if q:
                where_clause = (
                    " WHERE (name ILIKE :pattern OR short_name ILIKE :pattern OR CAST(id AS TEXT) ILIKE :pattern)"
                )
                params["pattern"] = f"%{q}%"

            total_query = text(f"SELECT COUNT(*) AS total FROM teams{where_clause}")
            total = connection.execute(total_query, params).scalar() or 0

            data_query = text(
                f"""
                SELECT id, name, short_name
                FROM teams
                {where_clause}
                ORDER BY {order_col} {order_dir} NULLS LAST
                LIMIT :limit OFFSET :offset
                """
            )
            result = connection.execute(data_query, params)
            items = [dict(row._mapping) for row in result]
            return {"items": items, "total": total}
    except Exception as e:
        logger.error(f"Error fetching paged teams: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")


@app.get("/api/v1/fixtures")
def get_all_fixtures():
    """
    Fetches all fixtures from the 'fixtures' table in the Neon database.
    """
    if engine is None:
        raise HTTPException(status_code=503, detail="Database not available. Please configure NEON_DATABASE_URL in .env file")
    
    logger.info("'/api/v1/fixtures' endpoint accessed.")
    try:
        with engine.connect() as connection:
            query = text(
                """
                SELECT id, event, kickoff_time, team_h_id, team_a_id, team_h_difficulty, team_a_difficulty
                FROM fixtures
                ORDER BY kickoff_time NULLS LAST, id ASC
                """
            )
            result = connection.execute(query)
            fixtures = [dict(row._mapping) for row in result]
            logger.info(f"Successfully fetched {len(fixtures)} fixtures from the database.")
            return fixtures
    except Exception as e:
        logger.error(f"Error fetching fixtures from database: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")


@app.get("/api/v1/fixtures/paged")
def get_fixtures_paged(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    sort_by: str = Query("id"),
    sort_dir: str = Query("asc")
):
    """
    Paginated fixtures with total count.
    """
    if engine is None:
        raise HTTPException(status_code=503, detail="Database not available. Please configure NEON_DATABASE_URL in .env file")
    
    logger.info(f"'/api/v1/fixtures/paged' accessed with limit={limit}, offset={offset}.")
    try:
        with engine.connect() as connection:
            allowed = {
                "id": "id",
                "event": "event",
                "kickoff_time": "kickoff_time",
                "team_h_id": "team_h_id",
                "team_a_id": "team_a_id",
                "team_h_difficulty": "team_h_difficulty",
                "team_a_difficulty": "team_a_difficulty",
            }
            order_col = allowed.get(sort_by.lower(), "id")
            order_dir = "DESC" if sort_dir.lower() == "desc" else "ASC"
            total_query = text("SELECT COUNT(*) AS total FROM fixtures")
            total = connection.execute(total_query).scalar() or 0

            data_query = text(
                f"""
                SELECT id, event, kickoff_time, team_h_id, team_a_id, team_h_difficulty, team_a_difficulty
                FROM fixtures
                ORDER BY {order_col} {order_dir} NULLS LAST
                LIMIT :limit OFFSET :offset
                """
            )
            result = connection.execute(data_query, {"limit": limit, "offset": offset})
            items = [dict(row._mapping) for r in result]
            return {"items": items, "total": total}
    except Exception as e:
        logger.error(f"Error fetching paged fixtures: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")


@app.get("/api/v1/gameweeks")
def get_all_gameweeks():
    """
    Fetches all player gameweek history entries from the 'player_gameweek_history' table.
    """
    if engine is None:
        raise HTTPException(status_code=503, detail="Database not available. Please configure NEON_DATABASE_URL in .env file")
    
    logger.info("'/api/v1/gameweeks' endpoint accessed.")
    try:
        with engine.connect() as connection:
            query = text(
                """
                SELECT 
                    id,
                    player_id,
                    fixture_id,
                    opponent_team_id,
                    gameweek,
                    minutes,
                    goals_scored,
                    assists,
                    clean_sheets,
                    goals_conceded,
                    own_goals,
                    penalties_saved,
                    penalties_missed,
                    yellow_cards,
                    red_cards,
                    saves,
                    starts,
                    total_points,
                    bonus,
                    bps,
                    influence,
                    creativity,
                    threat,
                    ict_index,
                    expected_goals,
                    expected_assists,
                    expected_goal_involvements,
                    expected_goals_conceded,
                    expected_points,
                    was_home,
                    kickoff_time,
                    player_value,
                    difficulty,
                    player_team_position,
                    transfers_in,
                    transfers_out,
                    transfers_balance,
                    selected
                FROM player_gameweek_history
                ORDER BY gameweek ASC, id ASC
                """
            )
            result = connection.execute(query)
            gws = [dict(row._mapping) for row in result]
            logger.info(f"Successfully fetched {len(gws)} gameweek history rows from the database.")
            return gws
    except Exception as e:
        logger.error(f"Error fetching gameweek history from database: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")


@app.get("/api/v1/gameweeks/paged")
def get_gameweeks_paged(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    sort_by: str = Query("id"),
    sort_dir: str = Query("asc"),
    q: str | None = Query(None),
):
    """
    Paginated player gameweek history with total count.
    """
    if engine is None:
        raise HTTPException(status_code=503, detail="Database not available. Please configure NEON_DATABASE_URL in .env file")
    
    logger.info(f"'/api/v1/gameweeks/paged' accessed with limit={limit}, offset={offset}.")
    try:
        with engine.connect() as connection:
            allowed = {
                "id": "id",
                "player_id": "player_id",
                "fixture_id": "fixture_id",
                "opponent_team_id": "opponent_team_id",
                "gameweek": "gameweek",
                "minutes": "minutes",
                "goals_scored": "goals_scored",
                "assists": "assists",
                "clean_sheets": "clean_sheets",
                "goals_conceded": "goals_conceded",
                "own_goals": "own_goals",
                "penalties_saved": "penalties_saved",
                "penalties_missed": "penalties_missed",
                "yellow_cards": "yellow_cards",
                "red_cards": "red_cards",
                "saves": "saves",
                "starts": "starts",
                "total_points": "total_points",
                "bonus": "bonus",
                "bps": "bps",
                "influence": "influence",
                "creativity": "creativity",
                "threat": "threat",
                "ict_index": "ict_index",
                "expected_goals": "expected_goals",
                "expected_assists": "expected_assists",
                "expected_goal_involvements": "expected_goal_involvements",
                "expected_goals_conceded": "expected_goals_conceded",
                "expected_points": "expected_points",
                "was_home": "was_home",
                "kickoff_time": "kickoff_time",
                "player_value": "player_value",
                "difficulty": "difficulty",
                "player_team_position": "player_team_position",
                "transfers_in": "transfers_in",
                "transfers_out": "transfers_out",
                "transfers_balance": "transfers_balance",
                "selected": "selected",
            }
            order_col = allowed.get(sort_by.lower(), "id")
            order_dir = "DESC" if sort_dir.lower() == "desc" else "ASC"

            # Search handling
            where_clause = ""
            params: dict[str, object] = {"limit": limit, "offset": offset}
            if q is not None and q.strip() != "":
                raw = q.strip()
                # Case 1: numeric search (player_id or gameweek)
                try:
                    qint = int(raw)
                    where_clause = " WHERE (player_id = :qint OR gameweek = :qint)"
                    params["qint"] = qint
                except ValueError:
                    # Case 2: name search - find matching player IDs by tokens, then filter gameweeks by those IDs
                    tokens = [t for t in raw.split() if t]
                    if tokens:
                        conds = []
                        p = {}
                        for idx, tok in enumerate(tokens):
                            key = f"p{idx}"
                            p[key] = f"%{tok}%"
                            conds.append(
                                f"(web_name ILIKE :{key} OR first_name ILIKE :{key} OR second_name ILIKE :{key})"
                            )
                        players_sql = f"SELECT id FROM players WHERE {' AND '.join(conds)}"
                        player_ids = []
                        try:
                            rows = connection.execute(text(players_sql), p).fetchall()
                            player_ids = [int(r[0]) for r in rows if r[0] is not None]
                        except Exception as e:
                            logger.warning(f"Player name search failed; falling back to no filter. Error: {e}")
                            player_ids = []

                        if player_ids:
                            ids_list = ",".join(str(int(pid)) for pid in player_ids)
                            where_clause = f" WHERE player_id IN ({ids_list})"
                        else:
                            # No matching players → empty result fast-path
                            return {"items": [], "total": 0}

            total_query = text(f"SELECT COUNT(*) AS total FROM player_gameweek_history{where_clause}")
            total = connection.execute(total_query, params).scalar() or 0

            data_query = text(
                f"""
                SELECT 
                    id,
                    player_id,
                    fixture_id,
                    opponent_team_id,
                    gameweek,
                    minutes,
                    goals_scored,
                    assists,
                    clean_sheets,
                    goals_conceded,
                    own_goals,
                    penalties_saved,
                    penalties_missed,
                    yellow_cards,
                    red_cards,
                    saves,
                    starts,
                    total_points,
                    bonus,
                    bps,
                    influence,
                    creativity,
                    threat,
                    ict_index,
                    expected_goals,
                    expected_assists,
                    expected_goal_involvements,
                    expected_goals_conceded,
                    expected_points,
                    was_home,
                    kickoff_time,
                    player_value,
                    difficulty,
                    player_team_position,
                    transfers_in,
                    transfers_out,
                    transfers_balance,
                    selected
                FROM player_gameweek_history
                {where_clause}
                ORDER BY {order_col} {order_dir} NULLS LAST
                LIMIT :limit OFFSET :offset
                """
            )
            result = connection.execute(data_query, params)
            items = [dict(row._mapping) for row in result]
            return {"items": items, "total": total}
    except Exception as e:
        logger.error(f"Error fetching paged gameweeks: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")


# ========== COMPLETELY REWRITTEN OPTIMIZE ENDPOINT ==========
@app.get("/api/v1/optimize-team")
def get_optimized_team():
    """
    Fetch optimized 15-player squad using ML predictions + OR-Tools optimizer.
    Returns squad in format expected by frontend.
    Works WITHOUT database - uses CSV file only.
    """
    logger.info("'/api/v1/optimize-team' endpoint accessed.")
    
    try:
        # Step 1: Load CSV data
        logger.info("Loading player data from CSV...")
        predictor.load_data()
        
        # Step 2: Generate ML predictions for all players
        logger.info("Generating ML predictions...")
        df = predictor.predict_all_players()
        
        # Step 3: Format data for optimizer
        logger.info("Preparing data for optimizer...")
        optimizer_data = predictor.get_optimizer_format()
        
        # Step 4: Run optimizer
        logger.info("Running optimizer...")
        squad_ids, xi_ids, captain_id = pick_fpl_team_with_predictions(optimizer_data)
        
        if not squad_ids:
            raise HTTPException(status_code=500, detail="Optimizer failed to find a solution.")
        
        # Step 5: Transform CSV format to Frontend format
        logger.info("Transforming data for frontend...")
        
        # Position mapping: string to number
        pos_to_num = {'GK': 1, 'DEF': 2, 'MID': 3, 'FWD': 4}
        
        # Get full player details from dataframe
        squad_players = []
        for idx in squad_ids:
            row = df.iloc[idx]
            
            # Extract name components
            if 'name' in df.columns:
                full_name = str(row['name'])
                # Try to split into first/last
                name_parts = full_name.split(' ', 1)
                first_name = name_parts[0] if len(name_parts) > 0 else None
                second_name = name_parts[1] if len(name_parts) > 1 else None
                web_name = full_name
            else:
                first_name = row.get('first_name')
                second_name = row.get('second_name')
                web_name = f"{first_name} {second_name}".strip() if first_name or second_name else "Unknown"
            
            # Get position as number
            pos_str = row.get('pos_std', row.get('position', 'MID'))
            position_num = pos_to_num.get(pos_str, 3)
            
            # Get cost in tenths (frontend expects now_cost in tenths, e.g., 55 = £5.5m)
            if 'now_cost' in df.columns:
                cost_tenths = int(row['now_cost'] * 10)
            elif 'value' in df.columns:
                cost_tenths = int(row['value'] * 10)
            else:
                cost_tenths = 0
            
            # Get team_id (use team name as ID if no numeric team_id)
            team_id = row.get('team_id', 0)
            if team_id == 0 and 'team' in df.columns:
                # Use hash of team name as a pseudo-ID
                team_id = hash(str(row['team'])) % 100
            
            player_dict = {
                'id': int(idx),
                'first_name': first_name,
                'second_name': second_name,
                'web_name': web_name,
                'team_id': int(team_id),
                'position': position_num,
                'now_cost': cost_tenths
            }
            squad_players.append(player_dict)
        
        # Step 6: Return in format expected by frontend
        response = {
            'squad': squad_players,
            'xi_ids': [int(idx) for idx in xi_ids],
            'captain_id': int(captain_id) if captain_id is not None else None
        }
        
        logger.info(f"✓ Successfully optimized team: {len(squad_players)} players, XI: {len(xi_ids)}, Captain: {captain_id}")
        return response
        
    except Exception as e:
        logger.error(f"Error in optimizer endpoint: {e}", exc_info=True)

        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")
