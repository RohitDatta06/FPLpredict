import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, text
import logging

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
    
