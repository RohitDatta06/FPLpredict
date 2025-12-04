from ortools.linear_solver import pywraplp
import pandas as pd
import itertools
from typing import Iterable, Optional, Sequence, Tuple, List


# ========== UPDATED FUNCTION: supports locks + dedup by name ==========
def pick_fpl_team_with_predictions(
    data: Sequence[Sequence],
    locked_names: Optional[Iterable[str]] = None
) -> Tuple[List[int], List[int], Optional[int]]:
    """
    Optimizer that uses predicted_points directly from ML models.

    Input rows: [player_id, name, position, team_id, cost, predicted_points]
      - player_id: can be any stable ID (index into original df is fine)
      - name: full name string (we use this to deduplicate & to lock)

    locked_names: optional iterable of full-name strings that MUST be in the 15.
                  Matching is case-insensitive and trimmed.

    Output: (squad_ids, xi_ids, captain_id)
      - squad_ids: list of player_id (the same IDs passed in data[*,0])
      - xi_ids:    subset of squad_ids (starting XI)
      - captain_id: one of xi_ids (best predicted_points)
    """

    # build df from raw data
    df = pd.DataFrame(
        data,
        columns=["player_id", "name", "position", "team_id", "cost", "predicted_points"]
    )

    # ---------- handle locks by name ----------
    if locked_names:
        locked_set = {n.strip().lower() for n in locked_names if n.strip()}
    else:
        locked_set = set()

    df["locked"] = df["name"].astype(str).str.strip().str.lower().isin(locked_set)

    # ---------- dedupe: one row per logical player ----------
    # If the CSV has multiple rows per player (repeated IDs / repeated names),
    # we keep the row with the highest predicted_points.
    df = df.sort_values("predicted_points", ascending=False)
    # Use name as the key for "same player"; you can also add "team_id" if needed:
    # subset=["name", "team_id"]
    df = df.drop_duplicates(subset=["name"], keep="first").reset_index(drop=True)

    # ---------- build arrays ----------
    points = df["predicted_points"].to_numpy()
    n = len(df)
    pos = df["position"].tolist()
    teams = df["team_id"].tolist()
    cost_tenths = [int(round(c * 10)) for c in df["cost"].tolist()]
    locked_flags = df["locked"].tolist()
    player_ids = df["player_id"].tolist()  # these are the IDs we will return

    # ---------- phase 1: pick the 15 (the "meta" decision) ----------
    solver = pywraplp.Solver.CreateSolver("CBC")
    x = [solver.IntVar(0, 1, f"x{i}") for i in range(n)]  # x[i]=1 means player i is in the 15

    # budget: £100.0 -> 1000 tenths
    solver.Add(sum(cost_tenths[i] * x[i] for i in range(n)) <= 1000)

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

    # force locked players into the squad
    for i, is_locked in enumerate(locked_flags):
        if is_locked:
            solver.Add(x[i] == 1)

    # maximize predicted_points
    solver.Maximize(sum(points[i] * x[i] for i in range(n)))

    status = solver.Solve()
    if status not in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE):
        # infeasible usually means: too many locks / bad constraints
        return [], [], None

    # we return the original player_ids, not the 0..n-1 internal indices
    squad_internal_idx = [i for i in range(n) if x[i].solution_value() > 0.5]
    squad_ids = [player_ids[i] for i in squad_internal_idx]

    # ---------- phase 2: pick XI + captain (the "weekly" decision) ----------
    # for XI + captain we work in terms of these player_ids
    position_map = {player_ids[i]: pos[i] for i in range(n)}
    points_map = {player_ids[i]: points[i] for i in range(n)}

    best_value = -1.0
    xi_ids: List[int] = []

    for lineup in itertools.combinations(squad_ids, 11):
        gk = d = m = f = 0
        for pid in lineup:
            p = position_map[pid]
            if p == "GK":
                gk += 1
            elif p == "DEF":
                d += 1
            elif p == "MID":
                m += 1
            else:
                f += 1

        # 1 GK, DEF ≥ 3, MID ≥ 3, FWD ≥ 1
        if not (gk == 1 and d >= 3 and m >= 3 and f >= 1):
            continue

        pts = [points_map[pid] for pid in lineup]
        value = sum(pts) + max(pts)  # captain double
        if value > best_value:
            best_value = value
            xi_ids = list(lineup)

    captain_id = max(xi_ids, key=lambda pid: points_map[pid]) if xi_ids else None
    return squad_ids, xi_ids, captain_id


