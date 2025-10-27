import React, { useState, useEffect } from 'react';
// Use 'import type' for interfaces to satisfy the build process
import {
  getPlayers,
  getPlayersPaged,
  getFixtures,
  getFixturesPaged,
  getTeamsPaged,
  getGameweekHistoryPaged,
  getTeams,
  type Player,
  type Fixture,
  type Team,
  type GameweekEntry,
  type PagedResult,
} from '../services/api';

const Predictions: React.FC = () => {
  const [players, setPlayers] = useState<Player[]>([]);
  const [fixtures, setFixtures] = useState<Fixture[]>([]);
  const [teams, setTeams] = useState<Team[]>([]);
  const [gameweeks, setGameweeks] = useState<GameweekEntry[]>([]);
  const [playersTotal, setPlayersTotal] = useState(0);
  const [fixturesTotal, setFixturesTotal] = useState(0);
  const [teamsTotal, setTeamsTotal] = useState(0);
  const [gameweeksTotal, setGameweeksTotal] = useState(0);
  // Lookup map for team IDs -> names (for tooltips in Fixtures table)
  const [teamLookup, setTeamLookup] = useState<Record<number, { name: string; short_name: string }>>({});
  const [playerLookup, setPlayerLookup] = useState<Record<number, { web_name: string; team_id: number }>>({});
  const [fixtureLookup, setFixtureLookup] = useState<Record<number, { event: number | null; team_h_id: number; team_a_id: number; kickoff_time: string | null }>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'Players' | 'Fixtures' | 'Gameweek' | 'Teams'>('Players');
  // Pagination state per tab
  const [playersPage, setPlayersPage] = useState(1);
  const [fixturesPage, setFixturesPage] = useState(1);
  const [teamsPage, setTeamsPage] = useState(1);
  const [gameweeksPage, setGameweeksPage] = useState(1);
  const [pageSize, setPageSize] = useState<10 | 30 | 50>(10);
  // Search state per relevant tab
  const [playersSearch, setPlayersSearch] = useState('');
  const [teamsSearch, setTeamsSearch] = useState('');
  const [gameweeksSearch, setGameweeksSearch] = useState('');
  // Initial load flags to reduce flicker on subsequent searches
  const [playersInitialLoaded, setPlayersInitialLoaded] = useState(false);
  const [teamsInitialLoaded, setTeamsInitialLoaded] = useState(false);
  const [gameweeksInitialLoaded, setGameweeksInitialLoaded] = useState(false);
  // Sorting state per tab (default: sort by id asc; first click on a header switches to desc)
  const [playersSortBy, setPlayersSortBy] = useState<keyof Player>('id');
  const [playersSortDir, setPlayersSortDir] = useState<'asc' | 'desc'>('asc');
  const [fixturesSortBy, setFixturesSortBy] = useState<keyof Fixture>('id');
  const [fixturesSortDir, setFixturesSortDir] = useState<'asc' | 'desc'>('asc');
  const [teamsSortBy, setTeamsSortBy] = useState<keyof Team>('id');
  const [teamsSortDir, setTeamsSortDir] = useState<'asc' | 'desc'>('asc');
  const [gameweeksSortBy, setGameweeksSortBy] = useState<keyof GameweekEntry>('id');
  const [gameweeksSortDir, setGameweeksSortDir] = useState<'asc' | 'desc'>('asc');

  // Define columns to display all fields from the Player interface
  const playerColumns: Array<keyof Player> = [
    'id',
    'first_name',
    'second_name',
    'web_name',
    'team_id',
    'position',
    'now_cost',
  ];

  const fixtureColumns: Array<keyof Fixture> = [
    'id',
    'event',
    'kickoff_time',
    'team_h_id',
    'team_a_id',
    'team_h_difficulty',
    'team_a_difficulty',
  ];

  const teamColumns: Array<keyof Team> = ['id', 'name', 'short_name'];

  const gameweekColumns: Array<keyof GameweekEntry> = [
    'id',
    'player_id',
    'fixture_id',
    'opponent_team_id',
    'gameweek',
    'minutes',
    'goals_scored',
    'assists',
    'clean_sheets',
    'goals_conceded',
    'own_goals',
    'penalties_saved',
    'penalties_missed',
    'yellow_cards',
    'red_cards',
    'saves',
    'starts',
    'total_points',
    'bonus',
    'bps',
    'influence',
    'creativity',
    'threat',
    'ict_index',
    'expected_goals',
    'expected_assists',
    'expected_goal_involvements',
    'expected_goals_conceded',
    'expected_points',
    'was_home',
    'kickoff_time',
    'player_value',
    'difficulty',
    'player_team_position',
    'transfers_in',
    'transfers_out',
    'transfers_balance',
    'selected',
  ];

  // Position lookup for Players table tooltips
  const positionLookup: Record<number, { name: string; short: 'GK' | 'DEF' | 'MID' | 'FWD' }> = {
    1: { name: 'Goalkeeper', short: 'GK' },
    2: { name: 'Defender', short: 'DEF' },
    3: { name: 'Midfielder', short: 'MID' },
    4: { name: 'Forward', short: 'FWD' },
  };

  // Load Players initially and whenever pagination/sort/search changes
  useEffect(() => {
    if (activeTab !== 'Players') return;
    const controller = new AbortController();
    (async () => {
      try {
        if (!playersInitialLoaded) setLoading(true);
        setError(null);
        const offset = (playersPage - 1) * pageSize;
        const res: PagedResult<Player> = await getPlayersPaged(
          pageSize,
          offset,
          playersSortBy,
          playersSortDir,
          playersSearch || undefined,
          controller.signal
        );
        setPlayers(res.items);
        setPlayersTotal(res.total);
        setPlayersInitialLoaded(true);
      } catch (err: any) {
        if (err && (err.code === 'ERR_CANCELED' || err.name === 'CanceledError')) {
          // ignore canceled request
        } else {
          setError('Failed to fetch players. Is the backend running?');
          console.error(err);
        }
      } finally {
        setLoading(false);
      }
    })();
    return () => controller.abort();
  }, [activeTab, playersPage, pageSize, playersSortBy, playersSortDir, playersSearch, playersInitialLoaded]);

  // Load other tabs whenever their pagination changes and they are active
  useEffect(() => {
    const controller = new AbortController();
    const loadTab = async () => {
      try {
        if (activeTab === 'Fixtures') {
          setLoading(true);
        } else if (activeTab === 'Teams') {
          if (!teamsInitialLoaded) setLoading(true);
        } else if (activeTab === 'Gameweek') {
          if (!gameweeksInitialLoaded) setLoading(true);
        }
        setError(null);
        if (activeTab === 'Fixtures') {
          const offset = (fixturesPage - 1) * pageSize;
          const res = await getFixturesPaged(pageSize, offset, fixturesSortBy, fixturesSortDir);
          setFixtures(res.items);
          setFixturesTotal(res.total);
          // Ensure team lookup is loaded for tooltips
          if (Object.keys(teamLookup).length === 0) {
            try {
              const allTeams = await getTeams();
              const map: Record<number, { name: string; short_name: string }> = {};
              allTeams.forEach((t) => { map[t.id] = { name: t.name, short_name: t.short_name }; });
              setTeamLookup(map);
            } catch (e) {
              console.warn('Failed to load teams for fixtures tooltips', e);
            }
          }
        } else if (activeTab === 'Teams') {
          const offset = (teamsPage - 1) * pageSize;
          try {
            const res = await getTeamsPaged(pageSize, offset, teamsSortBy, teamsSortDir, teamsSearch || undefined, controller.signal);
            setTeams(res.items);
            setTeamsTotal(res.total);
            setTeamsInitialLoaded(true);
          } catch (err: any) {
            if (!(err && (err.code === 'ERR_CANCELED' || err.name === 'CanceledError'))) {
              throw err;
            }
          }
        } else if (activeTab === 'Gameweek') {
          const offset = (gameweeksPage - 1) * pageSize;
          try {
            const res = await getGameweekHistoryPaged(
              pageSize,
              offset,
              gameweeksSortBy,
              gameweeksSortDir,
              gameweeksSearch || undefined,
              controller.signal
            );
            setGameweeks(res.items);
            setGameweeksTotal(res.total);
            setGameweeksInitialLoaded(true);

            // Ensure lookups are loaded for tooltips/references
            if (Object.keys(teamLookup).length === 0) {
              try {
                const allTeams = await getTeams();
                const tmap: Record<number, { name: string; short_name: string }>= {};
                allTeams.forEach((t) => { tmap[t.id] = { name: t.name, short_name: t.short_name }; });
                setTeamLookup(tmap);
              } catch (e) {
                console.warn('Failed to load teams for gameweek tooltips', e);
              }
            }

            if (Object.keys(playerLookup).length === 0) {
              try {
                const allPlayers = await getPlayers();
                const pmap: Record<number, { web_name: string; team_id: number }> = {};
                allPlayers.forEach((p) => { pmap[p.id] = { web_name: p.web_name, team_id: p.team_id }; });
                setPlayerLookup(pmap);
              } catch (e) {
                console.warn('Failed to load players for gameweek tooltips', e);
              }
            }

            if (Object.keys(fixtureLookup).length === 0) {
              try {
                const allFixtures = await getFixtures();
                const fmap: Record<number, { event: number | null; team_h_id: number; team_a_id: number; kickoff_time: string | null }> = {};
                allFixtures.forEach((f) => { fmap[f.id] = { event: f.event, team_h_id: f.team_h_id, team_a_id: f.team_a_id, kickoff_time: f.kickoff_time ?? null }; });
                setFixtureLookup(fmap);
              } catch (e) {
                console.warn('Failed to load fixtures for gameweek tooltips', e);
              }
            }
          } catch (err: any) {
            if (!(err && (err.code === 'ERR_CANCELED' || err.name === 'CanceledError'))) {
              throw err;
            }
          }
        }
      } catch (err) {
        setError(`Failed to fetch ${activeTab.toLowerCase()} data. Is the backend running?`);
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    if (activeTab !== 'Players') loadTab();
    return () => controller.abort();
  }, [activeTab, fixturesPage, teamsPage, gameweeksPage, pageSize, fixturesSortBy, fixturesSortDir, teamsSortBy, teamsSortDir, gameweeksSortBy, gameweeksSortDir, teamsSearch, gameweeksSearch, teamsInitialLoaded, gameweeksInitialLoaded]);

  // Helper to format kickoff time to "YYYY-MM-DD @ HH:MM (+/-HH:MM)"
  const formatKickoff = (raw: string | null): string => {
    if (!raw) return '';
    const m = raw.match(/^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}):\d{2}(?:\.\d+)?(Z|[+-]\d{2}:\d{2})$/);
    if (m) {
      const [, date, time, offset] = m;
      return `${date} @ ${time} (${offset})`;
    }
    // Fallback: try to display in a consistent short format with offset if supported
    try {
      const d = new Date(raw);
      const datePart = `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, '0')}-${String(d.getUTCDate()).padStart(2, '0')}`;
      const timePart = `${String(d.getUTCHours()).padStart(2, '0')}:${String(d.getUTCMinutes()).padStart(2, '0')}`;
      // Attempt to capture offset from original string
      const off = (raw.match(/(Z|[+-]\d{2}:\d{2})$/) || [,'Z'])[1];
      return `${datePart} @ ${timePart} (${off})`;
    } catch {
      return raw;
    }
  };

  // Header click handlers
  const nextDir = (currentBy: string, currentDir: 'asc' | 'desc', clicked: string) => (
    currentBy === clicked ? (currentDir === 'desc' ? 'asc' : 'desc') : 'desc'
  );

  if (loading && activeTab === 'Players') {
    return (
      <div>
        <h1 className="text-3xl font-bold mb-6">Predictions</h1>
        <Tabs activeTab={activeTab} onChange={setActiveTab} />
        <p className="mt-4 text-gray-400">Loading player data from the API...</p>
      </div>
    );
  }

  if (error && activeTab === 'Players') {
    return (
      <div>
        <h1 className="text-3xl font-bold mb-6">Predictions</h1>
        <Tabs activeTab={activeTab} onChange={setActiveTab} />
        <p className="mt-4 text-red-500 bg-red-900 bg-opacity-30 p-4 rounded-lg">{error}</p>
      </div>
    );
  }

  return (
    <div>
      <h1 className="text-3xl font-bold mb-6">Predictions</h1>
      <Tabs activeTab={activeTab} onChange={setActiveTab} />

      {activeTab === 'Players' && (
        <section className="mt-6">
          <h2 className="text-xl font-semibold mb-3">Players</h2>
          <div className="mb-3 flex items-center gap-2">
            <input
              type="text"
              placeholder="Search players by name, id, or team id..."
              className="w-full max-w-md bg-[#1a1a1a] text-gray-100 placeholder-gray-400 border border-[#3a3a3a] rounded px-3 py-2 focus:outline-none focus:ring-1 focus:ring-teal-600"
              value={playersSearch}
              onChange={(e) => { setPlayersSearch(e.target.value); setPlayersPage(1); }}
            />
          </div>
          <Pagination
            page={playersPage}
            pageSize={pageSize}
            total={playersTotal}
            onPageChange={setPlayersPage}
            onPageSizeChange={(s) => { setPageSize(s); setPlayersPage(1); }}
          />
          {/* Table to display ALL fields defined in Player interface */}
          <div className="overflow-x-auto bg-[#2b2b2b] rounded-lg border border-[#3a3a3a]">
            <table className="min-w-full">
              <thead className="bg-[#2b2b2b]">
                <tr>
                  {playerColumns.map((col) => {
                    const isActive = playersSortBy === col;
                    const arrow = isActive ? (playersSortDir === 'desc' ? '▼' : '▲') : '';
                    return (
                      <th
                        key={col as string}
                        className="p-4 text-left text-sm font-semibold text-gray-300 uppercase tracking-wider cursor-pointer select-none border-b border-r border-[#3a3a3a]"
                        onClick={() => {
                          const dir = nextDir(playersSortBy as string, playersSortDir, col as string);
                          setPlayersSortBy(col);
                          setPlayersSortDir(dir);
                          setPlayersPage(1);
                        }}
                      >
                        <span className="inline-flex items-center gap-1">
                          {col}
                          <span className="text-xs">{arrow}</span>
                        </span>
                      </th>
                    );
                  })}
                </tr>
              </thead>
              <tbody className="bg-[#2b2b2b]">
                {players.length === 0 ? (
                  <tr>
                    <td colSpan={playerColumns.length} className="p-4 text-center text-gray-400">
                      No players found. Is the backend returning data?
                    </td>
                  </tr>
                ) : (
                  players.map((player) => (
                    <tr key={player.id} className="border-b border-[#3a3a3a] hover:bg-[#353535] transition-colors">
                      {playerColumns.map((col) => {
                        const val = player[col as keyof Player] as any;
                        if (col === 'position') {
                          const pos = positionLookup[val as number];
                          const title = pos ? `${pos.name} (${pos.short})` : 'Unknown position';
                          return (
                            <td key={col as string} className="p-4 whitespace-nowrap border-r border-[#3a3a3a]">
                              <span title={title} className="underline decoration-dotted cursor-help">
                                {String(val ?? '')}
                              </span>
                            </td>
                          );
                        }
                        return (
                          <td key={col as string} className="p-4 whitespace-nowrap border-r border-[#3a3a3a]">
                            {String(val ?? '')}
                          </td>
                        );
                      })}
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
          <Pagination
            page={playersPage}
            pageSize={pageSize}
            total={playersTotal}
            onPageChange={setPlayersPage}
            onPageSizeChange={(s) => { setPageSize(s); setPlayersPage(1); }}
          />
        </section>
      )}

      {activeTab === 'Fixtures' && (
        <section className="mt-6">
          <h2 className="text-xl font-semibold mb-3">Fixtures</h2>
          <Pagination
            page={fixturesPage}
            pageSize={pageSize}
            total={fixturesTotal}
            onPageChange={setFixturesPage}
            onPageSizeChange={(s) => { setPageSize(s); setFixturesPage(1); }}
          />
          <div className="overflow-x-auto bg-[#2b2b2b] rounded-lg border border-[#3a3a3a]">
            <table className="min-w-full">
              <thead className="bg-[#2b2b2b]">
                <tr>
                  {fixtureColumns.map((col) => {
                    const isActive = fixturesSortBy === col;
                    const arrow = isActive ? (fixturesSortDir === 'desc' ? '▼' : '▲') : '';
                    return (
                      <th
                        key={col as string}
                        className="p-4 text-left text-sm font-semibold text-gray-300 uppercase tracking-wider cursor-pointer select-none border-b border-r border-[#3a3a3a]"
                        onClick={() => {
                          const dir = nextDir(fixturesSortBy as string, fixturesSortDir, col as string);
                          setFixturesSortBy(col);
                          setFixturesSortDir(dir);
                          setFixturesPage(1);
                        }}
                      >
                        <span className="inline-flex items-center gap-1">
                          {col}
                          <span className="text-xs">{arrow}</span>
                        </span>
                      </th>
                    );
                  })}
                </tr>
              </thead>
              <tbody className="bg-[#2b2b2b]">
                {loading ? (
                  <tr>
                    <td colSpan={fixtureColumns.length} className="p-4 text-center text-gray-400">
                      Loading fixtures...
                    </td>
                  </tr>
                ) : fixtures.length === 0 ? (
                  <tr>
                    <td colSpan={fixtureColumns.length} className="p-4 text-center text-gray-400">
                      No fixtures found.
                    </td>
                  </tr>
                ) : (
                  fixtures.map((fx) => (
                    <tr key={fx.id} className="border-b border-[#3a3a3a] hover:bg-[#353535] transition-colors">
                      {fixtureColumns.map((col) => {
                        const val = (fx as any)[col];
                        if (col === 'kickoff_time') {
                          return (
                            <td key={col as string} className="p-4 whitespace-nowrap border-r border-[#3a3a3a]">
                              {formatKickoff(val)}
                            </td>
                          );
                        }
                        if (col === 'team_h_id' || col === 'team_a_id') {
                          const t = teamLookup[val as number];
                          const title = t ? `${t.name} (${t.short_name})` : 'Unknown team';
                          return (
                            <td key={col as string} className="p-4 whitespace-nowrap border-r border-[#3a3a3a]">
                              <span title={title} className="underline decoration-dotted cursor-help">
                                {String(val ?? '')}
                              </span>
                            </td>
                          );
                        }
                        return (
                          <td key={col as string} className="p-4 whitespace-nowrap border-r border-[#3a3a3a]">
                            {String(val ?? '')}
                          </td>
                        );
                      })}
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
          <Pagination
            page={fixturesPage}
            pageSize={pageSize}
            total={fixturesTotal}
            onPageChange={setFixturesPage}
            onPageSizeChange={(s) => { setPageSize(s); setFixturesPage(1); }}
          />
        </section>
      )}

      {activeTab === 'Gameweek' && (
        <section className="mt-6">
          <h2 className="text-xl font-semibold mb-3">Gameweek</h2>
          <div className="mb-3 flex items-center gap-2">
            <input
              type="text"
              placeholder="Search by player name, player_id, or gameweek"
              className="w-full max-w-md bg-[#1a1a1a] text-gray-100 placeholder-gray-400 border border-[#3a3a3a] rounded px-3 py-2 focus:outline-none focus:ring-1 focus:ring-teal-600"
              value={gameweeksSearch}
              onChange={(e) => {
                setGameweeksSearch(e.target.value);
                setGameweeksPage(1);
              }}
            />
          </div>
          <Pagination
            page={gameweeksPage}
            pageSize={pageSize}
            total={gameweeksTotal}
            onPageChange={setGameweeksPage}
            onPageSizeChange={(s) => { setPageSize(s); setGameweeksPage(1); }}
          />
          <div className="overflow-x-auto bg-[#2b2b2b] rounded-lg border border-[#3a3a3a]">
            <table className="min-w-full">
              <thead className="bg-[#2b2b2b]">
                <tr>
                  {gameweekColumns.map((col) => {
                    const isActive = gameweeksSortBy === col;
                    const arrow = isActive ? (gameweeksSortDir === 'desc' ? '▼' : '▲') : '';
                    return (
                      <th
                        key={col as string}
                        className="p-4 text-left text-sm font-semibold text-gray-300 uppercase tracking-wider cursor-pointer select-none border-b border-r border-[#3a3a3a]"
                        onClick={() => {
                          const dir = nextDir(gameweeksSortBy as string, gameweeksSortDir, col as string);
                          setGameweeksSortBy(col);
                          setGameweeksSortDir(dir);
                          setGameweeksPage(1);
                        }}
                      >
                        <span className="inline-flex items-center gap-1">
                          {col}
                          <span className="text-xs">{arrow}</span>
                        </span>
                      </th>
                    );
                  })}
                </tr>
              </thead>
              <tbody className="bg-[#2b2b2b]">
                {loading ? (
                  <tr>
                    <td colSpan={gameweekColumns.length} className="p-4 text-center text-gray-400">
                      Loading gameweek history...
                    </td>
                  </tr>
                ) : gameweeks.length === 0 ? (
                  <tr>
                    <td colSpan={gameweekColumns.length} className="p-4 text-center text-gray-400">
                      No gameweek history found.
                    </td>
                  </tr>
                ) : (
                  gameweeks.map((gw) => (
                    <tr key={gw.id} className="border-b border-[#3a3a3a] hover:bg-[#353535] transition-colors">
                      {gameweekColumns.map((col) => {
                        const val = (gw as any)[col];
                        if (col === 'kickoff_time') {
                          return (
                            <td key={col as string} className="p-4 whitespace-nowrap border-r border-[#3a3a3a]">{formatKickoff(val)}</td>
                          );
                        }
                        if (col === 'opponent_team_id') {
                          const t = teamLookup[(val as number) ?? -1];
                          const title = t ? `${t.name} (${t.short_name})` : 'Unknown team';
                          return (
                            <td key={col as string} className="p-4 whitespace-nowrap border-r border-[#3a3a3a]">
                              <span title={title} className="underline decoration-dotted cursor-help">{String(val ?? '')}</span>
                            </td>
                          );
                        }
                        if (col === 'player_id') {
                          const p = playerLookup[(val as number) ?? -1];
                          const team = p ? teamLookup[p.team_id] : undefined;
                          const title = p ? `${p.web_name}${team ? ` (${team.short_name})` : ''}` : 'Unknown player';
                          return (
                            <td key={col as string} className="p-4 whitespace-nowrap border-r border-[#3a3a3a]">
                              <span title={title} className="underline decoration-dotted cursor-help">{String(val ?? '')}</span>
                            </td>
                          );
                        }
                        if (col === 'fixture_id') {
                          const f = fixtureLookup[(val as number) ?? -1];
                          const home = f ? teamLookup[f.team_h_id] : undefined;
                          const away = f ? teamLookup[f.team_a_id] : undefined;
                          const title = f
                            ? `GW ${f.event ?? ''}: ${home ? home.short_name : '?'} vs ${away ? away.short_name : '?'}${f.kickoff_time ? ` — ${formatKickoff(f.kickoff_time)}` : ''}`
                            : 'Unknown fixture';
                          return (
                            <td key={col as string} className="p-4 whitespace-nowrap border-r border-[#3a3a3a]">
                              <span title={title} className="underline decoration-dotted cursor-help">{String(val ?? '')}</span>
                            </td>
                          );
                        }
                        return (
                          <td key={col as string} className="p-4 whitespace-nowrap border-r border-[#3a3a3a]">{String(val ?? '')}</td>
                        );
                      })}
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
          <Pagination
            page={gameweeksPage}
            pageSize={pageSize}
            total={gameweeksTotal}
            onPageChange={setGameweeksPage}
            onPageSizeChange={(s) => { setPageSize(s); setGameweeksPage(1); }}
          />
        </section>
      )}

      {activeTab === 'Teams' && (
        <section className="mt-6">
          <h2 className="text-xl font-semibold mb-3">Teams</h2>
          <div className="mb-3 flex items-center gap-2">
            <input
              type="text"
              placeholder="Search teams by name, short name, or id..."
              className="w-full max-w-md bg-[#1a1a1a] text-gray-100 placeholder-gray-400 border border-[#3a3a3a] rounded px-3 py-2 focus:outline-none focus:ring-1 focus:ring-teal-600"
              value={teamsSearch}
              onChange={(e) => { setTeamsSearch(e.target.value); setTeamsPage(1); }}
            />
          </div>
          <Pagination
            page={teamsPage}
            pageSize={pageSize}
            total={teamsTotal}
            onPageChange={setTeamsPage}
            onPageSizeChange={(s) => { setPageSize(s); setTeamsPage(1); }}
          />
          <div className="overflow-x-auto bg-[#2b2b2b] rounded-lg border border-[#3a3a3a]">
            <table className="min-w-full">
              <thead className="bg-[#2b2b2b]">
                <tr>
                  {teamColumns.map((col) => {
                    const isActive = teamsSortBy === col;
                    const arrow = isActive ? (teamsSortDir === 'desc' ? '▼' : '▲') : '';
                    return (
                      <th
                        key={col as string}
                        className="p-4 text-left text-sm font-semibold text-gray-300 uppercase tracking-wider cursor-pointer select-none border-b border-r border-[#3a3a3a]"
                        onClick={() => {
                          const dir = nextDir(teamsSortBy as string, teamsSortDir, col as string);
                          setTeamsSortBy(col);
                          setTeamsSortDir(dir);
                          setTeamsPage(1);
                        }}
                      >
                        <span className="inline-flex items-center gap-1">
                          {col}
                          <span className="text-xs">{arrow}</span>
                        </span>
                      </th>
                    );
                  })}
                </tr>
              </thead>
              <tbody className="bg-[#2b2b2b]">
                {loading ? (
                  <tr>
                    <td colSpan={teamColumns.length} className="p-4 text-center text-gray-400">
                      Loading teams...
                    </td>
                  </tr>
                ) : teams.length === 0 ? (
                  <tr>
                    <td colSpan={teamColumns.length} className="p-4 text-center text-gray-400">
                      No teams found.
                    </td>
                  </tr>
                ) : (
                  teams.map((tm) => (
                    <tr key={tm.id} className="border-b border-[#3a3a3a] hover:bg-[#353535] transition-colors">
                      {teamColumns.map((col) => (
                        <td key={col as string} className="p-4 whitespace-nowrap border-r border-[#3a3a3a]">
                          {String((tm as any)[col] ?? '')}
                        </td>
                      ))}
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
          <Pagination
            page={teamsPage}
            pageSize={pageSize}
            total={teamsTotal}
            onPageChange={setTeamsPage}
            onPageSizeChange={(s) => { setPageSize(s); setTeamsPage(1); }}
          />
        </section>
      )}
    </div>
  );
};

type TabsProps = {
  activeTab: 'Players' | 'Fixtures' | 'Gameweek' | 'Teams';
  onChange: (tab: 'Players' | 'Fixtures' | 'Gameweek' | 'Teams') => void;
};

const Tabs: React.FC<TabsProps> = ({ activeTab, onChange }) => {
  const tabs: TabsProps['activeTab'][] = ['Players', 'Fixtures', 'Gameweek', 'Teams'];

  return (
    <div className="flex gap-2 border-b border-[#3a3a3a]">
      {tabs.map((tab) => {
        const isActive = activeTab === tab;
        return (
          <button
            key={tab}
            onClick={() => onChange(tab)}
            className={
              `px-4 py-2 rounded-t-md transition-colors ` +
              (isActive
                ? 'bg-teal-600 text-white border border-b-0 border-teal-700'
                : 'bg-[#2b2b2b] text-gray-200 border border-[#3a3a3a] hover:text-teal-300 hover:border-teal-600 hover:bg-[#353535]')
            }
          >
            {tab}
          </button>
        );
      })}
    </div>
  );
};

export default Predictions;

// ---- Pagination UI ----
type PaginationProps = {
  page: number;
  pageSize: 10 | 30 | 50;
  total: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (size: 10 | 30 | 50) => void;
};

const Pagination: React.FC<PaginationProps> = ({ page, pageSize, total, onPageChange, onPageSizeChange }) => {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const start = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const end = Math.min(total, page * pageSize);

  // Build a compact page number list: first, prev window, current, next window, last
  const pages: (number | '…')[] = [];
  const addPage = (p: number) => { if (!pages.includes(p)) pages.push(p); };
  if (totalPages <= 7) {
    for (let p = 1; p <= totalPages; p++) addPage(p);
  } else {
    addPage(1);
    if (page > 4) pages.push('…');
    for (let p = Math.max(2, page - 2); p <= Math.min(totalPages - 1, page + 2); p++) addPage(p);
    if (page < totalPages - 3) pages.push('…');
    addPage(totalPages);
  }

  return (
    <div className="flex items-center justify-between gap-4 my-3">
      <div className="text-sm text-gray-300">
        Showing {start}-{end} of {total}
      </div>
      <div className="flex items-center gap-2">
        <label className="text-sm text-gray-300">Rows per page:</label>
        <select
          className="bg-[#2b2b2b] text-gray-200 border border-[#3a3a3a] rounded px-2 py-1"
          value={pageSize}
          onChange={(e) => onPageSizeChange(Number(e.target.value) as 10 | 30 | 50)}
        >
          <option value={10}>10</option>
          <option value={30}>30</option>
          <option value={50}>50</option>
        </select>
      </div>
      <div className="flex items-center gap-1">
        <button
          className="px-2 py-1 bg-[#2b2b2b] text-gray-200 border border-[#3a3a3a] rounded disabled:opacity-50 hover:bg-[#353535]"
          onClick={() => onPageChange(Math.max(1, page - 1))}
          disabled={page === 1}
        >
          Prev
        </button>
        {pages.map((p, idx) => (
          p === '…' ? (
            <span key={`ellipsis-${idx}`} className="px-2 text-gray-400">…</span>
          ) : (
            <button
              key={p}
              className={`px-2 py-1 rounded border ${p === page ? 'bg-[#2b2b2b] text-teal-300 border-teal-600' : 'bg-[#2b2b2b] text-gray-200 border-[#3a3a3a] hover:bg-[#353535]'}`}
              onClick={() => onPageChange(p)}
            >
              {p}
            </button>
          )
        ))}
        <button
          className="px-2 py-1 bg-[#2b2b2b] text-gray-200 border border-[#3a3a3a] rounded disabled:opacity-50 hover:bg-[#353535]"
          onClick={() => onPageChange(Math.min(totalPages, page + 1))}
          disabled={page >= totalPages}
        >
          Next
        </button>
      </div>
    </div>
  );
};

