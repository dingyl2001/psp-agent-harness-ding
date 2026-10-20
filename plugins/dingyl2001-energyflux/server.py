#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["mcp"]
# ///
"""Multi-species (proton + alpha + electron) MHD solar wind energy-flux
model, as an MCP server. Research plugin for AI in Research, week 3.

Physics: generalizes Belcher (1971, ApJ 168, 509) and Halekas et al.
(2023, ApJ 952, 26) -- both single-species (proton-only) energy-flux
models -- to track alpha particles as their own species: their own
kinetic+enthalpy term (captures real alpha-proton differential
streaming), their own gravitational term, their own ambipolar-electric
term (charge number Z=2, not Z=1), and their mass contributing to the
total mass density used for the Alfven speed and wave-energy term.

This is a self-contained copy of the physics core originally developed
and validated against real PSP Encounter 10 data in
~/work/fast_radial_scan/mhd_energy_flux_model.py -- duplicated here (not
imported from that path) so this plugin is portable: anyone who clones
this repository can run it without that external, machine-specific path.
"""
import math

from mcp.server import MCPServer

# ---------------------------------------------------------------------------
# Physical constants (SI)
# ---------------------------------------------------------------------------
m_p = 1.67262192e-27        # proton mass [kg]
m_alpha = 4.0 * m_p         # alpha mass [kg]
k_B = 1.380649e-23          # Boltzmann constant [J/K]
G = 6.674e-11                # gravitational constant [m^3 kg^-1 s^-2]
M_sun = 1.989e30            # solar mass [kg]
mu0 = 1.25663706e-6          # vacuum permeability [T m / A]
q_e = 1.602176634e-19       # elementary charge [C]
R_sun_m = 6.96e8             # solar radius [m]

Z_PROTON = 1.0
Z_ALPHA = 2.0


def _budget_si(n_p, U_p, T_p, n_alpha, U_alpha, T_alpha, n_e, phi_e, B, dv, dB, r):
    """Core SI-unit computation. All densities in m^-3, speeds in m/s,
    temperatures in K, phi_e in V, B in T, dv/dB in m/s (dB already
    converted to a velocity-equivalent b/sqrt(mu0 rho)), r in m.
    """
    rho_total = n_p * m_p + n_alpha * m_alpha

    F_kin_p = n_p * U_p * (0.5 * m_p * U_p**2 + 2.5 * k_B * T_p)
    F_kin_alpha = n_alpha * U_alpha * (0.5 * m_alpha * U_alpha**2 + 2.5 * k_B * T_alpha)

    F_grav_p = -n_p * U_p * m_p * G * M_sun / r
    F_grav_alpha = -n_alpha * U_alpha * m_alpha * G * M_sun / r

    F_elec_p = n_p * U_p * Z_PROTON * q_e * phi_e
    F_elec_alpha = n_alpha * U_alpha * Z_ALPHA * q_e * phi_e

    V_A = B / math.sqrt(mu0 * rho_total) if rho_total > 0 else 0.0
    z_amp_sq = dv**2 + dB**2
    E_w = rho_total * z_amp_sq / 4.0
    F_wave = (1.5 * U_p + V_A) * E_w

    F_total = (F_kin_p + F_kin_alpha + F_grav_p + F_grav_alpha
               + F_elec_p + F_elec_alpha + F_wave)

    mass_flux_p = n_p * U_p * m_p
    mass_flux_alpha = n_alpha * U_alpha * m_alpha
    alpha_mass_fraction = (
        mass_flux_alpha / (mass_flux_p + mass_flux_alpha)
        if (mass_flux_p + mass_flux_alpha) > 0 else 0.0
    )
    alpha_species_total = F_kin_alpha + F_grav_alpha + F_elec_alpha
    alpha_energy_fraction = alpha_species_total / F_total if F_total != 0 else 0.0

    return dict(
        F_kin_p=F_kin_p, F_kin_alpha=F_kin_alpha,
        F_grav_p=F_grav_p, F_grav_alpha=F_grav_alpha,
        F_elec_p=F_elec_p, F_elec_alpha=F_elec_alpha,
        F_wave=F_wave, F_total=F_total,
        rho_total=rho_total, V_A=V_A,
        alpha_mass_fraction=alpha_mass_fraction,
        alpha_energy_fraction=alpha_energy_fraction,
    )


