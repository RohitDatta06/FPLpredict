import React, { useState } from 'react';
import {
  getOptimizedTeam,
  getOptimizedTeamExplanation,
  type Player,
  type OptimizedTeamResponse,
} from '../services/api';

// Helper function to group players by position
const groupPlayersByPosition = (players: Player[]) => {
  const positionMap: { [key: number]: string } = {
    1: 'Goalkeepers',
    2: 'Defenders',
    3: 'Midfielders',
    4: 'Forwards',
  };

  const groups: Record<string, Player[]> = {
    Goalkeepers: [],
    Defenders: [],
    Midfielders: [],
    Forwards: [],
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
const PlayerCard: React.FC<{ player: Player; isCaptain: boolean; isStarting: boolean }> = ({
  player,
  isCaptain,
  isStarting,
}) => {
  const positionMap: { [key: number]: string } = { 1: 'GKP', 2: 'DEF', 3: 'MID', 4: 'FWD' };

  const cardClasses = isStarting
    ? 'bg-[#3a3a3a] border border-transparent'
    : 'bg-[#2b2b2b] border border-[#4a4a4a] opacity-60';

  return (
    <div
      className={`p-3 rounded-lg flex justify-between items-center shadow-md relative ${cardClasses} transition-all`}
    >
      {isCaptain && (
        <span
          className="absolute -top-2 -right-2 bg-pink-600 text-white text-xs font-bold rounded-full h-5 w-5 flex items-center justify-center border-2 border-[#2b2b2b]"
          title="Captain"
        >
          C
        </span>
      )}
      {isStarting && !isCaptain && (
        <span
          className="absolute -top-2 -right-2 bg-teal-600 text-white text-xs font-bold rounded-full h-5 w-5 flex items-center justify-center border-2 border-[#2b2b2b]"
          title="Starting XI"
        >
          S
        </span>
      )}
      <div>
        <div className="font-bold text-white">
          {player.first_name && player.second_name
            ? `${player.first_name} ${player.second_name}`
            : player.web_name}
          <span className="text-sm text-gray-400">
            {' '}
            (ID: {player.id}, {positionMap[player.position]})
          </span>
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
  const [teamResponse, setTeamResponse] = useState<OptimizedTeamResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // NEW: locked players input (no gameweek)
  const [lockedInput, setLockedInput] = useState<string>(''); // e.g. "Erling Haaland, Bukayo Saka"

  // NEW: AI explanation state (must be inside component!)
  const [explanation, setExplanation] = useState<string | null>(null);
  const [explainLoading, setExplainLoading] = useState(false);

  const handleOptimizeClick = async () => {
    setLoading(true);
    setError(null);
    setTeamResponse(null);
    setExplanation(null);

    try {
      const lockedNames = lockedInput
        .split(/[\n,]/)
        .map(s => s.trim())
        .filter(s => s.length > 0);

      const response = await getOptimizedTeam(lockedNames);
      setTeamResponse(response);
    } catch (err: any) {
      setError(
        err?.response?.data?.detail ||
          'Failed to generate optimized squad. Is the backend running?',
      );
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleExplainClick = async () => {
    if (!teamResponse) return;

    setExplainLoading(true);
    setError(null);

    try {
      const lockedNames = lockedInput
        .split(/[\n,]/)
        .map(s => s.trim())
        .filter(s => s.length > 0);

      const { explanation } = await getOptimizedTeamExplanation(lockedNames);
      setExplanation(explanation);
    } catch (err: any) {
      setError(
        err?.response?.data?.detail ||
          'Failed to generate explanation. Is the backend running and GEMINI_API_KEY set?',
      );
      console.error(err);
    } finally {
      setExplainLoading(false);
    }
  };

  const squad = teamResponse?.squad || [];
  const squadByPosition = groupPlayersByPosition(squad);
  const totalCost = squad.reduce((acc, player) => acc + player.now_cost, 0) / 10;
  const startingXI_IDs = new Set(teamResponse?.xi_ids || []);

  return (
    <div>
      <h1 className="text-3xl font-bold mb-4">Team Optimizer</h1>

      {/* --- Control Panel --- */}
      <div className="p-6 bg-[#3a3a3a] rounded-lg shadow-lg mb-6 border border-[#4a4a4a] space-y-4">
        <p className="text-lg text-gray-200">
          Click the button to generate the mathematically optimal 15-player squad based on model
          predictions. Optionally lock in specific players by full name.
        </p>

        <div className="grid grid-cols-1 gap-4">
          {/* Locked players input */}
          <div>
            <label className="block text-sm font-semibold text-gray-300 mb-1">
              Locked players (optional)
            </label>
            <textarea
              className="w-full px-3 py-2 rounded-md bg-[#2b2b2b] border border-[#4a4a4a] text-gray-100 focus:outline-none focus:ring-2 focus:ring-teal-500 min-h-[60px]"
              placeholder={'Comma or newline separated full names, e.g.\nErling Haaland, Bukayo Saka'}
              value={lockedInput}
              onChange={e => setLockedInput(e.target.value)}
            />
            <p className="text-xs text-gray-400 mt-1">
              Names must match the CSV <code>name</code> field (case-insensitive), e.g. &quot;Femi
              Seriki&quot;.
            </p>
          </div>
        </div>

        <button
          onClick={handleOptimizeClick}
          disabled={loading}
          className="mt-2 px-6 py-3 bg-teal-600 text-white font-bold rounded-lg shadow-lg
                     hover:bg-teal-500 transition-colors duration-200
                     disabled:bg-gray-500 disabled:cursor-not-allowed"
        >
          {loading ? (
            <div className="flex items-center">
              <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white mr-3" />
              Optimizing...
            </div>
          ) : (
            'Generate Optimal Squad'
          )}
        </button>

        {teamResponse && (
          <button
            onClick={handleExplainClick}
            disabled={explainLoading}
            className="mt-2 ml-0 sm:ml-4 px-6 py-2 bg-purple-600 text-white font-semibold rounded-lg shadow
                      hover:bg-purple-500 transition-colors duration-200
                      disabled:bg-gray-500 disabled:cursor-not-allowed"
          >
            {explainLoading ? 'Asking AI...' : 'Explain this squad with AI'}
          </button>
        )}
      </div>

      {/* --- Error --- */}
      {error && (
        <div className="mt-4 text-red-400 bg-red-900 bg-opacity-30 p-4 rounded-lg border border-red-700">
          <strong>Error:</strong> {error}
        </div>
      )}

      {/* --- Results --- */}
      {squad.length > 0 && teamResponse && (
        <div className="bg-[#3a3a3a] rounded-lg shadow-lg p-6 border border-[#4a4a4a]">
          <div className="flex flex-col sm:flex-row justify-between sm:items-center mb-4">
            <h2 className="text-2xl font-bold text-teal-400">Your Optimal Squad</h2>
            <div className="text-xl font-bold text-gray-200 mt-2 sm:mt-0">
              Total Cost: <span className="text-teal-400">£{totalCost.toFixed(1)}m</span> / £100m
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {['Goalkeepers', 'Defenders', 'Midfielders', 'Forwards'].map(position => (
              <div key={position}>
                <h3 className="text-lg font-semibold text-gray-400 uppercase mb-3">
                  {position} ({squadByPosition[position]?.length || 0})
                </h3>
                <div className="space-y-3">
                  {squadByPosition[position]
                    ?.sort((a, b) => {
                      const aIsStarter = startingXI_IDs.has(a.id);
                      const bIsStarter = startingXI_IDs.has(b.id);
                      if (aIsStarter === bIsStarter) {
                        return b.now_cost - a.now_cost;
                      }
                      return aIsStarter ? -1 : 1;
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

      {explanation && (
        <div className="mt-6 bg-[#2b2b2b] rounded-lg border border-[#4a4a4a] p-4">
          <h3 className="text-xl font-semibold text-purple-300 mb-3">AI Explanation</h3>
          <div className="prose prose-invert max-w-none text-gray-100 whitespace-pre-wrap">
            {explanation}
          </div>
        </div>
      )}
    </div>
  );
};

export default Optimizer;

