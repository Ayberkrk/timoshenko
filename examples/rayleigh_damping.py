"""Fit Rayleigh damping to two target modes and inspect its frequency curve."""

from __future__ import annotations

import json

import timoshenko as tm


fit = tm.rayleigh_damping_coefficients(
    frequency_1_hz=0.8,
    damping_ratio_1=0.02,
    frequency_2_hz=4.0,
    damping_ratio_2=0.02,
)
result = fit.to_dict()
result["evaluated_damping_ratio_at_2_hz"] = fit.modal_damping_ratio(2.0)
print(json.dumps(result, indent=2))
