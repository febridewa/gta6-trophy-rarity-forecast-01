"""GTA VI trophy-rarity forecaster (gta6-trophy-rarity-forecast-01).

Reads each /input/<id>.in case (schema makefun/gta6-trophies-case/v1) and writes
/output/<id>.out: for every trophy, five quantiles (0.05/0.25/0.5/0.75/0.95) of
its Exophase earn rate at the case's target, as
{"trophies": [{"id": n, "q": [q05, q25, q50, q75, q95]}, ...]}.

Method (fitted at run time from the case's own history, stdlib only):
  Rates are modelled in logit space against log time, per trophy:
      logit(r_i(u)) = a_i + b_i * ln(1 + u),   u = hours since 2026-11-19T00:00Z.
  Only the last 24 hours of distinct refresh states are fitted. That window is
  what matters: over the full history the log-time trend is strongly concave
  (early dilution, then progression), so a whole-history line badly
  under-extrapolates, while the recent slope carries the final's 4.5-day
  horizon well. Slopes are shrunk toward the pooled slope across trophies
  (shrinkage weight 4 pseudo-observations): rare trophies' rates are printed
  to 2 decimals, so a 0.03% trophy's per-trophy slope is mostly rounding noise.
  Slopes are capped to [-0.5, 4] so one noisy state can never explode the
  extrapolation. The spread is the house random-walk spread (0.5*sqrt(days))
  combined with the fit's residual sd, times 0.6.
  With fewer than two usable states in the window the per-trophy slope falls
  back to the pooled slope from the last rate (two-point slope, shrunk halfway
  to the pooled slope); with a single state the pooled slope is zero, so the
  forecast is persistence with a widened spread.

  Flat-history fallback (practice cases: every read identical, one state):
  no trend is fittable, but a refresh is likely inside the horizon, and the
  one refresh the house has seen multiplied players-tracked ~6x while total
  earners multiplied ~4.5x, so non-universal rates fall. The forecast
  multiplies every non-100% rate by 0.63 and takes the 100% trophy (fishing,
  the first trophy every launch-night player had) to 80%, with a wide logit
  spread (sd 1.1). On the real practice cases this implies 4,259 total
  earners at N=3,868, against the recorded 4,276.

  Why not model earners and players separately? I tried: a probit factor
  model (shared time factor, dilution separated via ln N) and a log-earners /
  log-players decomposition. Both lose badly in backtest: ln(1+u) and ln N
  are almost perfectly collinear over a 2.5-day history, so the split between
  progression and dilution is unidentified and the extrapolation explodes;
  and log-earners extrapolate as an unbounded power law while the true
  earners saturate (the logit-rate line saturates naturally). The direct
  logit-rate line is the robust choice; it is also the house curve baseline's
  form, improved by the recent window, the shrinkage and the tighter spread.

Validation (synthetic backtest; the practice answers are not published, so
exact practice scoring is impossible locally):
  A cohort simulator of the Exophase process, calibrated to the two verified
  anchors (launch night N=638, 943 earners; first refresh N=3,868, 4,276
  earners, every rate but the 100% one lower), with refreshes every ~4h,
  saturating player growth, and per-trophy lognormal (and, separately,
  Weibull) time-to-earn curves. 16 worlds across varied growth, progression
  speed, dispersion and refresh cadence, final-like cases (checkpoint
  Nov 21 11:30Z -> target Nov 26 00:00Z):
      this entry      mean pinball loss 0.186 (worst world 0.233)
      house curve     mean 0.277 (worst 0.337)
      house baseline  mean 1.312 (worst 1.744)
      practice cases (flat fallback) 0.43 vs 1.31 for persistence
  Slow-refresh worlds (refresh every 12h): this entry 0.243, house curve
  1.519 (it falls back to persistence there). Hold-out backtest (24h -> 48h,
  36h -> 60h): this entry ~0.10-0.24 vs 0.20-0.65 for the house curve.

Deterministic: pure arithmetic, no randomness, no network, no time or
environment dependence beyond the case file itself. Two runs on the same
case write byte-identical output.
"""

import json
import math
import os
import sys
from datetime import datetime
from pathlib import Path

# The grader's -P leaves /bot off sys.path: put it back first, so a module
# shipped beside this file would import. This entry is a single file.
sys.path.insert(0, str(Path(__file__).resolve().parent))

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
Z = [-1.6448536269514722, -0.6744897501960817, 0.0, 0.6744897501960817, 1.6448536269514722]
EPOCH = datetime(2026, 11, 19, 0, 0)

WINDOW_HOURS = 24.0   # fit only the last 24h of distinct refresh states
SHRINK_K = 4.0        # pseudo-observations shrinking each slope to the pooled slope
SPREAD_MULT = 0.6     # multiplier on the combined (random-walk + residual) spread
SLOPE_LO = -0.5       # caps on the fitted logit slope per log-time unit
SLOPE_HI = 4.0

FLAT_MULT = 0.63      # flat-history dilution multiplier for non-100% rates
FLAT_RATE2 = 0.80     # flat-history forecast for the 100% trophy, as a fraction
FLAT_SD = 1.1         # flat-history spread on the logit scale


