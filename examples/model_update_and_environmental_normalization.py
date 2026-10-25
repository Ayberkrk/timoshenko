"""Fit local story stiffness and remove a known environmental frequency trend."""

import numpy as np

import timoshenko as tm


reference = tm.Structure(
    structure_id="three-story-reference",
    story_masses_kg=(120_000.0, 110_000.0, 100_000.0),
    story_stiffness_n_m=(85e6, 70e6, 55e6),
)
measured_model = tm.Structure(
    structure_id=reference.structure_id,
    story_masses_kg=reference.story_masses_kg,
    story_stiffness_n_m=(68e6, 70e6, 44e6),
)
update = tm.update_story_stiffness(reference, measured_model.natural_frequencies_hz)
print("Story stiffness scales:", update.story_stiffness_scale_factors)
print("Frequency fit RMS error [%]:", update.residual_rms_pct)

temperature = np.linspace(-10.0, 30.0, 40)
humidity = 20.0 + 60.0 * np.linspace(0.0, 1.0, 40) ** 2
environment = np.column_stack((temperature, humidity))
reference_modes_hz = np.array([2.0, 5.0])
trend_hz_per_unit = np.array([[0.002, -0.001], [-0.01, 0.004]])
baseline_records = reference_modes_hz + (
    environment - environment.mean(axis=0)
) @ trend_hz_per_unit.T
baseline = tm.fit_environmental_baseline(
    environment,
    baseline_records,
    feature_names=("temperature_c", "humidity_pct"),
)
current_environment = environment.mean(axis=0) + np.array([8.0, 0.0])
current_modes_hz = reference_modes_hz + np.array([0.002, -0.01]) * 8.0
print(
    "Environment-normalized modes [Hz]:",
    baseline.normalize(current_modes_hz, current_environment),
)
