"""Minimal digital-twin asset and relation records."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class Asset:
    asset_id: str
    asset_type: str
    name: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        asset_id, asset_type = str(self.asset_id).strip(), str(self.asset_type).strip()
        if not asset_id or not asset_type:
            raise ValueError("asset_id and asset_type must be non-empty")
        if not isinstance(self.metadata, Mapping):
            raise ValueError("asset metadata must be a mapping")
        object.__setattr__(self, "asset_id", asset_id)
        object.__setattr__(self, "asset_type", asset_type)
        object.__setattr__(self, "name", str(self.name))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {"asset_id": self.asset_id, "asset_type": self.asset_type, "name": self.name, "metadata": dict(self.metadata)}


@dataclass(frozen=True)
class Relation:
    source_asset_id: str
    relation_type: str
    target_asset_id: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        source, kind, target = (str(item).strip() for item in (self.source_asset_id, self.relation_type, self.target_asset_id))
        if not source or not kind or not target:
            raise ValueError("relation source, type, and target must be non-empty")
        if source == target:
            raise ValueError("self-relations are not supported")
        if not isinstance(self.metadata, Mapping):
            raise ValueError("relation metadata must be a mapping")
        object.__setattr__(self, "source_asset_id", source)
        object.__setattr__(self, "relation_type", kind)
        object.__setattr__(self, "target_asset_id", target)
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_asset_id": self.source_asset_id,
            "relation_type": self.relation_type,
            "target_asset_id": self.target_asset_id,
            "metadata": dict(self.metadata),
        }
