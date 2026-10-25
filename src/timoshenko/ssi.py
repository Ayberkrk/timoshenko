"""Covariance-driven stochastic subspace identification for output-only data."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence

import numpy as np

from .multichannel import MultiChannelData


@dataclass(frozen=True)
class SSIMode:
    """One stable pole family estimated by covariance-driven SSI."""

    frequency_hz: float
    damping_ratio: float
    channel_ids: tuple[str, ...]
    units: tuple[str, ...]
    shape_real: tuple[float, ...]
    shape_imag: tuple[float, ...]
    stable_order_count: int
    stability_score: float

    def to_dict(self) -> dict:
        return {
            "frequency_hz": self.frequency_hz,
            "damping_ratio": self.damping_ratio,
            "channel_ids": list(self.channel_ids),
            "units": list(self.units),
            "mode_shape": [
                {"real": real, "imag": imag}
                for real, imag in zip(self.shape_real, self.shape_imag, strict=True)
            ],
            "stable_order_count": self.stable_order_count,
            "stability_score": self.stability_score,
        }


@dataclass(frozen=True)
class SSIResult:
    """Modal estimates and stability information from a set of SSI model orders."""

    modes: tuple[SSIMode, ...]
    sampling_hz: float
    sample_count: int
    block_rows: int
    model_orders: tuple[int, ...]
    channel_ids: tuple[str, ...]
    units: tuple[str, ...]
    method: str = "covariance_driven_ssi"
    status: str = "ok"
    notes: tuple[str, ...] = ()

    @property
    def frequencies_hz(self) -> tuple[float, ...]:
        return tuple(mode.frequency_hz for mode in self.modes)

    def to_dict(self) -> dict:
        return {
            "modes": [mode.to_dict() for mode in self.modes],
            "sampling_hz": self.sampling_hz,
            "sample_count": self.sample_count,
            "block_rows": self.block_rows,
            "model_orders": list(self.model_orders),
            "channel_ids": list(self.channel_ids),
            "units": list(self.units),
            "method": self.method,
            "status": self.status,
            "notes": list(self.notes),
        }


@dataclass(frozen=True)
class _Pole:
    frequency: float
    damping: float
    shape: np.ndarray


def identify_ssi(
    observations: MultiChannelData,
    *,
    block_rows: int = 20,
    model_orders: Sequence[int] | None = None,
    max_modes: int = 12,
    min_frequency_hz: float = 0.1,
    max_frequency_hz: float | None = None,
    frequency_tolerance_pct: float = 2.0,
    damping_tolerance_pct: float = 20.0,
    min_stable_orders: int = 2,
) -> SSIResult:
    """Identify stable modes with covariance-driven SSI.

    The method forms a block Toeplitz matrix from output covariance lags,
    computes its truncated SVD for each requested state-space order and
    matches poles between adjacent orders by frequency and complex MAC.
    Returned poles must remain stable over ``min_stable_orders`` consecutive
    orders. The record must be synchronized, regularly sampled and use one
    unit across channels. SSI stability is a screening diagnostic, not proof
    that a pole is a structural mode.
    """
    if not isinstance(observations, MultiChannelData):
        raise TypeError("observations must be MultiChannelData")
    if len(set(observations.units)) != 1:
        raise ValueError("SSI requires all channels to use the same measurement unit")
    rows = int(block_rows)
    if isinstance(block_rows, bool) or rows != block_rows or rows < 2 or rows > 128:
        raise ValueError("block_rows must be an integer between 2 and 128")
    if rows * observations.channel_count > 1024:
        raise ValueError(
            "block_rows times channel_count cannot exceed 1024 to bound SSI memory use"
        )
    if isinstance(max_modes, bool) or int(max_modes) != max_modes or max_modes < 1:
        raise ValueError("max_modes must be a positive integer")
    if (
        isinstance(min_stable_orders, bool)
        or int(min_stable_orders) != min_stable_orders
        or min_stable_orders < 2
    ):
        raise ValueError("min_stable_orders must be at least 2")
    fmin = float(min_frequency_hz)
    fmax = float(max_frequency_hz) if max_frequency_hz is not None else observations.sampling_hz / 2
    ftol = float(frequency_tolerance_pct) / 100.0
    ztol = float(damping_tolerance_pct) / 100.0
    if not math.isfinite(fmin) or fmin < 0.0 or not math.isfinite(fmax) or fmax <= fmin:
        raise ValueError("frequency bounds must be finite and max_frequency_hz > min_frequency_hz")
    if fmax > observations.sampling_hz / 2.0:
        raise ValueError("max_frequency_hz cannot exceed the Nyquist frequency")
    if not math.isfinite(ftol) or not 0.0 < ftol <= 0.5:
        raise ValueError("frequency_tolerance_pct must be in (0, 50]")
    if not math.isfinite(ztol) or not 0.0 < ztol <= 2.0:
        raise ValueError("damping_tolerance_pct must be in (0, 200]")

    max_order = min(rows * observations.channel_count, observations.sample_count // 8)
    if model_orders is None:
        orders = tuple(
            range(2 * observations.channel_count, max_order + 1, 2 * observations.channel_count)
        )
    else:
        if any(isinstance(item, bool) or int(item) != item for item in model_orders):
            raise ValueError("model_orders must contain positive even integers")
        orders = tuple(int(item) for item in model_orders)
        if len(orders) < 2 or tuple(sorted(set(orders))) != orders:
            raise ValueError("model_orders must contain at least two strictly increasing orders")
        if any(order < 2 or order % 2 or order > max_order for order in orders):
            raise ValueError(f"model_orders must be even and no greater than {max_order}")
    if len(orders) < min_stable_orders:
        raise ValueError("record is too short for the requested number of model orders")

    values = np.asarray(observations.samples, dtype=float)
    values = values - np.mean(values, axis=0, keepdims=True)
    covariances = _covariance_sequence(values, 2 * rows)
    poles_by_order: list[tuple[int, list[_Pole]]] = []
    for order in orders:
        poles = _identify_order(covariances, observations.sampling_hz, rows, order, fmin, fmax)
        poles_by_order.append((order, poles))

    tracks: list[list[_Pole]] = []
    last_order = -1
    for _, poles in poles_by_order:
        if last_order < 0:
            tracks.extend([[pole] for pole in poles])
            last_order = 0
            continue
        previous = poles_by_order[last_order][1]
        matches = _match_poles(previous, poles, ftol, ztol)
        for previous_index, pole_index in matches:
            track = _find_active_track(tracks, previous[previous_index])
            if track is not None:
                track.append(poles[pole_index])
        already = {pole_index for _, pole_index in matches}
        tracks.extend([[pole] for index, pole in enumerate(poles) if index not in already])
        last_order += 1

    stable: list[SSIMode] = []
    for track in tracks:
        if len(track) < min_stable_orders:
            continue
        representative = track[-1]
        shape = representative.shape
        max_component = float(np.max(np.abs(shape)))
        if max_component <= 0.0:
            continue
        shape = shape / max_component
        phase = int(np.argmax(np.abs(shape)))
        shape *= np.exp(-1j * np.angle(shape[phase]))
        stable.append(
            SSIMode(
                frequency_hz=representative.frequency,
                damping_ratio=representative.damping,
                channel_ids=tuple(observations.channel_ids),
                units=tuple(observations.units),
                shape_real=tuple(float(value.real) for value in shape),
                shape_imag=tuple(float(value.imag) for value in shape),
                stable_order_count=len(track),
                stability_score=len(track) / len(orders),
            )
        )
    stable.sort(key=lambda mode: (-mode.stability_score, mode.frequency_hz))
    deduplicated: list[SSIMode] = []
    for mode in stable:
        if all(
            abs(mode.frequency_hz - other.frequency_hz) > max(0.02, fmin * 0.01)
            for other in deduplicated
        ):
            deduplicated.append(mode)
        if len(deduplicated) >= max_modes:
            break
    deduplicated.sort(key=lambda mode: mode.frequency_hz)
    return SSIResult(
        modes=tuple(deduplicated),
        sampling_hz=observations.sampling_hz,
        sample_count=observations.sample_count,
        block_rows=rows,
        model_orders=orders,
        channel_ids=tuple(observations.channel_ids),
        units=tuple(observations.units),
        status="ok" if deduplicated else "no_stable_modes",
        notes=(
            "SSI-COV poles are retained only when matched across consecutive model orders.",
            "Frequency and damping stability thresholds are screening parameters; inspect stabilization diagrams before engineering use.",
            "Covariance estimates can be biased by short, nonstationary or strongly transient records.",
        ),
    )


def _covariance_sequence(values: np.ndarray, lags: int) -> np.ndarray:
    count, channels = values.shape
    result = np.empty((lags + 1, channels, channels), dtype=float)
    for lag in range(lags + 1):
        result[lag] = values[lag:].T @ values[: count - lag] / (count - lag)
    return result


def _identify_order(
    cov: np.ndarray,
    sampling_hz: float,
    rows: int,
    order: int,
    low: float,
    high: float,
) -> list[_Pole]:
    channels = cov.shape[1]
    toeplitz = np.empty((rows * channels, rows * channels), dtype=float)
    for row in range(rows):
        for column in range(rows):
            toeplitz[
                row * channels : (row + 1) * channels,
                column * channels : (column + 1) * channels,
            ] = cov[row + column + 1]
    u, singular, _ = np.linalg.svd(toeplitz, full_matrices=False)
    if order >= len(singular) or singular[order - 1] <= np.finfo(float).eps * singular[0]:
        return []
    observability = u[:, :order] * np.sqrt(singular[:order])[None, :]
    upper = observability[:-channels]
    lower = observability[channels:]
    transition = np.linalg.pinv(upper) @ lower
    output = observability[:channels]
    eigenvalues, eigenvectors = np.linalg.eig(transition)
    poles = []
    for index, eigenvalue in enumerate(eigenvalues):
        if abs(eigenvalue) <= 0.0 or abs(eigenvalue) >= 1.0 or eigenvalue.imag < -1e-8:
            continue
        continuous = np.log(complex(eigenvalue)) * sampling_hz
        frequency = abs(continuous.imag) / (2.0 * math.pi)
        magnitude = abs(continuous)
        damping = -continuous.real / magnitude if magnitude else math.nan
        if low <= frequency <= high and math.isfinite(damping) and 0.0 <= damping <= 0.5:
            shape = output @ eigenvectors[:, index]
            poles.append(_Pole(float(frequency), float(damping), shape))
    return poles


def _match_poles(
    previous: list[_Pole],
    current: list[_Pole],
    frequency_tolerance: float,
    damping_tolerance: float,
) -> list[tuple[int, int]]:
    candidates = []
    for i, left in enumerate(previous):
        for j, right in enumerate(current):
            relative = abs(right.frequency - left.frequency) / max(left.frequency, 1e-12)
            z_relative = abs(right.damping - left.damping) / max(left.damping, 0.01)
            mac = _mac(left.shape, right.shape)
            if relative <= frequency_tolerance and z_relative <= damping_tolerance and mac >= 0.8:
                candidates.append((relative + z_relative * 0.1 + (1.0 - mac), i, j))
    candidates.sort()
    used_left: set[int] = set()
    used_right: set[int] = set()
    result = []
    for _, i, j in candidates:
        if i not in used_left and j not in used_right:
            result.append((i, j))
            used_left.add(i)
            used_right.add(j)
    return result


def _mac(left: np.ndarray, right: np.ndarray) -> float:
    denominator = float(np.vdot(left, left).real * np.vdot(right, right).real)
    return 0.0 if denominator <= 0.0 else float(abs(np.vdot(left, right)) ** 2 / denominator)


def _find_active_track(tracks: list[list[_Pole]], pole: _Pole) -> list[_Pole] | None:
    for track in reversed(tracks):
        last = track[-1]
        if last is pole:
            return track
    return None


__all__ = ["SSIMode", "SSIResult", "identify_ssi"]
