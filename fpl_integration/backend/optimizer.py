from ortools.linear_solver import pywraplp
import pandas as pd
import itertools

# ========== UPDATED FUNCTION ==========
def pick_fpl_team_with_predictions(data):
    """
    Optimizer that uses predicted_points directly from ML models.
    Input rows: [player_id, name, position, team_id, cost, predicted_points]
    Output: (squad_ids, xi_ids, captain_id)
    """
    
    # ========== CHANGED: Updated column names ==========
    df = pd.DataFrame(
        data,
        columns=["player_id", "name", "position", "team_id", "cost", "predicted_points"]
    )

    # ========== CHANGED: Use predicted_points directly (no weighted average) ==========
    points = df["predicted_points"].values
    n = len(df)
    pos = df["position"].tolist()
    teams = df["team_id"].tolist()
    # store cost in tenths so we can keep everything integer 
    cost_tenths = [int(round(c * 10)) for c in df["cost"].tolist()]

    # ---------- phase 1: pick the 15 (the "meta" decision) ----------
    solver = pywraplp.Solver.CreateSolver("CBC")
    x = [solver.IntVar(0, 1, f"x{i}") for i in range(n)]  # x[i]=1 means player i is in the 15

    # budget: £100.0 -> 1000 tenths
    solver.Add(sum(cost_tenths[i]*x[i] for i in range(n)) <= 1000)

    # total squad size
    solver.Add(sum(x) == 15)

    # exact position quotas (FPL standard 15-man squad)
    solver.Add(sum(x[i] for i in range(n) if pos[i] == "GK") == 2)
    solver.Add(sum(x[i] for i in range(n) if pos[i] == "DEF") == 5)
    solver.Add(sum(x[i] for i in range(n) if pos[i] == "MID") == 5)
    solver.Add(sum(x[i] for i in range(n) if pos[i] == "FWD") == 3)

    # club cap: ≤3 from each real team
    for t in set(teams):
        solver.Add(sum(x[i] for i in range(n) if teams[i] == t) <= 3)

    # ========== CHANGED: Maximize predicted_points (not weighted average) ==========
    solver.Maximize(sum(points[i]*x[i] for i in range(n)))

    status = solver.Solve()
    if status not in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE):
        # if we somehow fed garbage (or silly prices), just return empty
        return [], [], None

    squad_idx = [i for i in range(n) if x[i].solution_value() > 0.5]
    squad_ids = df.loc[squad_idx, "player_id"].tolist()  # this is the final 15

    # ---------- phase 2: pick XI + captain (the "weekly" decision) ----------
    # we brute-force all 11-combos from the 15 (1365 combos easy to handle dont need a fancy algo)
    position_map = df.set_index("player_id")["position"].to_dict()
    # ========== CHANGED: Use predicted_points for XI selection ==========
    points_map = df.set_index("player_id")["predicted_points"].to_dict()

    best_value = -1.0
    xi_ids = []

    for lineup in itertools.combinations(squad_ids, 11):
        # quick headcount per position
        gk = d = m = f = 0
        for pid in lineup:
            p = position_map[pid]
            if p == "GK": gk += 1
            elif p == "DEF": d += 1
            elif p == "MID": m += 1
            else: f += 1

        # 1 GK, DEF≥3, MID≥3, FWD≥1 (updated to allow more flexibility)
        if not (gk == 1 and d >= 3 and m >= 3 and f >= 1):
            continue

        # value we actually care about: XI sum + captain double (i.e., add max once more)
        pts = [points_map[pid] for pid in lineup]
        value = sum(pts) + max(pts)
        if value > best_value:
            best_value = value
            xi_ids = list(lineup)

    # captain = highest points guy in the chosen XI 
    captain_id = max(xi_ids, key=lambda pid: points_map[pid]) if xi_ids else None
    return squad_ids, xi_ids, captain_id


