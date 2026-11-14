"""Identify three shear-building modes from synthetic stochastic displacements.

This stationary linear modal simulation is not measured building data or a
structural safety assessment. Only NumPy and the timoshenko core are needed.
"""

import numpy as np

import timoshenko as tm

building = tm.Structure([12_000.0] * 3, [8.0e6] * 3)
model_frequencies = np.asarray(building.natural_frequencies_hz)
story_k = np.asarray(building.story_stiffness_n_m)
stiffness = np.diag(story_k + np.append(story_k[1:], 0.0))
stiffness -= np.diag(story_k[1:], 1) + np.diag(story_k[1:], -1)
inv_sqrt_mass = np.diag(1.0 / np.sqrt(building.story_masses_kg))
_, eigenvectors = np.linalg.eigh(inv_sqrt_mass @ stiffness @ inv_sqrt_mass)
shapes = inv_sqrt_mass @ eigenvectors
shapes /= np.max(np.abs(shapes), axis=0)

sampling_hz = 64.0
sample_count = 32_768
burn_in = 4096
model_damping = np.array([0.02, 0.025, 0.03])
rng = np.random.default_rng(23)
# Independently excited AR(2) modal oscillators have poles exp((-zeta*omega
# +/- i*omega*sqrt(1-zeta**2))*dt). Unlike pure sinusoids, these signals have
# finite damping and stochastic excitation. Discard startup transients.
radius = np.exp(-model_damping * 2.0 * np.pi * model_frequencies / sampling_hz)
angle = 2.0 * np.pi * model_frequencies * np.sqrt(1.0 - model_damping**2) / sampling_hz
coefficient = 2.0 * radius * np.cos(angle)
modal = np.zeros((sample_count + burn_in, 3))
noise = rng.standard_normal(modal.shape)
for index in range(2, len(modal)):
    modal[index] = coefficient * modal[index - 1] - radius**2 * modal[index - 2] + noise[index]
modal = modal[burn_in:]
# Normalization sets synthetic modal displacement RMS to 1 mm; it does not
# change pole frequencies/damping. Add 0.01 mm RMS independent sensor noise.
modal *= 0.001 / np.std(modal, axis=0)
channels = modal @ shapes.T + 0.00001 * rng.standard_normal((sample_count, 3))
data = tm.MultiChannelData(channels, sampling_hz, ["floor_1", "floor_2", "floor_3"], ["m"] * 3)
result = tm.identify_ssi(
    data,
    block_rows=24,
    model_orders=(6, 12, 18, 24),
    min_frequency_hz=1.0,
    max_frequency_hz=10.0,
    min_stable_orders=3,
)
print(f"Synthetic displacement record: {sample_count / sampling_hz:.0f} s at {sampling_hz:g} Hz")
print("Model Hz | SSI Hz | relative error | model damping | SSI damping")
# Require all modes, not just a successful exit with an empty/partial result.
if len(result.modes) != len(model_frequencies):
    raise RuntimeError(f"Expected three stable modes, found {len(result.modes)}")
for expected, damping, mode in zip(model_frequencies, model_damping, result.modes, strict=True):
    error = abs(mode.frequency_hz - expected) / expected
    print(
        f"{expected:8.4f} | {mode.frequency_hz:6.4f} | {error:13.2%} | "
        f"{damping:13.2%} | {mode.damping_ratio:11.2%}"
    )
    if error > 0.02:
        raise RuntimeError("Synthetic SSI frequency error exceeds 2%")
print("Damping is a finite-record estimate; stable poles alone do not validate a real structure.")
