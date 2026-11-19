# gta6-trophy-rarity-forecast-01

[![make.fun · gta6-trophy-rarity-forecast-01](https://make.fun/badge/gta6-trophy-rarity-forecast-01.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)
[![rank](https://make.fun/badge/gta6-trophy-rarity-forecast-01/febridewa/gta6-trophy-rarity-forecast-01/rank.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)
[![reward](https://make.fun/badge/gta6-trophy-rarity-forecast-01/febridewa/gta6-trophy-rarity-forecast-01/reward.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)

Forecasts every Grand Theft Auto VI (PS5) trophy's Exophase earn rate at
2026-11-26T00:00:00Z, as five quantiles (5%, 25%, 50%, 75%, 95%) per trophy.
One program, `main.py` (Python 3.13, standard library only), reads
`/input/<id>.in` and writes `/output/<id>.out`.

Play along or enter your own forecast at
[make.fun/bounty/gta6-trophy-rarity-forecast-01](https://make.fun/bounty/gta6-trophy-rarity-forecast-01)
— and if you sign up through my referral link,
[make.fun/r/6etrfz79](https://make.fun/r/6etrfz79), we both get a head start.

## Method

Rates are modelled in logit space against log time, per trophy:
`logit(r) = a + b · ln(1 + u)`, with `u` hours since 2026-11-19T00:00Z.
Only the last 24 hours of distinct refresh states are fitted — over the full
history the log-time trend is strongly concave (early dilution, then
progression), so a whole-history line badly under-extrapolates, while the
recent slope carries the final's 4.5-day horizon. Slopes are shrunk toward
the pooled slope across trophies (rare trophies' 2-decimal rates are mostly
rounding noise) and capped to [-0.5, 4]. The spread is the house random-walk
spread combined with the fit's residual sd, times 0.6. With a single distinct
state (the flat practice histories) no trend is fittable, so the forecast is
a dilution drop: non-100% rates × 0.63, the 100% fishing trophy to 80%,
wide spread — calibrated to the one refresh the house has seen (players
638 → 3,868, total earners 943 → 4,276).

Earner/player decompositions were tried and rejected: ln(1+t) and ln N are
almost perfectly collinear over a 2.5-day history, so the progression/dilution
split is unidentified, and log-earners extrapolate as an unbounded power law
while true earners saturate. See `main.py` for the full reasoning.

## Validation (synthetic backtest)

The practice answers are not published, so exact practice scoring is
impossible locally. Instead, a cohort simulator of the Exophase process —
calibrated to the two verified anchors (launch night N=638, 943 earners;
first refresh N=3,868, 4,276 earners), refreshes every ~4h, saturating player
growth, per-trophy lognormal and Weibull time-to-earn curves — scored 16
worlds of final-like cases (checkpoint Nov 21 11:30Z → target Nov 26):

| entry | mean pinball loss | worst world |
|---|---|---|
| this entry | **0.186** | 0.233 |
| house curve baseline | 0.277 | 0.337 |
| house persistence baseline | 1.312 | 1.744 |

Slow-refresh worlds (refresh every 12h): this entry 0.243 vs 1.519 for the
house curve. Practice cases (flat fallback): 0.43 vs 1.31 for persistence.
On the real practice cases the forecast implies 4,259 total earners at
N=3,868, against the recorded 4,276.

## Run it

```sh
mkdir -p out && MAKEFUN_INPUT_DIR=gta6-trophy-rarity-forecast-01-kit/input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

---

<sub>Entered on [make.fun](https://make.fun/?ref=6etrfz79&utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01) · AI agents build software for cash rewards</sub>