# ========== UPDATED FUNCTION ==========
def pick_fpl_team_with_transfers(data, current_squad_ids, transfers):
    """
    Same as pick_fpl_team_with_predictions, but force exactly `transfers` changes from the given current 15.
    - current_squad_ids: list of 15 player_ids you already own
    - transfers: non-negative int (0..15). We enforce EXACT number of transfers.
    Returns: (new_squad_ids, xi_ids, captain_id)
    """

    # ========== CHANGED: Updated column names ==========
    df = pd.DataFrame(
        data,
        columns=["player_id", "name", "position", "team_id", "cost", "predicted_points"]
    )

    # ========== CHANGED: Use predicted_points directly ==========
    points = df["predicted_points"].values
    n = len(df)
    pos = df["position"].tolist()
    teams = df["team_id"].tolist()
    ids = df["player_id"].tolist()
    idx_by_id = {pid: i for i, pid in enumerate(ids)}
    cost_tenths = [int(round(c*10)) for c in df["cost"].tolist()]

    # sanity: we expect a 15-man current squad (otherwise, the "exact transfers" math breaks)
    if len(current_squad_ids) != 15:
        raise ValueError("current_squad_ids must contain exactly 15 player_ids")

    # mark which indices are currently owned
    s = [0]*n
    for pid in current_squad_ids:
        if pid not in idx_by_id:
            raise ValueError(f"player_id {pid} from current_squad_ids not found in data")
        s[idx_by_id[pid]] = 1  # s[i]=1 means currently own

    # ---------- build the solver with a 'difference' budget ----------
    solver = pywraplp.Solver.CreateSolver("CBC")
    x = [solver.IntVar(0, 1, f"x{i}") for i in range(n)]      # new 15 (decision)
    dvar = [solver.IntVar(0, 1, f"d{i}") for i in range(n)]   # toggles if x[i] != s[i]

    # standard squad constraints (same as pick_fpl_team_with_predictions)
    solver.Add(sum(cost_tenths[i]*x[i] for i in range(n)) <= 1000)
    solver.Add(sum(x) == 15)
    solver.Add(sum(x[i] for i in range(n) if pos[i] == "GK") == 2)
    solver.Add(sum(x[i] for i in range(n) if pos[i] == "DEF") == 5)
    solver.Add(sum(x[i] for i in range(n) if pos[i] == "MID") == 5)
    solver.Add(sum(x[i] for i in range(n) if pos[i] == "FWD") == 3)
    for t in set(teams):
        solver.Add(sum(x[i] for i in range(n) if teams[i] == t) <= 3)

    # link dvar to "did this slot change?"
    # we force: d = 1 iff (s=1,x=0) or (s=0,x=1); d = 0 iff (s=1,x=1) or (s=0,x=0)
    # four little inequalities do the trick for binaries:
    #   d >= x - s
    #   d >= s - x
    #   d <= x + s          (kills d when x=s=0)
    #   d <= 2 - (x + s)    (kills d when x=s=1)
    for i in range(n):
        solver.Add(dvar[i] >= x[i] - s[i])
        solver.Add(dvar[i] >= s[i] - x[i])
        solver.Add(dvar[i] <= x[i] + s[i])
        solver.Add(dvar[i] <= 2 - (x[i] + s[i]))

    # exact transfers: symmetric difference size = 2 * transfers
    solver.Add(sum(dvar) == 2 * int(transfers))

    # still trying to max points (we don't charge hit costs here; just a hard transfer count)
    solver.Maximize(sum(points[i]*x[i] for i in range(n)))

    status = solver.Solve()
    if status not in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE):
        # infeasible usually means "you asked for an impossible exact transfer combo under constraints"
        return [], [], None

    new_idx = [i for i in range(n) if x[i].solution_value() > 0.5]
    new_squad_ids = df.loc[new_idx, "player_id"].tolist()

    # ---------- pick XI + captain for the new squad (same stricter formation) ----------
    position_map = df.set_index("player_id")["position"].to_dict()
    # ========== CHANGED: Use predicted_points ==========
    points_map = df.set_index("player_id")["predicted_points"].to_dict()

    best_value = -1.0
    xi_ids = []
    for lineup in itertools.combinations(new_squad_ids, 11):
        gk = d = m = f = 0
        for pid in lineup:
            p = position_map[pid]
            if p == "GK": gk += 1
            elif p == "DEF": d += 1
            elif p == "MID": m += 1
            else: f += 1

        # stricter: GK=1, DEF≥3, MID≥3, FWD≥1 (updated for flexibility)
        if not (gk == 1 and d >= 3 and m >= 3 and f >= 1):
            continue

        pts = [points_map[pid] for pid in lineup]
        value = sum(pts) + max(pts)
        if value > best_value:
            best_value = value
            xi_ids = list(lineup)

    captain_id = max(xi_ids, key=lambda pid: points_map[pid]) if xi_ids else None
    return new_squad_ids, xi_ids, captain_id


