# Demo 2 (fan out) + Demo 3 (follow up)

(session `20261027-162612`)

## main

**[   0.0s] tool call:** `subagent({"task":"Compute the multi-species MHD energy-flux budget for Case A (slow wind, R=20 Rs) with parameters: n_p=80 cm^-3, U_p=300 km/s, T_p=8e4 K, n_alpha=1.2 cm^-3, U_alpha=310 km/s, T_alpha=3e5 K, n_e=82.4 cm^-3, T_e=12 eV, B=60 nT, dv=10 km/s, dB=5 nT, R=20 Rs. Return the full breakdown including the alpha particle's share of the mass flux and energy flux.","action":"start","agent":"energyflux-researcher"})`

**[   0.0s] tool call:** `subagent({"agent":"energyflux-researcher","action":"start","task":"Compute the multi-species MHD energy-flux budget for Case B (fast wind, R=20 Rs) with parameters: n_p=20 cm^-3, U_p=650 km/s, T_p=2e5 K, n_alpha=1.6 cm^-3, U_alpha=700 km/s, T_alpha=1e6 K, n_e=23.2 cm^-3, T_e=20 eV, B=40 nT, dv=50 km/s, dB=25 nT, R=20 Rs. Return the full breakdown including the alpha particle's share of the mass flux and energy flux."})`

**[   0.0s] tool call:** `subagent({"agent":"energyflux-researcher","action":"start","task":"Compute the multi-species MHD energy-flux budget for Case C (intermediate, R=50 Rs) with parameters: n_p=40 cm^-3, U_p=450 km/s, T_p=1.2e5 K, n_alpha=0.8 cm^-3, U_alpha=470 km/s, T_alpha=5e5 K, n_e=41.6 cm^-3, T_e=15 eV, B=25 nT, dv=25 km/s, dB=12 nT, R=50 Rs. Return the full breakdown including the alpha particle's share of the mass flux and energy flux."})`

**[   0.0s] tool result (subagent):**
```
Started sa-1 (energyflux-researcher).
```

**[   0.0s] tool result (subagent):**
```
Started sa-2 (energyflux-researcher).
```

**[   0.0s] tool result (subagent):**
```
Started sa-3 (energyflux-researcher).
```

**[   2.4s] tool call:** `subagent({"ids":["sa-1","sa-2","sa-3"],"timeout":120,"action":"wait"})`

**[  22.4s] tool result (subagent):**
```
sa-1 (idle): **Total energy flux: 1.71 × 10⁻³ W/m²; alpha particles carry 6.03 % of the energy flux (and 5.84 % of the mass flux).**  
Even though alphas are only ~1.5 % of the particle count, their higher flow speed (~310 vs 300 km/s), hotter temperature (3×10⁵ K vs 8×10⁴ K), and double charge (Z=2 in the ambipolar term) make them contribute a disproportionate ~6 % of the total energy flux in this slow-wind interval at 20 R⊙.

sa-2 (idle): **Energy-flux budget (Case B, fast wind at 20 Rₛ)**  

| Term | Flux (W m⁻²) |
|------|--------------|
| Proton kinetic + enthalpy | 4.68 × 10⁻³ |
| Alpha kinetic + enthalpy | 1.87 × 10⁻³ |
| Proton gravitational | −2.07 × 10⁻⁴ |
| Alpha gravitational | −7.15 × 10⁻⁵ |
| Proton ambipolar-electric (Z=1) | 1.04 × 10⁻⁴ |
| Alpha ambipolar-electric (Z=2) | 1... [truncated]
```

**[  22.4s] user:** [subagent notes] sa-3 (energyflux-researcher) is idle after 2 turns: **Energy-flux budget (Case C, R = 50 Rₛ)**  
- **Total energy flux:** 3.43 × 10⁻³ W/m²  
- **Alpha particle share:** 8.15 % of the energy flux (7.71 % of the mass flux)  

**Breakdown (W/m²):**  
  Proton kinetic+enthalpy: 3.12 × 10⁻³  
  Alpha kinetic+enthalpy: 2.84 × 10⁻⁴  
  Proton gravitational: –1.15 × 10⁻⁴  
  Alpha gravitational: –9.60 × 10⁻⁶  
  Proton ambipolar-electric: 1.08 × 10⁻⁴  
  Alpha ambipolar-electric (Z=2): 4.52 × 10⁻⁶  
  Alfvén wave (dv=25 km/s, dB=12 nT): 3.03 × 10⁻⁵  

**
[subagent notes] sa-2 (energyflux-researcher) is idle after 2 turns: **Energy-flux budget (Case B, fast wind at 20 Rₛ)**  