def _budget_native(n_p_cm3, U_p_kms, T_p_K, n_alpha_cm3, U_alpha_kms, T_alpha_K,
                    n_e_cm3, T_e_eV, B_nT, dv_kms, dB_nT, R_rs):
    """Same computation, in this project's native PSP-data units."""
    n_p, U_p = n_p_cm3 * 1e6, U_p_kms * 1e3
    n_alpha, U_alpha = n_alpha_cm3 * 1e6, U_alpha_kms * 1e3
    B = B_nT * 1e-9
    dv = dv_kms * 1e3
    rho_total = n_p * m_p + n_alpha * m_alpha
    dB_vel_equiv = (dB_nT * 1e-9) / math.sqrt(mu0 * rho_total) if rho_total > 0 else 0.0
    phi_e = 2.5 * T_e_eV  # volts; adiabatic-electron convention (Halekas+2023 Sec. 2)
    r_m = R_rs * R_sun_m
    return _budget_si(n_p, U_p, T_p_K, n_alpha, U_alpha, T_alpha_K,
                       n_e_cm3 * 1e6, phi_e, B, dv, dB_vel_equiv, r_m)


def _format_budget(b: dict) -> str:
    return (
        f"Energy flux terms (W/m^2):\n"
        f"  proton kinetic+enthalpy  F_kin_p      = {b['F_kin_p']:.4e}\n"
        f"  alpha  kinetic+enthalpy  F_kin_alpha  = {b['F_kin_alpha']:.4e}\n"
        f"  proton gravitational     F_grav_p     = {b['F_grav_p']:.4e}\n"
        f"  alpha  gravitational     F_grav_alpha = {b['F_grav_alpha']:.4e}\n"
        f"  proton ambipolar-electric F_elec_p    = {b['F_elec_p']:.4e}\n"
        f"  alpha  ambipolar-electric F_elec_alpha = {b['F_elec_alpha']:.4e} (Z=2)\n"
        f"  Alfven wave              F_wave       = {b['F_wave']:.4e}\n"
        f"  TOTAL                    F_total      = {b['F_total']:.4e}\n\n"
        f"Diagnostics:\n"
        f"  Alfven speed V_A         = {b['V_A']/1e3:.2f} km/s\n"
        f"  total mass density rho   = {b['rho_total']:.4e} kg/m^3\n"
        f"  alpha mass fraction      = {100*b['alpha_mass_fraction']:.2f}% of mass flux\n"
        f"  alpha energy fraction    = {100*b['alpha_energy_fraction']:.2f}% of total energy flux"
    )


mcp = MCPServer("energyflux")


@mcp.tool()
def compute_energy_budget(
    n_p_cm3: float, U_p_kms: float, T_p_K: float,
    n_alpha_cm3: float, U_alpha_kms: float, T_alpha_K: float,
    n_e_cm3: float, T_e_eV: float,
    B_nT: float, dv_kms: float, dB_nT: float,
    R_rs: float,
) -> str:
    """Compute the multi-species (proton + alpha + electron-coupling)
    steady-state MHD energy-flux budget at one point in the solar wind,
    from PSP-style plasma moments.

    All units match what PSP SWEAP/FIELDS data products normally use:

    Args:
        n_p_cm3: proton number density [cm^-3], e.g. 50.
        U_p_kms: proton bulk speed [km/s], e.g. 350.
        T_p_K: proton temperature [K], e.g. 1e5.
        n_alpha_cm3: alpha particle number density [cm^-3], e.g. 1.5
            (typically a few % of n_p_cm3).
        U_alpha_kms: alpha bulk speed [km/s], e.g. 370 (alphas usually
            run faster than protons by roughly the local Alfven speed).
        T_alpha_K: alpha temperature [K], e.g. 4e5.
        n_e_cm3: total electron number density [cm^-3], e.g. 53.
        T_e_eV: electron temperature [eV], e.g. 15.
        B_nT: magnetic field magnitude [nT], e.g. 50.
        dv_kms: rms outward-propagating velocity-fluctuation amplitude
            [km/s], e.g. 30. Use 0 to omit the wave term.
        dB_nT: rms outward-propagating magnetic-fluctuation amplitude
            [nT], e.g. 15. Use 0 to omit the wave term.
        R_rs: heliocentric distance [solar radii], e.g. 20.

    Returns a breakdown of every energy-flux term (kinetic+enthalpy,
    gravitational and ambipolar-electric for each of protons and alphas,
    plus the Alfven wave term), the total, and the alpha particle's share
    of the mass flux and the energy flux.
    """
    try:
        b = _budget_native(n_p_cm3, U_p_kms, T_p_K, n_alpha_cm3, U_alpha_kms, T_alpha_K,
                            n_e_cm3, T_e_eV, B_nT, dv_kms, dB_nT, R_rs)
    except (ValueError, ZeroDivisionError) as e:
        return f"Could not compute: {e}. Check that R_rs and densities are positive."
    return _format_budget(b)