def parse_ts(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def clamp_pct(x):
    return min(99.99, max(0.01, x))


def logit_pct(x):
    p = clamp_pct(x) / 100.0
    return math.log(p / (1 - p))


def sigmoid_pct(lg):
    return 100.0 / (1.0 + math.exp(-max(-700.0, min(700.0, lg))))


def round4(x):
    """x rounded to 4 decimals, half up, as JavaScript's Math.round rounds it."""
    scaled = x * 10000
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    value = whole / 10000
    return int(value) if float(value).is_integer() else value


def quantiles_from_logit(lg, sd):
    qs = [sigmoid_pct(lg + z * sd) for z in Z]
    qs = [min(100.0, max(0.0, q)) for q in qs]
    for i in range(1, 5):
        qs[i] = max(qs[i], qs[i - 1])
    return [round4(q) for q in qs]


def hours_since_epoch(ts_text):
    dt = parse_ts(ts_text)
    return (dt.replace(tzinfo=None) - EPOCH).total_seconds() / 3600.0


def distinct_states(case):
    """Collapse consecutive identical reads into states.

    Returns [{u (hours since 2026-11-19T00:00Z), N, rates}], keeping the first
    occurrence time of each state. Reads between Exophase refreshes are
    identical, so this is what the history's information really is.
    """
    states = []
    prev_key = None
    for h in case["history"]:
        n = h.get("players_tracked") or 0
        rates = h.get("rates") or []
        key = (n, tuple(rates))
        if key == prev_key:
            continue
        prev_key = key
        states.append({"u": hours_since_epoch(h["at"]), "N": n,
                       "rates": list(rates)})
    return states


def last_known_rate(case, i):
    """The trophy's rate in the last read that lists it, else None."""
    for h in reversed(case["history"]):
        rates = h.get("rates") or []
        if i < len(rates) and rates[i] is not None:
            return rates[i]
    return None


def flat_fallback(case):
    """No trend is fittable (a single distinct state): forecast a dilution
    drop with a wide spread (see the module docstring for the calibration)."""
    out = {}
    for i, t in enumerate(case["trophies"]):
        r = last_known_rate(case, i)
        if r is None:
            r = 0.5
        med = FLAT_RATE2 * 100.0 if r >= 99.99 else r * FLAT_MULT
        out[t["id"]] = quantiles_from_logit(logit_pct(med), FLAT_SD)
    return out


def forecast_case(case):
    if case["levels"] != LEVELS:
        raise ValueError(f"{case['id']} asks for levels {case['levels']}, not {LEVELS}")
    if not case["history"]:
        raise ValueError(f"{case['id']} has no history")
    states = distinct_states(case)
    if len(states) < 2:
        flat = flat_fallback(case)
        return {"trophies": [{"id": t["id"], "q": flat[t["id"]]}
                             for t in case["trophies"]]}

    days = case["horizon_minutes"] / 1440.0
    rw = 0.5 * math.sqrt(days)
    u_ckpt = hours_since_epoch(case["at"])
    u_tgt = hours_since_epoch(case["target"])

    def tx(u):
        return math.log(1.0 + max(0.0, u))

    x_tgt = tx(u_tgt)
    win = [s for s in states if s["u"] >= u_ckpt - WINDOW_HOURS]
    if len(win) < 2:
        win = states

    # Pooled slope over every (trophy, state) point in the window.
    all_pts = []
    per = {}
    for i, t in enumerate(case["trophies"]):
        pts = []
        for s in win:
            r = s["rates"][i] if i < len(s["rates"]) else None
            if r is None:
                continue
            pts.append((tx(s["u"]), logit_pct(r)))
        per[t["id"]] = pts
        all_pts.extend(pts)
    if all_pts:
        n_all = len(all_pts)
        mx = sum(p[0] for p in all_pts) / n_all
        my = sum(p[1] for p in all_pts) / n_all
        sxx = sum((p[0] - mx) ** 2 for p in all_pts)
        b_pool = sum((p[0] - mx) * (p[1] - my) for p in all_pts) / sxx if sxx > 0 else 0.0
    else:
        b_pool = 0.0

    rows = []
    for i, t in enumerate(case["trophies"]):
        pts = per[t["id"]]
        r_last = last_known_rate(case, i)
        if r_last is None:
            r_last = 0.5
        if len(pts) >= 3:
            n = len(pts)
            mxp = sum(p[0] for p in pts) / n
            myp = sum(p[1] for p in pts) / n
            sxxp = sum((p[0] - mxp) ** 2 for p in pts)
            b_i = (sum((p[0] - mxp) * (p[1] - myp) for p in pts) / sxxp
                   if sxxp > 0 else b_pool)
            b = (n * b_i + SHRINK_K * b_pool) / (n + SHRINK_K)
            b = min(max(b, SLOPE_LO), SLOPE_HI)
            a = myp - b * mxp
            resid = [y - (a + b * xx) for xx, y in pts]
            sd_res = math.sqrt(sum(r * r for r in resid) / max(1, n - 2))
            lg = a + b * x_tgt
            sd = math.sqrt(rw * rw + sd_res ** 2) * SPREAD_MULT
        elif len(pts) == 2:
            # Two-point slope, shrunk halfway to the pooled slope, wider spread.
            (x1, y1), (x2, y2) = pts
            b_2pt = (y2 - y1) / (x2 - x1) if x2 != x1 else b_pool
            b = 0.5 * b_2pt + 0.5 * b_pool
            b = min(max(b, SLOPE_LO), SLOPE_HI)
            lg = y2 + b * (x_tgt - x2)
            sd = rw * SPREAD_MULT * 1.5
        else:
            # One usable point: pooled slope from the last rate, wider spread.
            lg = logit_pct(r_last) + b_pool * (x_tgt - tx(u_ckpt))
            sd = rw * SPREAD_MULT * 1.5
        rows.append({"id": t["id"], "q": quantiles_from_logit(lg, sd)})
    return {"trophies": rows}


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        forecast = forecast_case(case)
        (OUTPUT_DIR / f"{path.stem}.out").write_text(
            json.dumps(forecast, separators=(",", ":")) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
