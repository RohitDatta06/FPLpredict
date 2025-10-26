import React, { useState, useEffect } from 'react';
// FIX: Use 'import type' for interfaces to satisfy the build process
import { getPlayers, type Player } from '../services/api'; 

const Predictions: React.FC = () => {
  const [players, setPlayers] = useState<Player[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadPlayerData = async () => {
      try {
        setLoading(true);
        const data = await getPlayers();
        setPlayers(data);
        setError(null);
      } catch (err) {
        setError("Failed to fetch players. Is the backend running?");
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    loadPlayerData();
  }, []); 

  if (loading) {
    return (
      <div>
        <h1 className="text-3xl font-bold mb-6">Player Data</h1>
        <p className="mt-4 text-gray-400">Loading player data from the API...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div>
        <h1 className="text-3xl font-bold mb-6">Player Data</h1>
        <p className="mt-4 text-red-500 bg-red-900 bg-opacity-30 p-4 rounded-lg">{error}</p>
      </div>
    );
  }

  return (
    <div>
      <h1 className="text-3xl font-bold mb-6">Player Data</h1>
      
      {/* Simple Table to display data */}
      <div className="overflow-x-auto bg-gray-800 rounded-lg shadow-md">
        <table className="min-w-full">
          <thead className="bg-gray-700">
            <tr>
              <th className="p-4 text-left text-sm font-semibold text-gray-300 uppercase tracking-wider">Name</th>
              <th className="p-4 text-left text-sm font-semibold text-gray-300 uppercase tracking-wider">Position</th>
              <th className="p-4 text-right text-sm font-semibold text-gray-300 uppercase tracking-wider">Cost</th>
            </tr>
          </thead>
          <tbody>
            {players.length === 0 ? (
               <tr>
                 <td colSpan={3} className="p-4 text-center text-gray-400">No players found. Is the backend returning data?</td>
               </tr>
             ) : (
              players.map((player) => (
                <tr key={player.id} className="border-b border-gray-700 hover:bg-gray-700 transition-colors">
                  <td className="p-4 whitespace-nowrap">{player.web_name}</td>
                  <td className="p-4 whitespace-nowrap">{
                    // Basic position mapping - you can make this more robust
                    player.position === 1 ? 'GKP' :
                    player.position === 2 ? 'DEF' :
                    player.position === 3 ? 'MID' :
                    player.position === 4 ? 'FWD' : 'N/A'
                  }</td>
                  <td className="p-4 whitespace-nowrap text-right font-medium">£{(player.now_cost / 10).toFixed(1)}m</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default Predictions;

