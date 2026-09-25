"""Lifecycle contracts for caller-provided observation sources."""

from __future__ import annotations

from typing import Iterator, Protocol, runtime_checkable

from .observations import ObservationBatch
from .session import MonitoringSession, SessionIngestResult


@runtime_checkable
class ObservationSource(Protocol):
    """Synchronous pull-source contract for gateways and replay adapters.

    ``open`` acquires the source, ``read_batch`` returns the next arrival-order
    batch (or ``None`` at end of stream), and ``close`` releases resources.
    Implementations own protocol timeouts, reconnect rules, and authentication.
    """

    def open(self) -> None: ...

    def read_batch(self) -> ObservationBatch | None: ...

    def close(self) -> None: ...


@runtime_checkable
class AcknowledgingObservationSource(ObservationSource, Protocol):
    """Optional extension for sources that acknowledge only after ingestion."""

    def acknowledge(self, batch: ObservationBatch, result: SessionIngestResult) -> None: ...


class SessionRunner:
    """Drive one monitoring session from a source with explicit cleanup.

    Use as a context manager so early loop exit and exceptions still close the
    source. The runner does not retry reads or hide source errors.
    """

    def __init__(
        self,
        source: ObservationSource,
        session: MonitoringSession,
        *,
        max_batches: int | None = None,
    ):
        if not isinstance(session, MonitoringSession):
            raise TypeError("session must be a MonitoringSession")
        if any(not callable(getattr(source, name, None)) for name in ("open", "read_batch", "close")):
            raise TypeError("source must provide callable open(), read_batch(), and close() methods")
        if max_batches is not None and (isinstance(max_batches, bool) or int(max_batches) != max_batches or int(max_batches) < 1):
            raise ValueError("max_batches must be a positive integer or None")
        self.source = source
        self.session = session
        self.max_batches = None if max_batches is None else int(max_batches)
        self._active = False
        self._consuming = False

    def __enter__(self) -> "SessionRunner":
        if self._active:
            raise RuntimeError("SessionRunner is already active")
        try:
            self.source.open()
        except BaseException as open_error:
            try:
                self.source.close()
            except BaseException as close_error:
                if hasattr(open_error, "add_note"):
                    open_error.add_note(f"Source cleanup after open failure also failed: {close_error!r}")
            raise
        self._active = True
        self._consuming = False
        return self

    def __exit__(self, exc_type, exc, traceback) -> bool:
        self._active = False
        try:
            self.source.close()
        except BaseException as close_error:
            if exc is None:
                raise
            if hasattr(exc, "add_note"):
                exc.add_note(f"Closing the observation source also failed: {close_error!r}")
        return False

    def __iter__(self) -> Iterator[SessionIngestResult]:
        if not self._active:
            raise RuntimeError("use SessionRunner inside a 'with' block")
        if self._consuming:
            raise RuntimeError("SessionRunner supports one active iteration at a time")
        self._consuming = True
        try:
            read_count = 0
            while self.max_batches is None or read_count < self.max_batches:
                batch = self.source.read_batch()
                if batch is None:
                    return
                if not isinstance(batch, ObservationBatch):
                    raise TypeError("ObservationSource.read_batch() must return ObservationBatch or None")
                read_count += 1
                result = self.session.ingest(batch)
                acknowledge = getattr(self.source, "acknowledge", None)
                if callable(acknowledge):
                    acknowledge(batch, result)
                yield result
        finally:
            self._consuming = False


__all__ = ["AcknowledgingObservationSource", "ObservationSource", "SessionRunner"]
