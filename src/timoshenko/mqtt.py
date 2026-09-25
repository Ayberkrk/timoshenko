"""Optional MQTT source adapter using the Paho Python client API v2."""

from __future__ import annotations

from importlib import import_module
import json
import math
from queue import Full, Queue
import threading
from typing import Any, Callable

from .observations import Observation, ObservationBatch
from .plugins import PLUGIN_API_VERSION
from .session import SessionIngestResult


class _MqttEnvelope:
    __slots__ = ("batch", "message_id", "qos")

    def __init__(self, batch: ObservationBatch, message_id: int, qos: int):
        self.batch = batch
        self.message_id = int(message_id)
        self.qos = int(qos)


class MQTTSourceError(RuntimeError):
    """Raised for connection, payload, or bounded-queue failures."""


_STOP = object()


class MqttObservationSource:
    """Subscribe to a topic carrying version-1 Timoshenko JSON batch payloads.

    Paho is imported only when ``open()`` is called. A client factory can be
    injected for tests or an application-managed Paho configuration.
    """

    def __init__(
        self,
        *,
        host: str,
        topic: str,
        port: int = 1883,
        qos: int = 1,
        client_id: str = "",
        clean_session: bool = False,
        username: str | None = None,
        password: str | None = None,
        tls: bool = False,
        keepalive_s: int = 60,
        connect_timeout_s: float = 10.0,
        queue_capacity: int = 1024,
        max_payload_bytes: int = 1_048_576,
        allow_retained: bool = False,
        client_factory: Callable[[], Any] | None = None,
    ):
        host_value, topic_value = str(host).strip(), str(topic).strip()
        port_value, qos_value = int(port), int(qos)
        keepalive, capacity, payload_limit = int(keepalive_s), int(queue_capacity), int(max_payload_bytes)
        timeout = float(connect_timeout_s)
        if not host_value or not topic_value or "+" in topic_value or "#" in topic_value:
            raise ValueError("host and a concrete subscription topic are required; topic filters are not accepted")
        if not 1 <= port_value <= 65535 or qos_value not in {0, 1, 2}:
            raise ValueError("port must be in 1..65535 and qos must be 0, 1, or 2")
        if keepalive < 1 or capacity < 1 or payload_limit < 1:
            raise ValueError("keepalive_s, queue_capacity, and max_payload_bytes must be positive")
        if not math.isfinite(timeout) or timeout <= 0.0:
            raise ValueError("connect_timeout_s must be finite and positive")
        if not bool(clean_session) and not str(client_id).strip():
            raise ValueError("a stable client_id is required when clean_session=False")
        if password is not None and username is None:
            raise ValueError("username is required when password is supplied")
        self.host = host_value
        self.topic = topic_value
        self.port = port_value
        self.qos = qos_value
        self.client_id = str(client_id)
        self.clean_session = bool(clean_session)
        self.username = username
        self.password = password
        self.tls = bool(tls)
        self.keepalive_s = keepalive
        self.connect_timeout_s = timeout
        self.queue_capacity = capacity
        self.max_payload_bytes = payload_limit
        self.allow_retained = bool(allow_retained)
        self._client_factory = client_factory
        self._queue: Queue[_MqttEnvelope | object] = Queue(maxsize=capacity)
        self._client: Any = None
        self._connected = threading.Event()
        self._state_lock = threading.Lock()
        self._failure: BaseException | None = None
        self._opened = False
        self._network_started = False
        self._retained_drop_count = 0
        self._pending_acks: dict[str, list[_MqttEnvelope]] = {}

    @property
    def retained_drop_count(self) -> int:
        return self._retained_drop_count

    def open(self) -> None:
        if self._opened:
            raise RuntimeError("MQTT source is already open")
        if self._client_factory is None:
            try:
                mqtt = import_module("paho.mqtt.client")
            except ImportError as error:
                raise ImportError("MQTT support requires the optional dependency; install timoshenko-engine[mqtt]") from error
            client = mqtt.Client(
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                client_id=self.client_id,
                clean_session=self.clean_session,
                manual_ack=True,
            )
        else:
            client = self._client_factory()
        self._client = client
        self._failure = None
        self._queue = Queue(maxsize=self.queue_capacity)
        self._pending_acks.clear()
        self._connected.clear()
        self._retained_drop_count = 0
        client.on_connect = self._on_connect
        client.on_message = self._on_message
        if self.username is not None:
            client.username_pw_set(self.username, self.password)
        if self.tls:
            client.tls_set()
        try:
            result = client.connect(self.host, self.port, self.keepalive_s)
            if result not in (None, 0):
                raise MQTTSourceError(f"MQTT connect returned error code {result!r}")
            client.loop_start()
            self._network_started = True
            if not self._connected.wait(self.connect_timeout_s):
                raise TimeoutError(f"timed out waiting for MQTT subscription to {self.topic!r}")
            self._raise_failure()
            self._opened = True
        except BaseException:
            self.close()
            raise

    def _on_connect(self, client, userdata, flags, reason_code, properties=None) -> None:
        try:
            if int(reason_code) != 0:
                raise MQTTSourceError(f"MQTT broker rejected the connection: {reason_code}")
            result, _message_id = client.subscribe(self.topic, qos=self.qos)
            if result not in (None, 0):
                raise MQTTSourceError(f"MQTT subscribe returned error code {result!r}")
        except BaseException as error:
            self._set_failure(error)
        finally:
            self._connected.set()

    def _on_message(self, client, userdata, message) -> None:
        with self._state_lock:
            if self._failure is not None:
                return
        if bool(getattr(message, "retain", False)) and not self.allow_retained:
            self._retained_drop_count += 1
            if int(getattr(message, "qos", 0)) > 0:
                result_code = client.ack(message.mid, message.qos)
                if result_code not in (None, 0):
                    self._set_failure(MQTTSourceError(f"MQTT acknowledgement of retained message failed with code {result_code!r}"))
            return
        payload = message.payload
        if len(payload) > self.max_payload_bytes:
            self._set_failure(MQTTSourceError(f"MQTT payload exceeded {self.max_payload_bytes} bytes"))
            return
        try:
            decoded = json.loads(payload.decode("utf-8"))
            schema_version = decoded.get("schema_version") if isinstance(decoded, dict) else None
            valid_schema_version = (type(schema_version) is int and schema_version == 1) or schema_version == "1"
            if not isinstance(decoded, dict) or not valid_schema_version:
                raise ValueError("payload must be a JSON object with schema_version=1")
            source_id = decoded.get("source_id", "")
            batch_id = decoded.get("batch_id", "")
            observations = decoded.get("observations")
            if not isinstance(source_id, str) or not source_id.strip() or not isinstance(batch_id, str) or not batch_id.strip() or not isinstance(observations, list) or not observations:
                raise ValueError("source_id, batch_id, and a non-empty observations list are required")
            if len(observations) > 4096:
                raise ValueError("one MQTT batch may contain at most 4096 observations")
            if any(not isinstance(item, dict) or item.get("timestamp") is None for item in observations):
                raise ValueError("each MQTT observation must be an object with an event timestamp")
            batch = ObservationBatch(
                [Observation(**item) for item in observations],
                source_id=source_id.strip(),
                batch_id=batch_id.strip(),
            )
            self._queue.put_nowait(_MqttEnvelope(batch, message.mid, message.qos))
        except Full:
            self._set_failure(MQTTSourceError("MQTT receive queue is full; ingestion stopped to expose possible message loss"))
        except Exception as error:
            self._set_failure(MQTTSourceError(f"invalid MQTT observation payload: {error}"))

    def _set_failure(self, error: BaseException) -> None:
        with self._state_lock:
            if self._failure is None:
                self._failure = error
        try:
            self._queue.put_nowait(_STOP)
        except Full:
            pass

    def _raise_failure(self) -> None:
        with self._state_lock:
            error = self._failure
        if error is not None:
            raise MQTTSourceError(str(error)) from error

    def read_batch(self) -> ObservationBatch | None:
        if not self._opened:
            raise RuntimeError("MQTT source must be opened before reading")
        self._raise_failure()
        item = self._queue.get()
        if item is _STOP:
            self._raise_failure()
            return None
        assert isinstance(item, _MqttEnvelope)
        with self._state_lock:
            self._pending_acks.setdefault(item.batch.batch_id, []).append(item)
        return item.batch

    def acknowledge(self, batch: ObservationBatch, result: SessionIngestResult) -> None:
        """Acknowledge QoS 1/2 publications after session ingestion succeeds."""
        with self._state_lock:
            pending = list(self._pending_acks.get(batch.batch_id, ()))
        if not pending:
            raise MQTTSourceError(f"no pending MQTT delivery for batch {batch.batch_id!r}")
        client = self._client
        if client is None:
            raise MQTTSourceError("cannot acknowledge MQTT delivery after source close")
        for envelope in pending:
            if envelope.qos > 0:
                result_code = client.ack(envelope.message_id, envelope.qos)
                if result_code not in (None, 0):
                    raise MQTTSourceError(f"MQTT acknowledgement failed with code {result_code!r}")
        with self._state_lock:
            self._pending_acks.pop(batch.batch_id, None)

    def close(self) -> None:
        client, self._client = self._client, None
        self._opened = False
        self._connected.set()
        try:
            self._queue.put_nowait(_STOP)
        except Full:
            pass
        if client is None:
            return
        try:
            client.disconnect()
        finally:
            if self._network_started:
                self._network_started = False
                client.loop_stop()


class MqttPlugin:
    """Built-in optional-dependency plugin for ``PluginRegistry``."""

    name = "timoshenko-mqtt"
    api_version = PLUGIN_API_VERSION

    def register(self, registry) -> None:
        registry.register_source("mqtt", MqttObservationSource)


__all__ = ["MQTTSourceError", "MqttObservationSource", "MqttPlugin"]
