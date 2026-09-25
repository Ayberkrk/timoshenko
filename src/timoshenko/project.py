"""Explicit, reproducible JSON project manifests and one-shot execution."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from .health import HealthAssessment, assess
from .modal import ModalResult, identify
from .multichannel import MultiChannelData, load_multichannel_csv
from .oma import FDDResult, identify_fdd
from .sensors import SensorData, load_sensors
from .structure import Structure
from .update import update


@dataclass(frozen=True)
class ProjectManifest:
    """Validated manifest fields with file paths resolved from its directory."""

    manifest_path: Path
    schema_version: str
    project_id: str
    project_name: str
    structure: Structure
    observations_path: Path
    sampling_hz: float
    columns: tuple[str, ...]
    channel_ids: tuple[str, ...]
    units: tuple[str, ...]
    method: str
    options: dict[str, Any]


@dataclass(frozen=True)
class LoadedProject:
    manifest: ProjectManifest
    observations: SensorData | MultiChannelData
    source_sha256: str
    manifest_sha256: str


@dataclass(frozen=True)
class ProjectRunResult:
    project_id: str
    project_name: str
    manifest_path: str
    source_path: str
    source_sha256: str
    manifest_sha256: str
    method: str
    analysis_options: dict[str, Any]
    structure: Structure
    modal: ModalResult | FDDResult
    health: HealthAssessment

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "project_name": self.project_name,
            "manifest_path": self.manifest_path,
            "source_path": self.source_path,
            "source_sha256": self.source_sha256,
            "manifest_sha256": self.manifest_sha256,
            "method": self.method,
            "analysis_options": dict(self.analysis_options),
            "structure": {
                "structure_id": self.structure.structure_id,
                "story_count": self.structure.story_count,
                "natural_frequencies_hz": list(self.structure.natural_frequencies_hz),
                "reference_frequencies_hz": list(self.structure.baseline_frequencies_hz),
                "observed_frequencies_hz": list(self.structure.observed_frequencies_hz),
                "update_scale_factor": self.structure.update_scale_factor,
                "update_status": self.structure.update_status,
            },
            "modal": self.modal.to_dict(),
            "health": self.health.to_dict(),
        }


_SINGLE_OPTIONS = {"max_modes", "min_frequency_hz", "max_frequency_hz", "min_peak_ratio"}
_FDD_OPTIONS = _SINGLE_OPTIONS | {"nperseg", "overlap", "max_singular_values", "min_singular_value_ratio"}


def read_manifest(path: str | Path) -> ProjectManifest:
    """Read and validate a version-1 JSON manifest; relative files resolve beside it."""
    manifest_path = Path(path).expanduser().resolve()
    if manifest_path.suffix.lower() != ".json":
        raise ValueError("project manifests must use the .json extension in version 0.6")
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("project manifest root must be a JSON object")
    schema_version = str(payload.get("schema_version", ""))
    if schema_version not in {"1", "1.0"}:
        raise ValueError("unsupported schema_version; expected '1' or '1.0'")
    project = payload.get("project")
    if not isinstance(project, dict) or not str(project.get("id", "")).strip():
        raise ValueError("project.id must be a non-empty string")
    structure_payload = payload.get("structure")
    if not isinstance(structure_payload, dict) or structure_payload.get("type") != "shear_building":
        raise ValueError("version 0.6 supports structure.type='shear_building'")
    structure = Structure(
        structure_id=str(structure_payload.get("id") or project["id"]),
        name=str(structure_payload.get("name") or project.get("name") or ""),
        story_masses_kg=structure_payload.get("story_masses_kg", ()),
        story_stiffness_n_m=structure_payload.get("story_stiffness_n_m", ()),
        reference_frequencies_hz=structure_payload.get("reference_frequencies_hz", ()),
    )
    observation_payload = payload.get("observations")
    if not isinstance(observation_payload, dict):
        raise ValueError("observations must be a JSON object")
    file_value = str(observation_payload.get("file", "")).strip()
    if not file_value:
        raise ValueError("observations.file must be a non-empty path")
    source_path = (manifest_path.parent / file_value).resolve()
    if source_path.suffix.lower() != ".csv":
        raise ValueError("version 0.6 project manifests support CSV observations")
    try:
        sampling_hz = float(observation_payload["sampling_hz"])
    except (KeyError, TypeError, ValueError):
        raise ValueError("observations.sampling_hz must be a finite positive number") from None
    if not math.isfinite(sampling_hz) or sampling_hz <= 0.0:
        raise ValueError("observations.sampling_hz must be a finite positive number")
    channels_payload = observation_payload.get("channels")
    if not isinstance(channels_payload, list) or not channels_payload:
        raise ValueError("observations.channels must be a non-empty list")
    columns: list[str] = []
    channel_ids: list[str] = []
    units: list[str] = []
    for idx, channel in enumerate(channels_payload, start=1):
        if not isinstance(channel, dict):
            raise ValueError(f"observations.channels[{idx - 1}] must be an object")
        column = str(channel.get("column", "")).strip()
        channel_id = str(channel.get("id") or column).strip()
        unit = str(channel.get("unit", "unknown")).strip()
        if not column or not channel_id or not unit:
            raise ValueError(f"observations.channels[{idx - 1}] needs non-empty column, id, and unit")
        columns.append(column)
        channel_ids.append(channel_id)
        units.append(unit)
    if len(set(columns)) != len(columns) or len(set(channel_ids)) != len(channel_ids):
        raise ValueError("channel columns and ids must each be unique")

    analysis = payload.get("analysis", {})
    if not isinstance(analysis, dict):
        raise ValueError("analysis must be a JSON object")
    default_method = "peak_picking" if len(columns) == 1 else "fdd"
    method = str(analysis.get("method", default_method)).strip().lower()
    allowed_options = _SINGLE_OPTIONS if method == "peak_picking" else _FDD_OPTIONS
    if method not in {"peak_picking", "fdd"}:
        raise ValueError("analysis.method must be 'peak_picking' or 'fdd'")
    options = analysis.get("options", {})
    if not isinstance(options, dict):
        raise ValueError("analysis.options must be a JSON object")
    unknown = sorted(set(options) - allowed_options)
    if unknown:
        raise ValueError(f"unsupported analysis options for {method}: {unknown}")
    if method == "peak_picking" and len(columns) != 1:
        raise ValueError("peak_picking requires exactly one channel; use fdd for multiple channels")
    if method == "fdd" and len(columns) < 2:
        raise ValueError("fdd requires at least two channels")

    return ProjectManifest(
        manifest_path=manifest_path,
        schema_version=schema_version,
        project_id=str(project["id"]).strip(),
        project_name=str(project.get("name", "")).strip(),
        structure=structure,
        observations_path=source_path,
        sampling_hz=sampling_hz,
        columns=tuple(columns),
        channel_ids=tuple(channel_ids),
        units=tuple(units),
        method=method,
        options=dict(options),
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_project(path: str | Path) -> LoadedProject:
    """Validate a manifest, load its CSV channels, and capture input provenance."""
    manifest = read_manifest(path)
    if not manifest.observations_path.is_file():
        raise FileNotFoundError(f"observation CSV not found: {manifest.observations_path}")
    if len(manifest.columns) == 1:
        observations: SensorData | MultiChannelData = load_sensors(
            manifest.observations_path,
            sampling_hz=manifest.sampling_hz,
            column=manifest.columns[0],
            unit=manifest.units[0],
            channel=manifest.channel_ids[0],
        )
    else:
        observations = load_multichannel_csv(
            manifest.observations_path,
            columns=manifest.columns,
            sampling_hz=manifest.sampling_hz,
            units=manifest.units,
            channel_ids=manifest.channel_ids,
        )
    return LoadedProject(
        manifest=manifest,
        observations=observations,
        source_sha256=_sha256(manifest.observations_path),
        manifest_sha256=_sha256(manifest.manifest_path),
    )


def run_project(project: LoadedProject | str | Path) -> ProjectRunResult:
    """Execute one deterministic one-shot analysis described by a manifest."""
    loaded = load_project(project) if isinstance(project, (str, Path)) else project
    if not isinstance(loaded, LoadedProject):
        raise TypeError("project must be a manifest path or LoadedProject from tm.load_project()")
    manifest = loaded.manifest
    if manifest.method == "peak_picking":
        if not isinstance(loaded.observations, SensorData):
            raise TypeError("peak_picking manifest must load one SensorData channel")
        modal = identify(loaded.observations, **manifest.options)
    else:
        if not isinstance(loaded.observations, MultiChannelData):
            raise TypeError("fdd manifest must load multiple channels")
        modal = identify_fdd(loaded.observations, **manifest.options)

    structure = manifest.structure
    if modal.modes:
        structure = update(structure, modal)
    health = assess(structure=structure, observations=loaded.observations, modal_result=modal)
    return ProjectRunResult(
        project_id=manifest.project_id,
        project_name=manifest.project_name,
        manifest_path=str(manifest.manifest_path),
        source_path=str(manifest.observations_path),
        source_sha256=loaded.source_sha256,
        manifest_sha256=loaded.manifest_sha256,
        method=manifest.method,
        analysis_options=dict(manifest.options),
        structure=structure,
        modal=modal,
        health=health,
    )
