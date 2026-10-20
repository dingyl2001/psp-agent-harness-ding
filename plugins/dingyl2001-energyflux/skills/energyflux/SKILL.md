---
name: energyflux
description: Use when the user asks about solar wind energy budgets, the contribution of alpha particles to PSP energy flux, or wants to compute the multi-species (proton/alpha/electron) MHD energy-flux terms for given plasma parameters.
---

# Solar wind energy-flux model

Three tools, built on a multi-species extension of Belcher (1971) and
Halekas et al. (2023):

- `compute_energy_budget(...)` — the full energy-flux breakdown (kinetic,
  enthalpy, gravitational, ambipolar-electric for protons and alphas
  separately, plus the Alfven wave term) for one set of plasma moments.
- `alpha_density_from_quasineutrality(n_e_cm3, n_p_cm3)` — infer n_alpha
  when PSP's direct SPAN-I alpha density isn't trusted for a given
  interval.
- `compare_alpha_density_assumptions(...)` — see how much a fixed
  abundance-ratio assumption differs from a measured alpha density, for
  a given n_p.

## Conventions

- All inputs are in PSP's usual native units: density in cm^-3, speed in
  km/s, ion temperature in K, electron temperature in eV, B in nT,
  distance in solar radii (R_rs).
- `dv_kms`/`dB_nT` are rms *fluctuation* amplitudes (not the mean field),
  used only for the Alfven wave term; pass 0 for either to omit that
  term rather than guessing a value.
- Alpha particles carry charge 2e, so their ambipolar-electric term uses
  Z=2, not Z=1 — this is the main thing a naive proton-only extension
  gets wrong, along with leaving alpha mass out of the total density
  used for the Alfven speed.
- These tools compute a budget from values you (or the user) supply —
  they don't fetch PSP data themselves. If the user wants a real
  interval's values, ask them for the numbers or point them to their own
  data pipeline.