@mcp.tool()
def alpha_density_from_quasineutrality(n_e_cm3: float, n_p_cm3: float) -> str:
    """Infer the alpha particle density from quasineutrality, n_alpha =
    (n_e - n_p) / 2, when a direct alpha density measurement isn't
    trusted (PSP's SPAN-I alpha density moment is known to be less
    reliable than its proton and QTN electron density moments, since
    alphas often drift partly out of the instrument's field of view).

    Args:
        n_e_cm3: total electron number density [cm^-3], typically from
            quasi-thermal noise (QTN), e.g. 53.
        n_p_cm3: proton number density [cm^-3], typically from SPAN-I or
            SPC, e.g. 50.

    Returns the inferred alpha density and the alpha/proton ratio.
    """
    n_alpha = (n_e_cm3 - n_p_cm3) / 2.0
    if n_alpha < 0:
        return (
            f"n_alpha = {n_alpha:.4f} cm^-3 is negative, which isn't physical. "
            f"n_e_cm3 ({n_e_cm3}) should be >= n_p_cm3 ({n_p_cm3}); check which "
            f"density product each value actually came from."
        )
    ratio = n_alpha / n_p_cm3 if n_p_cm3 > 0 else float("nan")
    return (
        f"n_alpha = {n_alpha:.4f} cm^-3 (from quasineutrality: (n_e - n_p) / 2)\n"
        f"n_alpha / n_p = {ratio:.4f} ({100*ratio:.2f}%)"
    )


@mcp.tool()
def compare_alpha_density_assumptions(
    n_p_cm3: float, measured_n_alpha_cm3: float,
    fixed_ratio: float = 0.0433,
) -> str:
    """Compare how much the alpha particle's energy-flux contribution
    changes depending on whether you trust a directly measured alpha
    density versus a fixed abundance ratio assumption (n_alpha = ratio *
    n_p). Useful when the real alpha density moment is of uncertain
    quality and you want to see how much the choice actually matters for
    a given encounter.

    Args:
        n_p_cm3: proton number density [cm^-3], e.g. 174.
        measured_n_alpha_cm3: the directly measured alpha density
            [cm^-3] to compare against, e.g. 2.35.
        fixed_ratio: the assumed fixed n_alpha/n_p ratio, default 0.0433
            (~4.3%, a common solar-wind-average assumption).

    Returns the two implied alpha densities, their ratio to each other,
    and each one's resulting alpha energy fraction, using representative
    speed/temperature/field values so the two cases are directly
    comparable (not a full PSP-data run -- use compute_energy_budget
    directly for that, with the real values for a specific interval).
    """
    if n_p_cm3 <= 0 or measured_n_alpha_cm3 < 0:
        return "n_p_cm3 must be positive and measured_n_alpha_cm3 must not be negative."

    # Representative "typical young solar wind" values, held fixed so the
    # comparison isolates the effect of the density choice alone.
    U_p, T_p = 350.0, 1e5
    U_alpha, T_alpha = 370.0, 4e5
    T_e, B, dv, dB, R_rs = 15.0, 50.0, 30.0, 15.0, 20.0

    fixed_n_alpha = n_p_cm3 * fixed_ratio
    n_e_measured = n_p_cm3 + 2 * measured_n_alpha_cm3
    n_e_fixed = n_p_cm3 + 2 * fixed_n_alpha

    b_measured = _budget_native(n_p_cm3, U_p, T_p, measured_n_alpha_cm3, U_alpha, T_alpha,
                                 n_e_measured, T_e, B, dv, dB, R_rs)
    b_fixed = _budget_native(n_p_cm3, U_p, T_p, fixed_n_alpha, U_alpha, T_alpha,
                              n_e_fixed, T_e, B, dv, dB, R_rs)

    ratio_measured = measured_n_alpha_cm3 / n_p_cm3
    factor = (fixed_ratio / ratio_measured) if ratio_measured > 0 else float("inf")

    return (
        f"Measured: n_alpha = {measured_n_alpha_cm3:.4f} cm^-3 "
        f"(n_alpha/n_p = {100*ratio_measured:.2f}%) "
        f"-> alpha energy fraction = {100*b_measured['alpha_energy_fraction']:.2f}%\n"
        f"Fixed-ratio ({100*fixed_ratio:.2f}%): n_alpha = {fixed_n_alpha:.4f} cm^-3 "
        f"-> alpha energy fraction = {100*b_fixed['alpha_energy_fraction']:.2f}%\n\n"
        f"The fixed-ratio assumption implies {factor:.2f}x the measured alpha "
        f"density for this n_p. (Computed with representative mid-young-wind "
        f"speed/temperature/field values, not a specific real interval -- "
        f"use compute_energy_budget with real values for an actual data point.)"
    )


if __name__ == "__main__":
    mcp.run()