# ========== KEEPING transfer-based function (no change) ==========
def pick_fpl_team_with_transfers(data, current_squad_ids, transfers):
    """
    Same as pick_fpl_team_with_predictions, but force exactly `transfers` changes from the given current 15.
    - current_squad_ids: list of 15 player_ids you already own
    - transfers: non-negative int (0..15). We enforce EXACT number of transfers.
    Returns: (new_squad_ids, xi_ids, captain_id)
    """

    df = pd.DataFrame(
        data,
        columns=["player_id", "name", "position", "team_id", "cost", "predicted_points"]
    )

    points = df["predicted_points"].values
    n = len(df)
    pos = df["position"].tolist()
    teams = df["team_id"].tolist()
    ids = df["player_id"].tolist()
    idx_by_id = {pid: i for i, pid in enumerate(ids)}
    cost_tenths = [int(round(c * 10)) for c in df["cost"].tolist()]

    if len(current_squad_ids) != 15:
        raise ValueError("current_squad_ids must contain exactly 15 player_ids")

    s = [0] * n
    for pid in current_squad_ids:
        if pid not in idx_by_id:
            raise ValueError(f"player_id {pid} from current_squad_ids not found in data")
        s[idx_by_id[pid]] = 1

    solver = pywraplp.Solver.CreateSolver("CBC")
    x = [solver.IntVar(0, 1, f"x{i}") for i in range(n)]
    dvar = [solver.IntVar(0, 1, f"d{i}") for i in range(n)]

    solver.Add(sum(cost_tenths[i] * x[i] for i in range(n)) <= 1000)
    solver.Add(sum(x) == 15)
    solver.Add(sum(x[i] for i in range(n) if pos[i] == "GK") == 2)
    solver.Add(sum(x[i] for i in range(n) if pos[i] == "DEF") == 5)
    solver.Add(sum(x[i] for i in range(n) if pos[i] == "MID") == 5)
    solver.Add(sum(x[i] for i in range(n) if pos[i] == "FWD") == 3)
    for t in set(teams):
        solver.Add(sum(x[i] for i in range(n) if teams[i] == t) <= 3)

    for i in range(n):
        solver.Add(dvar[i] >= x[i] - s[i])
        solver.Add(dvar[i] >= s[i] - x[i])
        solver.Add(dvar[i] <= x[i] + s[i])
        solver.Add(dvar[i] <= 2 - (x[i] + s[i]))

    solver.Add(sum(dvar) == 2 * int(transfers))

    solver.Maximize(sum(points[i] * x[i] for i in range(n)))

    status = solver.Solve()
    if status not in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE):
        return [], [], None

    new_idx = [i for i in range(n) if x[i].solution_value() > 0.5]
    new_squad_ids = [ids[i] for i in new_idx]

    position_map = df.set_index("player_id")["position"].to_dict()
    points_map = df.set_index("player_id")["predicted_points"].to_dict()

    best_value = -1.0
    xi_ids = []
    for lineup in itertools.combinations(new_squad_ids, 11):
        gk = d = m = f = 0
        for pid in lineup:
            p = position_map[pid]
            if p == "GK":
                gk += 1
            elif p == "DEF":
                d += 1
            elif p == "MID":
                m += 1
            else:
                f += 1

        if not (gk == 1 and d >= 3 and m >= 3 and f >= 1):
            continue

        pts = [points_map[pid] for pid in lineup]
        value = sum(pts) + max(pts)
        if value > best_value:
            best_value = value
            xi_ids = list(lineup)

    captain_id = max(xi_ids, key=lambda pid: points_map[pid]) if xi_ids else None
    return new_squad_ids, xi_ids, captain_id
