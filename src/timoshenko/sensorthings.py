"""Bounded HTTP pull adapter for scalar OGC SensorThings observations."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
import math
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from .observations import Observation, ObservationBatch
from .plugins import PLUGIN_API_VERSION


class SensorThingsSourceError(RuntimeError):
    """Raised for SensorThings transport, pagination, or mapping failures."""


def _origin(url: str) -> tuple[str, str, int | None]:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
        raise ValueError("SensorThings URLs must be absolute HTTP(S) URLs without embedded credentials or fragments")
    try:
        port = parsed.port
    except ValueError as error:
        raise ValueError("SensorThings URL contains an invalid port") from error
    return parsed.scheme.lower(), parsed.hostname.lower(), port


def _phenomenon_timestamp(value: Any) -> float:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("phenomenonTime must be a timezone-aware ISO-8601 instant")
    text = value.strip()
    if "/" in text:
        raise ValueError("interval phenomenonTime values are not supported; provide instant observations")
    iso_text = text[:-1] + "+00:00" if text.endswith(("Z", "z")) else text
    parsed = datetime.fromisoformat(iso_text)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("phenomenonTime must include a timezone")
    return parsed.timestamp()


class SensorThingsObservationSource:
    """Read one configured SensorThings Datastream Observations collection.

    Supply the collection URL, a stable sensor identifier, and a unit because
    this adapter does not perform Datastream metadata discovery. It follows
    server-provided ``@iot.nextLink`` URLs as opaque pagination cursors and
    emits one bounded batch per response page. Only scalar numeric ``result``
    values and instant ``phenomenonTime`` values are mapped. Quality defaults
    to false unless the caller explicitly opts into another default or maps a
    boolean property from SensorThings ``parameters``.
    """

    def __init__(
        self,
        observations_url: str,
        *,
        sensor_id: str,
        unit: str,
        name: str | None = None,
        source_id: str | None = None,
        bearer_token: str | None = None,
        quality_parameter: str | None = None,
        default_quality: bool = False,
        timeout_s: float = 15.0,
        max_response_bytes: int = 4_194_304,
        max_observations_per_page: int = 4096,
        fetcher: Callable[[Request, float, int], bytes] | None = None,
    ):
        url = str(observations_url).strip()
        if not url:
            raise ValueError("observations_url must be non-empty")
        origin = _origin(url)
        sensor_value, unit_value = str(sensor_id).strip(), str(unit).strip()
        if not sensor_value or not unit_value:
            raise ValueError("sensor_id and unit must be non-empty")
        timeout = float(timeout_s)
        byte_limit, observation_limit = int(max_response_bytes), int(max_observations_per_page)
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout_s must be finite and positive")
        if isinstance(max_response_bytes, bool) or byte_limit != max_response_bytes or not 1 <= byte_limit <= 67_108_864:
            raise ValueError("max_response_bytes must be an integer between 1 and 67108864")
        if isinstance(max_observations_per_page, bool) or observation_limit != max_observations_per_page or not 1 <= observation_limit <= 65_536:
            raise ValueError("max_observations_per_page must be an integer between 1 and 65536")
        token = None if bearer_token is None else str(bearer_token).strip()
        if token == "":
            raise ValueError("bearer_token must be non-empty or None")
        if type(default_quality) is not bool:
            raise ValueError("default_quality must be a bool")
        quality_key = None if quality_parameter is None else str(quality_parameter).strip()
        if quality_key == "":
            raise ValueError("quality_parameter must be non-empty or None")
        self.observations_url = url
        self.sensor_id = sensor_value
        self.name = sensor_value if name is None else str(name).strip()
        if not self.name:
            raise ValueError("name must be non-empty")
        self.unit = unit_value
        self.source_id = str(source_id).strip() if source_id is not None else f"sensorthings:{sensor_value}"
        if not self.source_id:
            raise ValueError("source_id must be non-empty")
        self.bearer_token = token
        self.quality_parameter = quality_key
        self.default_quality = default_quality
        self.timeout_s = timeout
        self.max_response_bytes = byte_limit
        self.max_observations_per_page = observation_limit
        self._origin = origin
        self._fetcher = fetcher
        self._next_url: str | None = None
        self._opened = False

    def open(self) -> None:
        if self._opened:
            raise RuntimeError("SensorThings observation source is already open")
        self._next_url = self.observations_url
        self._opened = True

    def read_batch(self) -> ObservationBatch | None:
        if not self._opened:
            raise RuntimeError("open() must be called before read_batch()")
        if self._next_url is None:
            return None
        page_url, self._next_url = self._next_url, None
        try:
            payload = self._fetch_page(page_url)
            document = json.loads(payload.decode("utf-8"))
            if not isinstance(document, dict) or not isinstance(document.get("value"), list):
                raise ValueError("response must be a JSON object with a 'value' array")
            items = document["value"]
            if len(items) > self.max_observations_per_page:
                raise ValueError(f"response has more than {self.max_observations_per_page} observations")
            next_link = document.get("@iot.nextLink")
            if next_link is not None:
                if not isinstance(next_link, str) or not next_link.strip():
                    raise ValueError("@iot.nextLink must be a non-empty URL string")
                next_link = next_link.strip()
                if _origin(next_link) != self._origin:
                    raise ValueError("@iot.nextLink must remain on the configured service origin")
            observations = [self._observation(item, index) for index, item in enumerate(items)]
            self._next_url = next_link
            batch_material = [item.get("@iot.id") for item in items]
            if any(item_id is None for item_id in batch_material):
                batch_material = items
            digest = hashlib.sha256(
                json.dumps(batch_material, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
            ).hexdigest()
            return ObservationBatch(
                observations,
                source_id=self.source_id,
                batch_id=f"{self.source_id}:page:{digest}",
            )
        except SensorThingsSourceError:
            raise
        except (ValueError, TypeError, KeyError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise SensorThingsSourceError(f"invalid SensorThings observation page: {error}") from error

    def _fetch_page(self, url: str) -> bytes:
        headers = {"Accept": "application/json"}
        if self.bearer_token is not None:
            headers["Authorization"] = f"Bearer {self.bearer_token}"
        request = Request(url, headers=headers, method="GET")
        try:
            if self._fetcher is not None:
                payload = self._fetcher(request, self.timeout_s, self.max_response_bytes)
            else:
                with urlopen(request, timeout=self.timeout_s) as response:
                    status = getattr(response, "status", 200)
                    if not 200 <= int(status) < 300:
                        raise SensorThingsSourceError(f"SensorThings server returned HTTP {status}")
                    payload = response.read(self.max_response_bytes + 1)
        except SensorThingsSourceError:
            raise
        except (HTTPError, URLError, TimeoutError, OSError) as error:
            raise SensorThingsSourceError(f"SensorThings request failed: {error}") from error
        if not isinstance(payload, bytes):
            raise SensorThingsSourceError("SensorThings fetcher must return response bytes")
        if len(payload) > self.max_response_bytes:
            raise SensorThingsSourceError(f"SensorThings response exceeded {self.max_response_bytes} bytes")
        return payload

    def _observation(self, item: Any, index: int) -> Observation:
        if not isinstance(item, dict):
            raise ValueError(f"value[{index}] must be an Observation JSON object")
        result = item.get("result")
        if isinstance(result, bool) or not isinstance(result, (int, float)):
            raise ValueError(f"value[{index}].result must be a scalar number")
        timestamp = _phenomenon_timestamp(item.get("phenomenonTime"))
        observation_id = item.get("@iot.id")
        metadata = {} if observation_id is None else {"sensorthings_observation_id": observation_id}
        quality = self.default_quality
        if self.quality_parameter is not None:
            parameters = item.get("parameters")
            if parameters is not None and not isinstance(parameters, dict):
                raise ValueError(f"value[{index}].parameters must be an object")
            if isinstance(parameters, dict) and self.quality_parameter in parameters:
                parameter_value = parameters[self.quality_parameter]
                if type(parameter_value) is not bool:
                    raise ValueError(f"value[{index}].parameters[{self.quality_parameter!r}] must be boolean")
                quality = parameter_value
        return Observation(
            sensor_id=self.sensor_id,
            name=self.name,
            unit=self.unit,
            value=float(result),
            timestamp=timestamp,
            quality=quality,
            source_id=self.source_id,
            metadata=metadata,
        )

    def close(self) -> None:
        self._opened = False
        self._next_url = None


class SensorThingsPlugin:
    """Built-in source plugin for ``PluginRegistry``."""

    name = "timoshenko-sensorthings"
    api_version = PLUGIN_API_VERSION

    def register(self, registry) -> None:
        registry.register_source("sensorthings", SensorThingsObservationSource)


__all__ = ["SensorThingsObservationSource", "SensorThingsPlugin", "SensorThingsSourceError"]
