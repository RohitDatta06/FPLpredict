import axios from 'axios';

// The base URL of your FastAPI backend
const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

// This interface is correct and matches your 'players' table
export interface Player {
  id: number;
  first_name: string | null;
  second_name: string | null;
  web_name: string;
  team_id: number;
  position: number;
  now_cost: number;
}

// --- NEW INTERFACE ---
// This defines the object shape that the /optimize-team endpoint returns
export interface OptimizedTeamResponse {
  squad: Player[];      // The full 15-player squad
  xi_ids: number[];     // The 11 IDs of the starting players
  captain_id: number;   // The ID of the captain
}

// Function to fetch all players
export const getPlayers = async (): Promise<Player[]> => {
  try {
    const response = await axios.get<Player[]>(`${API_URL}/api/v1/players`);
    return response.data;
  } catch (error) {
    console.error(`Error fetching players from ${API_URL}/api/v1/players:`, error);
    throw error;
  }
};

export const getOptimizedTeam = async (
  lockedNames?: string[]
): Promise<OptimizedTeamResponse> => {
  try {
    const params: any = {};
    if (lockedNames && lockedNames.length > 0) {
      // axios will serialize this as locked[]=A&locked[]=B
      params.locked = lockedNames;
    }

    const response = await axios.get<OptimizedTeamResponse>(
      `${API_URL}/api/v1/optimize-team`,
      { params }
    );
    return response.data;
  } catch (error) {
    console.error(`Error fetching optimized team from ${API_URL}/api/v1/optimize-team:`, error);
    throw error;
  }
};


// --- All other functions (getPlayersPaged, getTeams, etc.) remain below ---

// Generic paginated result type
export interface PagedResult<T> {
  items: T[];
  total: number;
}

export type SortDir = 'asc' | 'desc';

export const getPlayersPaged = async (
  limit: number,
  offset: number,
  sortBy: keyof Player = 'id',
  sortDir: SortDir = 'asc',
  q?: string,
  signal?: AbortSignal
): Promise<PagedResult<Player>> => {
  const response = await axios.get<PagedResult<Player>>(
    `${API_URL}/api/v1/players/paged`,
    { params: { limit, offset, sort_by: sortBy, sort_dir: sortDir, q }, signal }
  );
  return response.data;
};

// Teams
export interface Team {
  id: number;
  name: string;
  short_name: string;
}

export const getTeams = async (): Promise<Team[]> => {
  try {
    const response = await axios.get<Team[]>(`${API_URL}/api/v1/teams`);
    return response.data;
  } catch (error) {
    console.error('Error fetching teams:', error);
    throw error;
  }
};

export const getTeamsPaged = async (
  limit: number,
  offset: number,
  sortBy: keyof Team = 'id',
  sortDir: SortDir = 'asc',
  q?: string,
  signal?: AbortSignal
): Promise<PagedResult<Team>> => {
  const response = await axios.get<PagedResult<Team>>(
    `${API_URL}/api/v1/teams/paged`,
    { params: { limit, offset, sort_by: sortBy, sort_dir: sortDir, q }, signal }
  );
  return response.data;
};

// Fixtures
export interface Fixture {
  id: number;
  event: number | null;
  kickoff_time: string | null; // ISO datetime string
  team_h_id: number;
  team_a_id: number;
  team_h_difficulty: number;
  team_a_difficulty: number;
}

export const getFixtures = async (): Promise<Fixture[]> => {
  try {
    const response = await axios.get<Fixture[]>(`${API_URL}/api/v1/fixtures`);
    return response.data;
  } catch (error) {
    console.error('Error fetching fixtures:', error);
    throw error;
  }
};

export const getFixturesPaged = async (
  limit: number,
  offset: number,
  sortBy: keyof Fixture = 'id',
  sortDir: SortDir = 'asc'
): Promise<PagedResult<Fixture>> => {
  const response = await axios.get<PagedResult<Fixture>>(
    `${API_URL}/api/v1/fixtures/paged`,
    { params: { limit, offset, sort_by: sortBy, sort_dir: sortDir } }
  );
  return response.data;
};

// Player Gameweek History
export interface GameweekEntry {
  id: number;
  player_id: number;
  fixture_id: number | null;
  opponent_team_id: number | null;
  gameweek: number | null;
  minutes: number | null;
  goals_scored: number | null;
  assists: number | null;
  clean_sheets: number | null;
  goals_conceded: number | null;
  own_goals: number | null;
  penalties_saved: number | null;
  penalties_missed: number | null;
  yellow_cards: number | null;
  red_cards: number | null;
  saves: number | null;
  starts: number | null;
  total_points: number | null;
  bonus: number | null;
  bps: number | null;
  influence: number | null;
  creativity: number | null;
  threat: number | null;
  ict_index: number | null;
  expected_goals: number | null;
  expected_assists: number | null;
  expected_goal_involvements: number | null;
  expected_goals_conceded: number | null;
  expected_points: number | null;
  was_home: boolean | null;
  kickoff_time?: string | null; // some rows may have been dropped during load
  player_value: number | null;
  difficulty: number | null;
  player_team_position: string | null;
  transfers_in: number | null;
  transfers_out: number | null;
  transfers_balance: number | null;
  selected: number | null;
}

export const getGameweekHistory = async (): Promise<GameweekEntry[]> => {
  try {
    const response = await axios.get<GameweekEntry[]>(`${API_URL}/api/v1/gameweeks`);
    return response.data;
  } catch (error) {
    console.error('Error fetching gameweek history:', error);
    throw error;
  }
};

export const getGameweekHistoryPaged = async (
  limit: number,
  offset: number,
  sortBy: keyof GameweekEntry = 'id',
  sortDir: SortDir = 'asc',
  q?: string,
  signal?: AbortSignal
): Promise<PagedResult<GameweekEntry>> => {
  const response = await axios.get<PagedResult<GameweekEntry>>(
    `${API_URL}/api/v1/gameweeks/paged`,
    { params: { limit, offset, sort_by: sortBy, sort_dir: sortDir, q }, signal }
  );
  return response.data;
};
