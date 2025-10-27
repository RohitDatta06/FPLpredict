from ortools.linear_solver import pywraplp
import pandas as pd
import itertools

def pick_fpl_team(data):
  """
  Input:  list of [player_id, name, position, team_id, cost, gw1, gw2, ...]
    Output: (squad_ids, xi_ids, captain_id)
    """

    # ---------- Load & weight points ----------
  df = pd.DataFrame(
    data,
    columns=["player_id","name","position","team_id","cost","gw1","gw2","gw3","gw4"]
  )
  # geometric decay weights: 1, 0.9, 0.8, 0.7
  n_gw = len([c for c in df.columns if c.startswith("gw")])
  weights = [1 - 0.1*i for i in range(n_gw)]
  df["weighted_points"] = sum(df[f"gw{i+1}"]*weights[i] for i in range(n_gw))

  points = df["weighted_points"].values
  n = len(df)
  pos = df["position"].tolist()
  teams = df["team_id"].tolist()
  cost_tenths = (df["cost"] * 10).round().astype(int).tolist()

    # ---------- 1) Choose 15-man squad ----------
  solver = pywraplp.Solver.CreateSolver("CBC")
  x = [solver.IntVar(0,1,f"x{i}") for i in range(n)]
    # Here's tthe first part where we add the constraints
    # budget 100.0
  solver.Add(sum(cost_tenths[i]*x[i] for i in range(n)) <= 1000)
    # squad size 15
  solver.Add(sum(x)==15)
    # position quotas
  solver.Add(sum(x[i] for i in range(n) if pos[i]=="GK")==2)
  solver.Add(sum(x[i] for i in range(n) if pos[i]=="DEF")==5)
  solver.Add(sum(x[i] for i in range(n) if pos[i]=="MID")==5)
  solver.Add(sum(x[i] for i in range(n) if pos[i]=="FWD")==3)
    # ≤3 per real team
  for t in set(teams):
      solver.Add(sum(x[i] for i in range(n) if teams[i]==t)<=3)

    # tell the solver what we wanna maximize (total weighted points)
  solver.Maximize(sum(points[i]*x[i] for i in range(n)))
  solver.Solve() #solver literally does everything else for ys
  squad_idx = [i for i in range(n) if x[i].solution_value()>0.5]
  squad_ids = df.loc[squad_idx,"player_id"].tolist() #This is the 15 player list

    # ---------- 2) Choose starting XI and captain ----------

  temp_lineups = list(itertools.combinations(squad_ids, 11))  #this is all possible lineups from 15
  valid_lineups = []
    #filter
  position_map = df.set_index('player_id')['position'].to_dict()
  for lineup in temp_lineups:
    num_gk = 0
    num_forward = 0
    num_def = 0
    num_midfielder = 0
    for player_id in lineup:
      position = position_map[player_id]
      if position == "GK":
          num_gk+=1
      elif (position == "FWD"):
        num_forward += 1
      elif (position == "DEF"):
        num_def += 1
      else:
        num_midfielder+=1
    if (num_gk == 1 and num_forward >= 2 and num_def >= 3 and num_midfielder >= 3):
        valid_lineups.append(lineup)

    #now looking at total points for each lineup
  best_lineup_points = -1
  points_map = df.set_index('player_id')['weighted_points'].to_dict()
  xi_ids = []
  for lineup in valid_lineups:
    current_lineup_points = 0
    for player_id in lineup:
      current_lineup_points += points_map[player_id]
    if (current_lineup_points > best_lineup_points):
      best_lineup_points   =  current_lineup_points
      xi_ids = lineup

  captain_points = 0
  captain_id = None
  if xi_ids:
    for player in xi_ids:
      temp_points = points_map[player]
      if (temp_points > captain_points):
        captain_points = temp_points
        captain_id = player

  return squad_ids, xi_ids, captain_id