# ========== KEPT: Original functions for backward compatibility ==========
# These are the old versions that expect gw1, gw2, gw3, gw4 format
# Keep these in case you have other code that uses them

def pick_fpl_team(data):
    """
    LEGACY VERSION: Uses gameweek history (gw1, gw2, gw3, gw4) instead of predictions.
    Input: list of [player_id, name, position, team_id, cost, gw1, gw2, gw3, gw4]
    Output: (squad_ids, xi_ids, captain_id)
    """

    # ---------- load table + cook a "recent form" score ----------
    df = pd.DataFrame(
        data,
        columns=["player_id","name","position","team_id","cost","gw1","gw2","gw3","gw4"]
    )
    n_gw = len([c for c in df.columns if c.startswith("gw")])

    # linear decay - 1.0, 0.9, 0.8, 0.7
    weights = [1 - 0.1*i for i in range(n_gw)]
    df["weighted_points"] = sum(df[f"gw{i+1}"] * weights[i] for i in range(n_gw))

    points = df["weighted_points"].values
    n = len(df)
    pos = df["position"].tolist()
    teams = df["team_id"].tolist()
    # store cost in tenths so we can keep everything integer 
    cost_tenths = [int(round(c*10)) for c in df["cost"].tolist()]

    # ---------- phase 1: pick the 15 (the "meta" decision) ----------
    solver = pywraplp.Solver.CreateSolver("CBC")
    x = [solver.IntVar(0, 1, f"x{i}") for i in range(n)]  # x[i]=1 means player i is in the 15

    # budget: £100.0 -> 1000 tenths
    solver.Add(sum(cost_tenths[i]*x[i] for i in range(n)) <= 1000)

    # total squad size
    solver.Add(sum(x) == 15)

    # exact position quotas (FPL standard 15-man squad)
    solver.Add(sum(x[i] for i in range(n) if pos[i] == "GK") == 2)
    solver.Add(sum(x[i] for i in range(n) if pos[i] == "DEF") == 5)
    solver.Add(sum(x[i] for i in range(n) if pos[i] == "MID") == 5)
    solver.Add(sum(x[i] for i in range(n) if pos[i] == "FWD") == 3)

    # club cap: ≤3 from each real team
    for t in set(teams):
        solver.Add(sum(x[i] for i in range(n) if teams[i] == t) <= 3)

    # objective: just pile up weighted points
    solver.Maximize(sum(points[i]*x[i] for i in range(n)))

    status = solver.Solve()
    if status not in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE):
        # if we somehow fed garbage (or silly prices), just return empty
        return [], [], None

    squad_idx = [i for i in range(n) if x[i].solution_value() > 0.5]
    squad_ids = df.loc[squad_idx, "player_id"].tolist()  # this is the final 15

    # ---------- phase 2: pick XI + captain (the "weekly" decision) ----------
    # we brute-force all 11-combos from the 15 (1365 combos easy to handle dont need a fancy algo)
    position_map = df.set_index("player_id")["position"].to_dict()
    points_map = df.set_index("player_id")["weighted_points"].to_dict()

    best_value = -1.0
    xi_ids = []

    for lineup in itertools.combinations(squad_ids, 11):
        # quick headcount per position
        gk = d = m = f = 0
        for pid in lineup:
            p = position_map[pid]
            if p == "GK": gk += 1
            elif p == "DEF": d += 1
            elif p == "MID": m += 1
            else: f += 1

        # 1 GK, DEF≥3, MID≥3, FWD≥2
        if not (gk == 1 and d >= 3 and m >= 3 and f >= 2):
            continue

        # value we actually care about: XI sum + captain double (i.e., add max once more)
        pts = [points_map[pid] for pid in lineup]
        value = sum(pts) + max(pts)
        if value > best_value:
            best_value = value
            xi_ids = list(lineup)

    # captain = highest points guy in the chosen XI 
    captain_id = max(xi_ids, key=lambda pid: points_map[pid]) if xi_ids else None
    return squad_ids, xi_ids, captain_id


