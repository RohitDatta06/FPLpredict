import axios from 'axios';

// The base URL of your FastAPI backend
// You'll run this locally first, so the default is usually:
const API_URL = 'http://127.0.0.1:8000';

// Define an interface for the Player data you expect
// Updated to match all columns in the 'players' database table
export interface Player {
  id: number;
  first_name: string | null; // Use string | null if the DB column can be empty
  second_name: string | null; // Use string | null if the DB column can be empty
  web_name: string;
  team_id: number;
  position: number;
  now_cost: number;
}

// Function to fetch all players
export const getPlayers = async (): Promise<Player[]> => {
  try {
    // Make sure your backend returns data matching the Player interface
    const response = await axios.get<Player[]>(`${API_URL}/api/v1/players`);
    return response.data;
  } catch (error) {
    console.error("Error fetching players:", error);
    // It's often better to return an empty array or handle the error
    // in the component rather than re-throwing here,
    // but re-throwing works for now.
    throw error;
  }
};

