"""Propagate known mass/stiffness uncertainty through a modal equation."""

from __future__ import annotations

import json

import timoshenko as tm


inputs = {"mass_kg": 120_000.0, "stiffness_n_m": 85_000_000.0}
standard_uncertainties = {"mass_kg": 600.0, "stiffness_n_m": 4_250_000.0}

first_order = tm.propagate_uncertainty(
    tm.natural_frequency_hz,
    inputs,
    standard_uncertainties=standard_uncertainties,
    method="first_order",
)
monte_carlo = tm.uncertainty.propagate(
    tm.natural_frequency_hz,
    inputs,
    standard_uncertainties=standard_uncertainties,
    method="monte_carlo",
    samples=20_000,
    seed=42,
)

print(json.dumps({"first_order": first_order.to_dict(), "monte_carlo": monte_carlo.to_dict()}, indent=2))
