import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi import Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, text
import logging
import pandas as pd

# Try to import the optimizer function; fall back gracefully if not available
pick_fpl_team = None
try:
    from optimisation_fpl import pick_fpl_team as _pick_fpl_team
    pick_fpl_team = _pick_fpl_team
    logging.getLogger(__name__).info("Optimizer function 'pick_fpl_team' imported from optimisation_fpl.py")
except Exception as _imp_err:
    logging.getLogger(__name__).warning(f"Optimizer import failed: {_imp_err}")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()  # Load variables from your .env file
DB_URL = os.getenv("NEON_DATABASE_URL")

if not DB_URL:
    logger.error("FATAL: NEON_DATABASE_URL not found in .env file")
    raise ValueError("NEON_DATABASE_URL not found in .env file")
else:
    logger.info("Database URL loaded from .env file.")

# Create a database engine
try:
    engine = create_engine(DB_URL)
    logger.info("Database engine created successfully.")
    # Test connection
    with engine.connect() as connection:
        logger.info("Successfully connected to the database.")
except Exception as e:
    logger.error(f"Failed to create database engine or connect: {e}")
    # Depending on your needs, you might want the app to fail startup here
    # raise e # Uncomment this line to stop the app if DB connection fails


app = FastAPI(
    title="FPL Predictor API",
    description="API for fetching FPL data and predictions."
)

# Allows your React frontend (running on localhost:5173) to talk to this backend
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    # Add Vercel deployment URL here later 
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], # Allows all methods (GET, POST, etc.)
    allow_headers=["*"], # Allows all headers
)
logger.info(f"CORS middleware configured for origins: {origins}")


def get_data_for_optimizer() -> tuple[list[list[object]], pd.DataFrame]:
    """
    Build optimizer input from database tables.
    Returns:
      - optimizer_data: list of [player_id, name, position_str, team_id, cost_float, gw1, gw2, gw3, gw4]
      - players_df: DataFrame with at least columns ['player_id','name','position','team_id','cost']
    Notes:
      - gw1 is the most recent expected_points, gw4 is older.
      - cost is in millions (e.g., 5.5), not in tenths.
    """
    with engine.connect() as connection:
        # Rank latest four gameweeks per player by gameweek desc
        sql = text(
            """
            WITH ranked AS (
                SELECT 
                    player_id,
                    COALESCE(expected_points, total_points::float, 0.0) AS ep,
                    gameweek,
                    ROW_NUMBER() OVER (PARTITION BY player_id ORDER BY gameweek DESC) AS rn
                FROM player_gameweek_history
            )
            SELECT 
                p.id AS player_id,
                p.web_name AS name,
                p.first_name,
                p.second_name,
                p.team_id,
                p.position,
                p.now_cost,
                COALESCE(MAX(CASE WHEN r.rn = 1 THEN r.ep END), 0.0) AS gw1,
                COALESCE(MAX(CASE WHEN r.rn = 2 THEN r.ep END), 0.0) AS gw2,
                COALESCE(MAX(CASE WHEN r.rn = 3 THEN r.ep END), 0.0) AS gw3,
                COALESCE(MAX(CASE WHEN r.rn = 4 THEN r.ep END), 0.0) AS gw4
            FROM players p
            LEFT JOIN ranked r ON r.player_id = p.id
            GROUP BY p.id, p.web_name, p.first_name, p.second_name, p.team_id, p.position, p.now_cost
            ORDER BY p.id ASC
            """
        )
        rows = connection.execute(sql).fetchall()

    # Map positions to optimizer labels
    pos_map = {1: "GK", 2: "DEF", 3: "MID", 4: "FWD"}
    data: list[list[object]] = []
    records: list[dict[str, object]] = []
    for r in rows:
        m = dict(r._mapping)
        position_str = pos_map.get(int(m["position"]) if m["position"] is not None else 0, "MID")
        cost_float = float(m["now_cost"] or 0) / 10.0
        row = [
            int(m["player_id"]),
            str(m["name"] or ""),
            position_str,
            int(m["team_id"]) if m["team_id"] is not None else 0,
            cost_float,
            float(m["gw1"] or 0.0),
            float(m["gw2"] or 0.0),
            float(m["gw3"] or 0.0),
            float(m["gw4"] or 0.0),
        ]
        data.append(row)
        records.append({
            "player_id": int(m["player_id"]),
            "name": str(m["name"] or ""),
            "first_name": m.get("first_name"),
            "second_name": m.get("second_name"),
            "position": position_str,
            "team_id": int(m["team_id"]) if m["team_id"] is not None else 0,
            "cost": cost_float,
        })

    players_df = pd.DataFrame.from_records(records)
    return data, players_df


@app.get("/")
def read_root():
    """A simple root endpoint to check if the server is running."""
    logger.info("Root endpoint '/' accessed.")
    return {"message": "Welcome to the FPL Predictor API!"}

@app.get("/api/v1/players")
def get_all_players():
    """
    Fetches all players from the 'players' table in the Neon database.
    """
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
            items = [dict(row._mapping) for row in result]
            return {"items": items, "total": total}
    except Exception as e:
        logger.error(f"Error fetching paged fixtures: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")


@app.get("/api/v1/gameweeks")
def get_all_gameweeks():
    """
    Fetches all player gameweek history entries from the 'player_gameweek_history' table.
    """
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
                            # No matching players -> empty result fast-path
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
    

@app.get("/api/v1/optimize-team")
def get_optimized_team():
    if pick_fpl_team is None:
        raise HTTPException(status_code=500, detail="Optimizer function not imported. Check server logs.")
        
    try:
        # 1. Get data formatted for the optimizer
        optimizer_data, players_df = get_data_for_optimizer()
        if not optimizer_data:
            raise HTTPException(status_code=404, detail="No player data found to optimize.")

        # 2. Run the optimizer function
        # This will return just the IDs of the chosen players
        squad_ids, xi_ids, captain_id = pick_fpl_team(optimizer_data)
        
        if not squad_ids:
            raise HTTPException(status_code=500, detail="Optimizer failed to find a solution.")

        # 3. Get the full player details for the frontend
        # Convert players_df to a dict for easy lookup
        players_dict = players_df.set_index('player_id').to_dict('index')
        
        optimal_squad = []
        for pid in squad_ids:
            player_data = players_dict.get(pid)
            if player_data:
                # Add back the fields the frontend expects
                player_data['id'] = pid
                player_data['now_cost'] = int(player_data['cost'] * 10)
                # Map position string back to integer
                pos_map = {'GK': 1, 'DEF': 2, 'MID': 3, 'FWD': 4}
                player_data['position'] = pos_map.get(player_data['position'])
                # Ensure web_name exists for frontend display
                if 'web_name' not in player_data or not player_data.get('web_name'):
                    player_data['web_name'] = player_data.get('name', '')
                # Include first_name/second_name so UI can render full name
                player_data['first_name'] = player_data.get('first_name')
                player_data['second_name'] = player_data.get('second_name')
                optimal_squad.append(player_data)

        return {
            "squad": optimal_squad,
            "xi_ids": xi_ids,
            "captain_id": captain_id
        }

    except Exception as e:
        logging.error(f"Error in optimizer endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")