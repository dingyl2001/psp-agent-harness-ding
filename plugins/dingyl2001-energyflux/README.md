# dingyl2001-energyflux

A multi-species (proton + alpha + electron-coupling) MHD solar wind
energy-flux model, as an MCP server. Research plugin for UCLA's AI in
Research (EPSS 254), week 3.

## What it is

Generalizes two published single-species (proton-only) energy-flux
models to track alpha particles as their own species:

- Belcher (1971, ApJ 168, 509): one-fluid polytrope wind + Alfven-wave
  pressure, a closed-form conserved energy flux.
- Halekas et al. (2023, ApJ 952, 26): empirical proton energy budget
  from real PSP data (kinetic+enthalpy, gravitational, ambipolar
  electric potential, Alfven wave energy) — which explicitly neglects
  alpha particles.

Alpha particles get their own kinetic+enthalpy term (their own bulk
speed, capturing real alpha-proton differential streaming), their own
gravitational term, their own ambipolar-electric term (charge number
Z=2, since an alpha carries twice a proton's charge), and their mass
contributes to the total mass density used for the Alfven speed and wave
term. Validated against real PSP Encounter 10 SWEAP data (see
`~/work/fast_radial_scan/mhd_energy_flux_model.py`, the original,
non-portable version this plugin's physics core is copied from).

Three tools, in `server.py` (a `uv` script, no project setup, no
external data access, no API key needed):

- `compute_energy_budget(...)` — full per-term energy-flux breakdown
  from PSP-style plasma moments.
- `alpha_density_from_quasineutrality(n_e_cm3, n_p_cm3)` — infer
  n_alpha when SPAN-I's direct alpha density is suspect.
- `compare_alpha_density_assumptions(...)` — a measured alpha density
  vs. a fixed abundance-ratio assumption, side by side.

## Environment variables

None — purely computational, no external calls.

## Load it

Claude Code:
```
claude --plugin-dir plugins/dingyl2001-energyflux
```

Codex: `codex mcp add dingyl2001-energyflux -- uv run --script /absolute/path/to/server.py`
(check `codex mcp add --help` for current flags).

## Check it works

Ask: "Using n_p=174 cm^-3, U_p=315 km/s, T_p=1e5 K, n_alpha=2.35 cm^-3,
U_alpha=390 km/s, T_alpha=4e5 K, n_e=179 cm^-3, T_e=15 eV, B=50 nT,
dv=30 km/s, dB=15 nT, R=70 Rs, what's the energy budget?" — these are
close to the real median values from PSP Encounter 10 used to validate
this model. Expect the alpha particle to carry roughly 5-10% of the
total energy flux with these numbers.