| Term | Flux (W m⁻²) |
|------|--------------|
| Proton kinetic + enthalpy | 4.68 × 10⁻³ |
| Alpha kinetic + enthalpy | 1.87 × 10⁻³ |
| Proton gravitational | −2.07 × 10⁻⁴ |
| Alpha gravitational | −7.15 × 10⁻⁵ |
| Proton ambipolar-electric (Z=1) | 1.04 × 10⁻⁴ |
| Alpha ambipolar-electric (Z=2) | 1.79 × 10⁻⁵ |
| Alfvén wave (outward) | 1.74 × 10⁻⁴ |
| **Total** | **6.57 × 10⁻³** |

**Alpha-particle shares**  
- Mass flux: 25.6 %  
- Energy 
[subagent notes] sa-1 (energyflux-researcher) is idle after 2 turns: **Total energy flux: 1.71 × 10⁻³ W/m²; alpha particles carry 6.03 % of the energy flux (and 5.84 % of the mass flux).**  
Even though alphas are only ~1.5 % of the particle count, their higher flow speed (~310 vs 300 km/s), hotter temperature (3×10⁵ K vs 8×10⁴ K), and double charge (Z=2 in the ambipolar term) make them contribute a disproportionate ~6 % of the total energy flux in this slow-wind interval at 20 R⊙.

**[  31.3s] assistant:** **Summary: Alpha Energy Fractions**

| Case | Alpha Energy Fraction | Alpha Mass Fraction | Total Energy Flux |
|------|----------------------|---------------------|-------------------|
| **A** (slow, 20 Rₛ) | **6.03%** | 5.84% | 1.71 × 10⁻³ W/m² |
| **B** (fast, 20 Rₛ) | **27.7%** | 25.6% | 6.57 × 10⁻³ W/m² |
| **C** (intermediate, 50 Rₛ) | **8.15%** | 7.71% | 3.43 × 10⁻³ W/m² |

**Case B (fast wind) has the largest alpha energy fraction by a wide margin — 27.7%**, nearly 3.5× Case C and 4.6× Case A.

The fast wind's high alpha bulk speed (700 vs 650 km/s) and extreme temperature (1 MK vs 0.2 MK for protons) amplify both kinetic and enthalpy fluxes per unit mass, letting alphas punch well above their ~4% number-density weight.

**[  33.2s] tool call:** `subagent({"action":"send","id":"sa-1","message":"What was the Alfven speed in your result?"})`

**[  33.2s] tool result (subagent):**
```
Sent to sa-1.
```

**[  35.6s] tool call:** `subagent({"ids":["sa-1"],"action":"wait","timeout":30})`

**[  36.4s] tool result (subagent):**
```
sa-1 (idle): The Alfvén speed was **142.12 km/s** (as reported in the diagnostics section of the computation).
```

**[  36.4s] user:** [subagent notes] sa-1 (energyflux-researcher) is idle after 3 turns: The Alfvén speed was **142.12 km/s** (as reported in the diagnostics section of the computation).

**[  37.6s] assistant:** The Alfvén speed in Case A was **142.12 km/s**.

## sa-1

**[   0.0s] tool call:** `energyflux__compute_energy_budget({"dv_kms":10,"U_alpha_kms":310,"T_alpha_K":300000,"n_e_cm3":82.4,"n_alpha_cm3":1.2,"U_p_kms":300,"T_p_K":80000,"T_e_eV":12,"B_nT":60,"dB_nT":5,"R_rs":20,"n_p_cm3":80})`

**[   0.0s] tool result (energyflux__compute_energy_budget):**
```
Energy flux terms (W/m^2):
  proton kinetic+enthalpy  F_kin_p      = 1.8727e-03
  alpha  kinetic+enthalpy  F_kin_alpha  = 1.2344e-04
  proton gravitational     F_grav_p     = -3.8282e-04
  alpha  gravitational     F_grav_alpha = -2.3735e-05
  proton ambipolar-electric F_elec_p    = 1.1536e-04
  alpha  ambipolar-electric F_elec_alpha = 3.5761e-06 (Z=2)
  Alfven wave              F_wave       = 5.0446e-06
  TOTAL                    F_total      = 1.7136e-03

Diagnostics:
  Alfven speed V_A         = 142.12 km/s
  total mass density rho   = 1.4184e-19 kg/m^3
  alpha mass fraction      = 5.84% of mass flux
  alpha energy fraction    = 6.03% of total energy flux
```

**[  17.6s] assistant:** **Total energy flux: 1.71 × 10⁻³ W/m²; alpha particles carry 6.03 % of the energy flux (and 5.84 % of the mass flux).**  
Even though alphas are only ~1.5 % of the particle count, their higher flow speed (~310 vs 300 km/s), hotter temperature (3×10⁵ K vs 8×10⁴ K), and double charge (Z=2 in the ambipolar term) make them contribute a disproportionate ~6 % of the total energy flux in this slow-wind interval at 20 R⊙.

**[  28.5s] user:** What was the Alfven speed in your result?

**[  31.6s] assistant:** The Alfvén speed was **142.12 km/s** (as reported in the diagnostics section of the computation).

## sa-2

