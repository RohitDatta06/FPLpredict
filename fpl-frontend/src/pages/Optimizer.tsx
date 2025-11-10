import React, { useState } from 'react';
// Import the updated function and types from your api.ts file
import { getOptimizedTeam, type Player, type OptimizedTeamResponse } from '../services/api';

// Helper function to group players by position
const groupPlayersByPosition = (players: Player[]) => {
  const positionMap: { [key: number]: string } = { 1: 'Goalkeepers', 2: 'Defenders', 3: 'Midfielders', 4: 'Forwards' };
  
  const groups: Record<string, Player[]> = {
    'Goalkeepers': [],
    'Defenders': [],
    'Midfielders': [],
    'Forwards': [],
  };

  for (const player of players) {
    const positionName = positionMap[player.position] || 'Unknown';
    if (!groups[positionName]) {
      groups[positionName] = [];
    }
    groups[positionName].push(player);
  }
  return groups;
};

// --- Player Card Component ---
// A small component to display each player in the optimized squad
const PlayerCard: React.FC<{ player: Player; isCaptain: boolean; isStarting: boolean }> = ({ player, isCaptain, isStarting }) => {
  const positionMap: { [key: number]: string } = { 1: 'GKP', 2: 'DEF', 3: 'MID', 4: 'FWD' };
  
  // Apply different styles if player is not in starting XI
  const cardClasses = isStarting 
    ? "bg-[#3a3a3a] border border-transparent" 
    : "bg-[#2b2b2b] border border-[#4a4a4a] opacity-60"; // Make bench players dimmer
  
  return (
    <div className={`p-3 rounded-lg flex justify-between items-center shadow-md relative ${cardClasses} transition-all`}>
      {/* Show (C) for Captain */}
      {isCaptain && (
        <span className="absolute -top-2 -right-2 bg-pink-600 text-white text-xs font-bold rounded-full h-5 w-5 flex items-center justify-center border-2 border-[#2b2b2b]" title="Captain">C</span>
      )}
       {/* Show (S) for Starter */}
       {isStarting && !isCaptain && (
        <span className="absolute -top-2 -right-2 bg-teal-600 text-white text-xs font-bold rounded-full h-5 w-5 flex items-center justify-center border-2 border-[#2b2b2b]" title="Starting XI">S</span>
      )}
      <div>
        <div className="font-bold text-white">
          {player.first_name && player.second_name ? `${player.first_name} ${player.second_name}` : player.web_name}
          <span className="text-sm text-gray-400"> (ID: {player.id}, {positionMap[player.position]})</span>
        </div>
      </div>
      <div className="text-right">
        <div className="font-bold text-teal-400">£{(player.now_cost / 10).toFixed(1)}m</div>
      </div>
    </div>
  );
};

// --- Optimizer Page Component ---
const Optimizer: React.FC = () => {
  // Store the full response from the API
  const [teamResponse, setTeamResponse] = useState<OptimizedTeamResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // This function is called when the button is clicked
  const handleOptimizeClick = async () => {
    setLoading(true);
    setError(null);
    setTeamResponse(null); // Clear previous squad

    try {
      // Call the API function
      const response = await getOptimizedTeam();
      setTeamResponse(response);
    } catch (err: any) {
      // Try to get the detailed error message from the backend
      setError(err.response?.data?.detail || 'Failed to generate optimized squad. Is the backend running?');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  // --- Data for Rendering ---
  const squad = teamResponse?.squad || [];
  const squadByPosition = groupPlayersByPosition(squad);
  const totalCost = squad.reduce((acc, player) => acc + player.now_cost, 0) / 10;
  
  // Create a Set of starting XI IDs for easy lookup
  const startingXI_IDs = new Set(teamResponse?.xi_ids || []);

  return (
    <div>
      <h1 className="text-3xl font-bold mb-4">Team Optimizer</h1>
      
      {/* --- Control Panel / Button --- */}
      <div className="p-6 bg-[#3a3a3a] rounded-lg shadow-lg mb-6 border border-[#4a4a4a]">
        <p className="text-lg text-gray-200">
          Click the button to generate the mathematically optimal 15-player squad
          based on recent performance and all FPL constraints.
        </p>
        <button
          onClick={handleOptimizeClick}
          disabled={loading} // Disable button while loading
          className="mt-4 px-6 py-3 bg-teal-600 text-white font-bold rounded-lg shadow-lg
                     hover:bg-teal-500 transition-colors duration-200
                     disabled:bg-gray-500 disabled:cursor-not-allowed"
        >
          {loading ? (
            <div className="flex items-center">
              {/* Simple loading spinner */}
              <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white mr-3"></div>
              Optimizing...
            </div>
          ) : (
            'Generate Optimal Squad'
          )}
        </button>
      </div>

      {/* --- Results Section --- */}
      
      {/* Display error message if something went wrong */}
      {error && (
        <div className="mt-4 text-red-400 bg-red-900 bg-opacity-30 p-4 rounded-lg border border-red-700">
          <strong>Error:</strong> {error}
        </div>
      )}

      {/* Display the squad once it's loaded */}
      {squad.length > 0 && teamResponse && (
        <div className="bg-[#3a3a3a] rounded-lg shadow-lg p-6 border border-[#4a4a4a]">
          <div className="flex flex-col sm:flex-row justify-between sm:items-center mb-4">
            <h2 className="text-2xl font-bold text-teal-400">Your Optimal Squad</h2>
            <div className="text-xl font-bold text-gray-200 mt-2 sm:mt-0">
              Total Cost: <span className="text-teal-400">£{totalCost.toFixed(1)}m</span> / £100m
            </div>
          </div>
          
          {/* Grid for displaying players grouped by position */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {/* Loop through the position groups in order */}
            {['Goalkeepers', 'Defenders', 'Midfielders', 'Forwards'].map((position) => (
              <div key={position}>
                <h3 className="text-lg font-semibold text-gray-400 uppercase mb-3">
                  {position} ({squadByPosition[position]?.length || 0})
                </h3>
                <div className="space-y-3">
                  {/* Loop through the players in that position group, sorting starters first */}
                  {squadByPosition[position]
                    ?.sort((a, b) => {
                      // Sort by starting (true) vs bench (false)
                      const aIsStarter = startingXI_IDs.has(a.id);
                      const bIsStarter = startingXI_IDs.has(b.id);
                      if (aIsStarter === bIsStarter) {
                        return b.now_cost - a.now_cost; // Secondary sort by cost
                      }
                      return aIsStarter ? -1 : 1; // Starters come first
                    })
                    .map(player => (
                    <PlayerCard 
                      key={player.id} 
                      player={player}
                      isCaptain={player.id === teamResponse.captain_id}
                      isStarting={startingXI_IDs.has(player.id)}
                    />
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default Optimizer;