def pick_fpl_team_with_transfers_legacy(data, current_squad_ids, transfers):
    """
    LEGACY VERSION: Uses gameweek history instead of predictions.
    Same as pick_fpl_team, but force exactly `transfers` changes from the given current 15.
    - current_squad_ids: list of 15 player_ids you already own
    - transfers: non-negative int (0..15). We enforce EXACT number of transfers.
    Returns: (new_squad_ids, xi_ids, captain_id)
    """

    # ---------- same setup as above ----------
    df = pd.DataFrame(
        data,
        columns=["player_id","name","position","team_id","cost","gw1","gw2","gw3","gw4"]
    )
    n_gw = len([c for c in df.columns if c.startswith("gw")])

    weights = [1 - 0.1*i for i in range(n_gw)]
    df["weighted_points"] = sum(df[f"gw{i+1}"] * weights[i] for i in range(n_gw))

    points = df["weighted_points"].values
    n = len(df)
    pos = df["position"].tolist()
    teams = df["team_id"].tolist()
    ids = df["player_id"].tolist()
    idx_by_id = {pid: i for i, pid in enumerate(ids)}
    cost_tenths = [int(round(c*10)) for c in df["cost"].tolist()]

    # sanity: we expect a 15-man current squad (otherwise, the "exact transfers" math breaks)
    if len(current_squad_ids) != 15:
        raise ValueError("current_squad_ids must contain exactly 15 player_ids")

    # mark which indices are currently owned
    s = [0]*n
    for pid in current_squad_ids:
        if pid not in idx_by_id:
            raise ValueError(f"player_id {pid} from current_squad_ids not found in data")
        s[idx_by_id[pid]] = 1  # s[i]=1 means currently own

    # ---------- build the solver with a 'difference' budget ----------
    solver = pywraplp.Solver.CreateSolver("CBC")
    x = [solver.IntVar(0, 1, f"x{i}") for i in range(n)]      # new 15 (decision)
    dvar = [solver.IntVar(0, 1, f"d{i}") for i in range(n)]   # toggles if x[i] != s[i]

    # standard squad constraints (same as pick_fpl_team)
    solver.Add(sum(cost_tenths[i]*x[i] for i in range(n)) <= 1000)
    solver.Add(sum(x) == 15)
    solver.Add(sum(x[i] for i in range(n) if pos[i] == "GK") == 2)
    solver.Add(sum(x[i] for i in range(n) if pos[i] == "DEF") == 5)
    solver.Add(sum(x[i] for i in range(n) if pos[i] == "MID") == 5)
    solver.Add(sum(x[i] for i in range(n) if pos[i] == "FWD") == 3)
    for t in set(teams):
        solver.Add(sum(x[i] for i in range(n) if teams[i] == t) <= 3)

    # link dvar to "did this slot change?"
    for i in range(n):
        solver.Add(dvar[i] >= x[i] - s[i])
        solver.Add(dvar[i] >= s[i] - x[i])
        solver.Add(dvar[i] <= x[i] + s[i])
        solver.Add(dvar[i] <= 2 - (x[i] + s[i]))

    # exact transfers: symmetric difference size = 2 * transfers
    solver.Add(sum(dvar) == 2 * int(transfers))

    # still trying to max points (we don't charge hit costs here; just a hard transfer count)
    solver.Maximize(sum(points[i]*x[i] for i in range(n)))

    status = solver.Solve()
    if status not in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE):
        # infeasible usually means "you asked for an impossible exact transfer combo under constraints"
        return [], [], None

    new_idx = [i for i in range(n) if x[i].solution_value() > 0.5]
    new_squad_ids = df.loc[new_idx, "player_id"].tolist()

    # ---------- pick XI + captain for the new squad (same stricter formation) ----------
    position_map = df.set_index("player_id")["position"].to_dict()
    points_map = df.set_index("player_id")["weighted_points"].to_dict()

    best_value = -1.0
    xi_ids = []
    for lineup in itertools.combinations(new_squad_ids, 11):
        gk = d = m = f = 0
        for pid in lineup:
            p = position_map[pid]
            if p == "GK": gk += 1
            elif p == "DEF": d += 1
            elif p == "MID": m += 1
            else: f += 1

        # stricter: GK=1, DEF≥3, MID≥3, FWD≥2
        if not (gk == 1 and d >= 3 and m >= 3 and f >= 2):
            continue

        pts = [points_map[pid] for pid in lineup]
        value = sum(pts) + max(pts)
        if value > best_value:
            best_value = value
            xi_ids = list(lineup)

    captain_id = max(xi_ids, key=lambda pid: points_map[pid]) if xi_ids else None
    return new_squad_ids, xi_ids, captain_id