**[   0.0s] tool call:** `energyflux__compute_energy_budget({"T_e_eV":20,"n_e_cm3":23.2,"dB_nT":25,"R_rs":20,"U_p_kms":650,"B_nT":40,"n_p_cm3":20,"T_p_K":200000,"n_alpha_cm3":1.6,"U_alpha_kms":700,"dv_kms":50,"T_alpha_K":1000000})`

**[   0.0s] tool result (energyflux__compute_energy_budget):**
```
Energy flux terms (W/m^2):
  proton kinetic+enthalpy  F_kin_p      = 4.6832e-03
  alpha  kinetic+enthalpy  F_kin_alpha  = 1.8745e-03
  proton gravitational     F_grav_p     = -2.0736e-04
  alpha  gravitational     F_grav_alpha = -7.1459e-05
  proton ambipolar-electric F_elec_p    = 1.0414e-04
  alpha  ambipolar-electric F_elec_alpha = 1.7944e-05 (Z=2)
  Alfven wave              F_wave       = 1.7394e-04
  TOTAL                    F_total      = 6.5749e-03

Diagnostics:
  Alfven speed V_A         = 169.81 km/s
  total mass density rho   = 4.4157e-20 kg/m^3
  alpha mass fraction      = 25.63% of mass flux
  alpha energy fraction    = 27.70% of total energy flux
```

**[  11.6s] assistant:** **Energy-flux budget (Case B, fast wind at 20 Rₛ)**  

| Term | Flux (W m⁻²) |
|------|--------------|
| Proton kinetic + enthalpy | 4.68 × 10⁻³ |
| Alpha kinetic + enthalpy | 1.87 × 10⁻³ |
| Proton gravitational | −2.07 × 10⁻⁴ |
| Alpha gravitational | −7.15 × 10⁻⁵ |
| Proton ambipolar-electric (Z=1) | 1.04 × 10⁻⁴ |
| Alpha ambipolar-electric (Z=2) | 1.79 × 10⁻⁵ |
| Alfvén wave (outward) | 1.74 × 10⁻⁴ |
| **Total** | **6.57 × 10⁻³** |

**Alpha-particle shares**  
- Mass flux: 25.6 %  
- Energy flux: 27.7 %  

**Interpretation:** Alphas carry ~28 % of the total energy flux—exceeding their 26 % mass share—because their higher bulk speed (700 vs. 650 km/s) and much larger temperature (1 MK vs. 0.2 MK) amplify both kinetic and enthalpy contributions.

## sa-3

**[   0.0s] tool call:** `energyflux__compute_energy_budget({"B_nT":25,"U_alpha_kms":470,"n_e_cm3":41.6,"U_p_kms":450,"T_p_K":120000,"T_alpha_K":500000,"R_rs":50,"n_p_cm3":40,"T_e_eV":15,"n_alpha_cm3":0.8,"dB_nT":12,"dv_kms":25})`

**[   0.0s] tool result (energyflux__compute_energy_budget):**
```
Energy flux terms (W/m^2):
  proton kinetic+enthalpy  F_kin_p      = 3.1229e-03
  alpha  kinetic+enthalpy  F_kin_alpha  = 2.8434e-04
  proton gravitational     F_grav_p     = -1.1484e-04
  alpha  gravitational     F_grav_alpha = -9.5959e-06
  proton ambipolar-electric F_elec_p    = 1.0815e-04
  alpha  ambipolar-electric F_elec_alpha = 4.5181e-06 (Z=2)
  Alfven wave              F_wave       = 3.0272e-05
  TOTAL                    F_total      = 3.4257e-03

Diagnostics:
  Alfven speed V_A         = 82.96 km/s
  total mass density rho   = 7.2257e-20 kg/m^3
  alpha mass fraction      = 7.71% of mass flux
  alpha energy fraction    = 8.15% of total energy flux
```

**[  12.4s] assistant:** **Energy-flux budget (Case C, R = 50 Rₛ)**  
- **Total energy flux:** 3.43 × 10⁻³ W/m²  
- **Alpha particle share:** 8.15 % of the energy flux (7.71 % of the mass flux)  

**Breakdown (W/m²):**  
  Proton kinetic+enthalpy: 3.12 × 10⁻³  
  Alpha kinetic+enthalpy: 2.84 × 10⁻⁴  
  Proton gravitational: –1.15 × 10⁻⁴  
  Alpha gravitational: –9.60 × 10⁻⁶  
  Proton ambipolar-electric: 1.08 × 10⁻⁴  
  Alpha ambipolar-electric (Z=2): 4.52 × 10⁻⁶  
  Alfvén wave (dv=25 km/s, dB=12 nT): 3.03 × 10⁻⁵  

**Interpretation:** Alpha particles carry a slightly larger fraction of the energy flux (8.15 %) than of the mass flux (7.71 %) because their higher bulk speed (470 vs 450 km/s) and much higher temperature (5×10⁵ vs 1.2×10⁵ K) boost their kinetic and enthalpy fluxes per unit mass.

