"""SQLite-backed persistence for the API (BFF) layer -- stdlib ``sqlite3`` only.

Why this module exists
-----------------------
``api/repositories.py`` used to hold brand profiles, connections, campaigns, approvals,
the audit log, and (via ``campaia_core.infra.IdempotencyStore``) idempotency records purely
as plain Python objects in ``dict``/``list`` attributes -- a process restart lost everything.
This module adds an optional SQLite file behind those same repository classes, without
changing a single method signature they expose to ``api/routes_*.py``: when a repository is
constructed with a ``RecordTable`` (see ``Database.table`` below) it persists every mutation
immediately; when it is not (the default), it behaves exactly as before -- plain in-memory
Python objects, nothing touches disk. See ``api/state.py`` for how ``AppState.db_path``
selects between the two.

``campaia_core`` is never imported *for modification* here and never subclassed at the
module level -- this file only reads its dataclasses/enums (to encode them) and reconstructs
them (by calling their own constructors), so the domain layer stays exactly as pure and
I/O-free as it was before this module existed.

Storage shape
-------------
No normalized relational schema: each repository gets one SQLite table
``(id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, data TEXT NOT NULL)`` and every record is a
single JSON blob in ``data`` (row-per-record). This is enough because nothing in this layer
needs to query by anything other than "by id" or "by tenant", both of which are plain indexed
column lookups -- see ``RecordTable``. Every write goes through ``RecordTable.put``, which
executes and commits in the same call: there is no batching, no deferred flush, and no
in-memory-only mutation that could be lost if the process crashed the instant after a route
handler returned 200/201/202.

Serialization approach (the ``encode``/``decode`` pair below)
---------------------------------------------------------------
The codec is self-describing: every value that is not already a JSON-native primitive
(``str``/``int``/``float``/``bool``/``None``) is wrapped in a small ``{"__type__": ..., ...}``
envelope on the way out, so decoding never has to *guess* what a value is or consult a target
schema. This matters because not every value that needs to round-trip is one of the five
record dataclasses: the idempotency store's stored results, in particular, can be arbitrary
domain objects (``PublicationSaga.run()`` returns a ``SagaOutcome`` nesting ``SagaStep``
dataclasses and several ``StrEnum`` types), and the encoder handles those the exact same way
it handles a ``BrandProfile``.

  Decimal          -> {"__type__": "decimal", "v": "<str(value)>"}
                      Money fields are always ``Decimal`` in this codebase and never touch a
                      ``float``. ``str(Decimal("12.50"))`` is exact and ``Decimal(that_string)``
                      reconstructs the identical value -- this is the one rule that must never
                      be relaxed, since a float round-trip would silently corrupt amounts.
  datetime         -> {"__type__": "datetime", "v": "<isoformat>"}
                      Every datetime in this codebase is built via
                      ``datetime.now(timezone.utc)`` (always timezone-aware, always UTC).
                      ``isoformat()`` keeps the ``+00:00`` offset and ``fromisoformat()``
                      reads it back exactly, so a value can never come back naive or shifted.
  Enum             -> {"__type__": "enum", "mod": "<module>", "qual": "<qualname>",
  (covers plain               "v": <member.value>}
  ``(str, Enum)``  On decode the class is imported by dotted module + qualname and
  subclasses,      reconstructed via ``EnumClass(v)`` -- precisely how e.g.
  ``StrEnum``,     ``CampaignState("DRAFT")`` already works everywhere else in this codebase.
  ``IntEnum``)
  frozenset        -> {"__type__": "frozenset", "v": [...]}
  set              -> {"__type__": "set", "v": [...]}
  tuple            -> {"__type__": "tuple", "v": [...]}
                      JSON has no tuple/set/frozenset type and a plain Python ``list`` is used
                      untagged for genuine ``list[...]`` fields, so these tags are what let
                      e.g. ``planned_channels: tuple[str, ...]`` come back as a tuple and not
                      quietly turn into a list (which would break the frozen dataclasses that
                      hash/compare on it) or vice versa for ``decided_by: set[str]``.
  dataclass        -> {"__type__": "dataclass", "mod": "<module>", "qual": "<qualname>",
  instance                     "fields": {<name>: <encoded field>, ...}}
                      Reconstructed by importing the class and calling ``cls(**fields)``.
                      Works uniformly for frozen and non-frozen dataclasses; every dataclass
                      actually persisted here (``BrandProfile``, ``Connection``,
                      ``CampaignRecord``, the domain's ``Campaign``/``BudgetEngine``/
                      ``BudgetLimits``/``Reservation``/``AutonomySettings``/``PolicyDecision``/
                      ``Finding``, ``ApprovalRequest``, ``AuditEvent``, and the saga's
                      ``SagaOutcome``/``SagaStep``) accepts all of its fields as keyword
                      arguments, so no special-casing per class is needed.
  dict             -> recursed into as a plain JSON object (values encoded, keys passed
                      through as-is). Every dict actually stored here already has ``str``
                      keys (tenant ids, campaign ids, channel names, ...), so this never needs
                      the ``__type__`` envelope -- a dict is simply the absence of one on a
                      JSON object. (A dict is never itself tagged, so a domain value must never
                      legitimately contain a key literally named ``"__type__"``; none of the
                      dataclasses persisted here do.)
  list             -> a plain JSON array, elements encoded recursively, untagged.

Mutation tracking for records that are mutated *in place* after ``get()``
--------------------------------------------------------------------------
Route handlers (deliberately left unmodified -- see the module docstrings of
``routes_approvals.py`` and ``routes_campaigns.py``) mutate ``ApprovalRequest`` and
``CampaignRecord`` objects directly by attribute assignment (``approval.status = "APPROVED"``,
``approval.decided_by.add(user_id)``) and, several calls deep inside ``campaia_core``, mutate
the nested ``Campaign`` (``campaign.state = ...``, ``campaign.history.append(...)``) and
``BudgetEngine`` (``spent_total +=``, ``self._reservations[id] = ...``) objects the same way.
There is no explicit "save this record" call anywhere for the repository to hook into.

``wrap_for_notify`` below solves this generically instead of chasing every call site: given a
record, it recursively walks every *mutable* field (non-frozen dataclasses, ``list``,
``dict``, ``set`` -- frozen dataclasses, ``tuple`` and ``frozenset`` are immutable and can only
be *replaced* wholesale by a parent's own wrapped ``__setattr__``, so they are left alone) and
swaps each mutable object's class for a dynamically generated subclass (or, for containers,
a purpose-built subclass) whose mutating methods call back into a single shared ``on_change``
closure after performing the mutation. Every node in one record's object graph shares the same
closure, which re-serializes and commits *that whole top-level record* to its row. A single
logical mutation such as ``Campaign.transition_to`` (which sets ``self.state`` and then appends
to ``self.history`` as two separate statements) triggers two writes instead of one, but because
Python is single-threaded here and route handlers run to completion synchronously, the *last*
write before the HTTP response is always the fully-consistent one -- the small amount of
redundant I/O is the price paid for never adding a "does this call site need a manual save()"
audit to every future change in ``campaia_core`` or ``routes_*.py``.

This wrapping is applied only when a repository is constructed with a real ``RecordTable``
(i.e. persistent mode). In the default, ephemeral/in-memory mode used by every pre-existing
test, ``wrap_for_notify`` is never called at all, so those tests run against the exact same
plain ``dataclass`` instances as before this module existed.
"""

from __future__ import annotations

import dataclasses
import enum
from contextlib import contextmanager
import importlib
import json
import sqlite3
import threading
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Callable


# --------------------------------------------------------------------------------- encode/decode

# Optional billing observations live outside constructor fields. The previous decoder
# ignores extra envelope keys, so rollback readers still reconstruct the original
# financial records. Only these explicit non-authoritative fields use this extension.
_BILLING_OBSERVATION_FIELDS = {
    ("campaia_core.subscription", "SubscriptionCharge"): frozenset({
        "created_at", "gateway_status", "gateway_provider", "gateway_mode",
        "status_observed_at", "status_source", "invoice_url",
    }),
    ("campaia_core.payment_gateway", "ChargeResult"): frozenset({"invoice_url"}),
}


# New authoritative commercial terms are isolated from legacy constructor fields.
# Old binaries can decode the envelope but MUST NOT write V1 contracts on rollback.
# Disable billing/AI mutation and drain workers before any old-code rollback.
_COMMERCIAL_FIELDS = {
    ("campaia_core.subscription", "PlanDefinition"): frozenset({"credit_policy"}),
    ("campaia_core.subscription", "Subscription"): frozenset({"paid_cycle_schedule", "extra_credit_consent"}),
    ("campaia_core.subscription", "SubscriptionCharge"): frozenset({
        "commercial_cycle_index", "commercial_lifecycle_id",
    }),
}


def _original_class(obj: Any) -> type:
    return getattr(type(obj), "_notify_orig", type(obj))


def encode(value: Any) -> Any:
    # NOTE: Enum must be checked before the plain-primitive shortcut below, because a
    # `class Foo(str, Enum)` (or IntEnum) member genuinely *is* an instance of `str` (or
    # `int`) via the mixin -- checking primitives first would silently encode e.g.
    # CampaignState.DRAFT as the bare string "DRAFT" with no way to tell it apart on decode
    # from a real plain string field, and reconstructing it as `str` instead of
    # `CampaignState` breaks every `.value`/identity comparison call site downstream.
    if isinstance(value, enum.Enum):
        cls = type(value)
        return {"__type__": "enum", "mod": cls.__module__, "qual": cls.__qualname__, "v": value.value}
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Decimal):
        return {"__type__": "decimal", "v": str(value)}
    if isinstance(value, datetime):
        return {"__type__": "datetime", "v": value.isoformat()}
    if isinstance(value, frozenset):
        return {"__type__": "frozenset", "v": [encode(x) for x in value]}
    if isinstance(value, set):
        return {"__type__": "set", "v": [encode(x) for x in value]}
    if isinstance(value, tuple):
        return {"__type__": "tuple", "v": [encode(x) for x in value]}
    if isinstance(value, dict):
        return {k: encode(v) for k, v in value.items()}
    if isinstance(value, list):
        return [encode(x) for x in value]
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        cls = _original_class(value)
        fields = {f.name: encode(getattr(value, f.name)) for f in dataclasses.fields(value)}
        extension_keys = _BILLING_OBSERVATION_FIELDS.get((cls.__module__, cls.__qualname__), ())
        extensions = {key: fields.pop(key) for key in extension_keys if key in fields}
        commercial_keys = _COMMERCIAL_FIELDS.get((cls.__module__, cls.__qualname__), ())
        commercial = {key: fields.pop(key) for key in commercial_keys if key in fields}
        envelope = {"__type__": "dataclass", "mod": cls.__module__, "qual": cls.__qualname__, "fields": fields}
        if extensions:
            envelope["billing_observations"] = extensions
        if any(value is not None for value in commercial.values()):
            envelope["commercial_v1"] = commercial
        return envelope
    raise TypeError(f"api.db.encode: no encoding rule for {type(value)!r} (value={value!r})")


def _import_path(mod_name: str, qualname: str) -> Any:
    mod = importlib.import_module(mod_name)
    obj: Any = mod
    for part in qualname.split("."):
        obj = getattr(obj, part)
    return obj


def decode(value: Any) -> Any:
    if isinstance(value, dict):
        tag = value.get("__type__")
        if tag == "decimal":
            return Decimal(value["v"])
        if tag == "datetime":
            return datetime.fromisoformat(value["v"])
        if tag == "enum":
            cls = _import_path(value["mod"], value["qual"])
            return cls(value["v"])
        if tag == "frozenset":
            return frozenset(decode(x) for x in value["v"])
        if tag == "set":
            return set(decode(x) for x in value["v"])
        if tag == "tuple":
            return tuple(decode(x) for x in value["v"])
        if tag == "dataclass":
            cls = _import_path(value["mod"], value["qual"])
            fields = {k: decode(v) for k, v in value["fields"].items()}
            extensions = value.get("billing_observations", {})
            allowed = _BILLING_OBSERVATION_FIELDS.get((value["mod"], value["qual"]), ())
            if not isinstance(extensions, dict) or not set(extensions).issubset(allowed):
                raise ValueError("Unsupported billing observation fields.")
            if set(extensions).intersection(fields):
                raise ValueError("Duplicate billing observation fields.")
            fields.update({k: decode(v) for k, v in extensions.items()})
            commercial = value.get("commercial_v1", {})
            allowed_commercial = _COMMERCIAL_FIELDS.get((value["mod"], value["qual"]), ())
            if (not isinstance(commercial, dict)
                    or not set(commercial).issubset(allowed_commercial)
                    or set(commercial).intersection(fields)):
                raise ValueError("Unsupported or duplicate commercial terms.")
            fields.update({k: decode(v) for k, v in commercial.items()})
            return cls(**fields)
        return {k: decode(v) for k, v in value.items()}
    if isinstance(value, list):
        return [decode(x) for x in value]
    return value


# --------------------------------------------------------------------------------- notify wrapping


_notify_class_cache: dict[type, type] = {}


def _notify_class_for(cls: type) -> type:
    existing = _notify_class_cache.get(cls)
    if existing is not None:
        return existing

    def __setattr__(self: Any, name: str, value: Any) -> None:
        object.__setattr__(self, name, value)
        if name == "_on_change":
            return
        cb = self.__dict__.get("_on_change")
        if cb is not None:
            cb()

    notify_cls = type(f"_Notify{cls.__name__}", (cls,), {"__setattr__": __setattr__, "_notify_orig": cls})
    _notify_class_cache[cls] = notify_cls
    return notify_cls


class _NotifyList(list):
    def __init__(self, items, on_change: Callable[[], None]) -> None:
        super().__init__(items)
        self._on_change = on_change

    def append(self, item) -> None:
        super().append(item)
        self._on_change()

    def extend(self, items) -> None:
        super().extend(items)
        self._on_change()

    def insert(self, index, item) -> None:
        super().insert(index, item)
        self._on_change()

    def pop(self, *args):
        value = super().pop(*args)
        self._on_change()
        return value

    def remove(self, item) -> None:
        super().remove(item)
        self._on_change()

    def clear(self) -> None:
        super().clear()
        self._on_change()

    def __setitem__(self, key, value) -> None:
        super().__setitem__(key, value)
        self._on_change()

    def __delitem__(self, key) -> None:
        super().__delitem__(key)
        self._on_change()

    def __iadd__(self, other):
        result = super().__iadd__(other)
        self._on_change()
        return result


class _NotifyDict(dict):
    def __init__(self, items, on_change: Callable[[], None]) -> None:
        super().__init__(items)
        self._on_change = on_change

    def __setitem__(self, key, value) -> None:
        super().__setitem__(key, value)
        self._on_change()

    def __delitem__(self, key) -> None:
        super().__delitem__(key)
        self._on_change()

    def update(self, *args, **kwargs) -> None:
        super().update(*args, **kwargs)
        self._on_change()

    def pop(self, *args):
        value = super().pop(*args)
        self._on_change()
        return value

    def clear(self) -> None:
        super().clear()
        self._on_change()

    def setdefault(self, key, default=None):
        had = key in self
        value = super().setdefault(key, default)
        if not had:
            self._on_change()
        return value


class _NotifySet(set):
    def __init__(self, items, on_change: Callable[[], None]) -> None:
        super().__init__(items)
        self._on_change = on_change

    def add(self, item) -> None:
        super().add(item)
        self._on_change()

    def discard(self, item) -> None:
        super().discard(item)
        self._on_change()

    def remove(self, item) -> None:
        super().remove(item)
        self._on_change()

    def update(self, *args) -> None:
        super().update(*args)
        self._on_change()

    def clear(self) -> None:
        super().clear()
        self._on_change()


def wrap_for_notify(obj: Any, on_change: Callable[[], None]) -> Any:
    """Recursively wrap obj's mutable tree so any in-place mutation persists immediately.

    Dataclass instances keep their identity (their ``__class__`` is swapped in place).
    ``list``/``dict``/``set`` fields are replaced with notifying subclass instances holding
    the same (already-wrapped) elements. Frozen dataclasses, ``tuple`` and ``frozenset`` are
    immutable and are returned unchanged.
    """
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        params = getattr(obj, "__dataclass_params__", None)
        if params is not None and params.frozen:
            return obj
        for f in dataclasses.fields(obj):
            current = obj.__dict__.get(f.name)
            wrapped = wrap_for_notify(current, on_change)
            if wrapped is not current:
                object.__setattr__(obj, f.name, wrapped)
        notify_cls = _notify_class_for(type(obj))
        obj.__class__ = notify_cls
        object.__setattr__(obj, "_on_change", on_change)
        return obj
    if isinstance(obj, list):
        return _NotifyList([wrap_for_notify(x, on_change) for x in obj], on_change)
    if isinstance(obj, dict):
        return _NotifyDict({k: wrap_for_notify(v, on_change) for k, v in obj.items()}, on_change)
    if isinstance(obj, set) and not isinstance(obj, frozenset):
        return _NotifySet(obj, on_change)
    return obj


# --------------------------------------------------------------------------------- sqlite plumbing


class RecordTable:
    """Generic tenant-scoped record table used by the current runtime.

    F3 adds a real transaction boundary: writes commit immediately only when no outer
    transaction is active. PersistentIdempotencyStore opens an outer transaction around
    reservation + domain mutation + audit + result storage, so a failure rolls the entire
    unit back instead of leaving half-applied rows.
    """

    def __init__(self, database: "Database", name: str) -> None:
        self._database = database
        self._conn = database._conn
        self._lock = database._lock
        self._name = name
        with self._lock:
            self._conn.execute(
                f'CREATE TABLE IF NOT EXISTS "{name}" ('
                "id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, data TEXT NOT NULL)"
            )
            self._conn.execute(
                f'CREATE INDEX IF NOT EXISTS "{name}_tenant_idx" ON "{name}" (tenant_id)'
            )
            if not self._database.in_transaction:
                self._conn.commit()

    def transaction(self):
        return self._database.transaction()

    def lock_key(self, key: str) -> None:
        self._database.lock_key(key)

    def put(self, id_: str, tenant_id: str, obj: Any) -> None:
        if not tenant_id:
            raise ValueError("tenant_id is required for persisted runtime rows")
        payload = json.dumps(encode(obj))
        with self._lock:
            updated = self._conn.execute(
                f'UPDATE "{self._name}" SET data = ? WHERE id = ? AND tenant_id = ?',
                (payload, id_, tenant_id),
            )
            if updated.rowcount == 0:
                inserted = self._conn.execute(
                    f'INSERT OR IGNORE INTO "{self._name}" (id, tenant_id, data) '
                    "VALUES (?, ?, ?)",
                    (id_, tenant_id, payload),
                )
                if inserted.rowcount == 0:
                    updated = self._conn.execute(
                        f'UPDATE "{self._name}" SET data = ? '
                        "WHERE id = ? AND tenant_id = ?",
                        (payload, id_, tenant_id),
                    )
                    if updated.rowcount == 0:
                        from campaia_core.errors import TenantIsolationViolation

                        raise TenantIsolationViolation(
                            "Registro persistido pertence a outro tenant."
                        )
            if not self._database.in_transaction:
                self._conn.commit()

    def delete(self, id_: str) -> None:
        with self._lock:
            self._conn.execute(f'DELETE FROM "{self._name}" WHERE id = ?', (id_,))
            if not self._database.in_transaction:
                self._conn.commit()

    def get(self, id_: str) -> Any | None:
        with self._lock:
            row = self._conn.execute(
                f'SELECT data FROM "{self._name}" WHERE id = ?', (id_,)
            ).fetchone()
        if row is None:
            return None
        return decode(json.loads(row[0]))

    def get_for_tenant(self, id_: str, tenant_id: str) -> Any | None:
        with self._lock:
            row = self._conn.execute(
                f'SELECT data FROM "{self._name}" '
                "WHERE id = ? AND tenant_id = ?",
                (id_, tenant_id),
            ).fetchone()
        if row is None:
            return None
        return decode(json.loads(row[0]))

    def delete_for_tenant(self, id_: str, tenant_id: str) -> bool:
        with self._lock:
            cursor = self._conn.execute(
                f'DELETE FROM "{self._name}" WHERE id = ? AND tenant_id = ?',
                (id_, tenant_id),
            )
            if not self._database.in_transaction:
                self._conn.commit()
        return cursor.rowcount > 0

    def rows_for_tenant(self, tenant_id: str) -> list[tuple[str, str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                f'SELECT id, tenant_id, data FROM "{self._name}" '
                "WHERE tenant_id = ? ORDER BY rowid",
                (tenant_id,),
            ).fetchall()
        return [(r[0], r[1], decode(json.loads(r[2]))) for r in rows]

    def all_rows(self) -> list[tuple[str, str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                f'SELECT id, tenant_id, data FROM "{self._name}" ORDER BY rowid'
            ).fetchall()
        return [(r[0], r[1], decode(json.loads(r[2]))) for r in rows]


class Database:
    """SQLite compatibility runtime with an explicit transactional unit-of-work.

    SQLite remains a development/test compatibility backend. F3's production adapter is
    PostgreSQL, but keeping identical transaction semantics here lets the full application
    suite prove rollback/replay behavior without weakening the existing fast test path.
    """

    def __init__(self, path: str) -> None:
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._lock = threading.RLock()
        self._local = threading.local()

    @property
    def in_transaction(self) -> bool:
        return getattr(self._local, "transaction_depth", 0) > 0

    @contextmanager
    def transaction(self):
        """Serialize an outer unit and commit/rollback atomically.

        Nested calls share the same DB transaction. BEGIN IMMEDIATE prevents two SQLite
        writers from both passing a get-before-put idempotency check concurrently.
        """
        with self._lock:
            depth = getattr(self._local, "transaction_depth", 0)
            outer = depth == 0
            if outer:
                self._conn.execute("BEGIN IMMEDIATE")
            self._local.transaction_depth = depth + 1
            try:
                yield
            except Exception:
                if outer:
                    self._conn.rollback()
                raise
            else:
                if outer:
                    self._conn.commit()
            finally:
                self._local.transaction_depth = depth

    def lock_key(self, key: str) -> None:
        # BEGIN IMMEDIATE and the process-wide RLock already serialize SQLite writers.
        if not self.in_transaction:
            raise RuntimeError("lock_key requires an active SQLite transaction")

    def table(self, name: str) -> RecordTable:
        table = RecordTable(self, name)
        if name == "credit_journal":
            with self._lock:
                for operation in ("UPDATE", "DELETE"):
                    self._conn.execute(
                        f'CREATE TRIGGER IF NOT EXISTS credit_journal_no_{operation.lower()} '
                        f'BEFORE {operation} ON credit_journal BEGIN '
                        "SELECT RAISE(ABORT, 'credit_journal is append-only'); END"
                    )
                if not self.in_transaction:
                    self._conn.commit()
        return table

    def ping(self) -> bool:
        try:
            with self._lock:
                self._conn.execute("SELECT 1").fetchone()
            return True
        except Exception:
            return False

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass

    def __del__(self) -> None:  # pragma: no cover
        self.close()


class PersistentTenantAutonomy:
    """Live tenant-keyed persistent mapping.

    F3 removes the process-local preload cache. Each get observes the backing store, which
    is required when two replicas share one database. A legacy "all" blob is still read as
    fallback so development SQLite files created by the previous runtime remain readable.
    """

    def __init__(self, table: RecordTable) -> None:
        self._table = table

    def get(self, key: str, default=None):
        row = self._table.get_for_tenant(key, key)
        if row is not None:
            return row
        legacy = self._table.get("all")
        if isinstance(legacy, dict):
            return legacy.get(key, default)
        return default

    def __getitem__(self, key: str):
        value = self.get(key)
        if value is None:
            raise KeyError(key)
        return value

    def __setitem__(self, key: str, value) -> None:
        self._table.put(key, key, value)

    def __contains__(self, key: str) -> bool:
        sentinel = object()
        return self.get(key, sentinel) is not sentinel


class PersistentTenantObjectMap:
    """Live persistent mapping for tenant-owned domain records keyed by arbitrary ids.

    Billing uses tenant ids as subscription keys and gateway payment ids as charge keys.
    The value itself is the authority for tenant ownership; every write requires a non-empty
    `tenant_id` attribute and RecordTable enforces that an existing id cannot be silently
    reassigned to another tenant.
    """

    def __init__(self, table: RecordTable) -> None:
        self._table = table

    def get(self, key: str, default=None):
        value = self._table.get(key)
        return default if value is None else value

    def __getitem__(self, key: str):
        value = self._table.get(key)
        if value is None:
            raise KeyError(key)
        return value

    def __setitem__(self, key: str, value) -> None:
        tenant_id = getattr(value, "tenant_id", None)
        if not tenant_id:
            raise ValueError("PersistentTenantObjectMap values require tenant_id")
        self._table.put(key, tenant_id, value)

    def __delitem__(self, key: str) -> None:
        self._table.delete(key)

    def __contains__(self, key: str) -> bool:
        return self._table.get(key) is not None

    def __iter__(self):
        return (row_id for row_id, _tenant_id, _obj in self._table.all_rows())

    def __len__(self) -> int:
        return len(self._table.all_rows())

    def values(self):
        return [obj for _row_id, _tenant_id, obj in self._table.all_rows()]

    def items_for_tenant(self, tenant_id: str):
        return [(row_id, obj) for row_id, _tenant_id, obj
                in self._table.rows_for_tenant(tenant_id)]


class PersistentIdempotencyStore:
    """SQLite-backed drop-in for ``campaia_core.infra.IdempotencyStore``'s public interface.

    ``campaia_core`` must stay pure domain logic with no I/O (constraint of this task), so this
    is a parallel, API-layer implementation with the exact same ``get``/``execute`` contract
    and semantics (replay returns the original result without re-invoking ``operation``), only
    swapped into ``AppState.idempotency`` when persistence is enabled. It reuses
    ``campaia_core.infra.StoredResult`` purely as a plain, already-defined return-value shape --
    it does not import anything mutable from, or write into, ``campaia_core``.
    """

    def __init__(self, table: RecordTable) -> None:
        self._table = table

    @staticmethod
    def _composite_id(tenant_id: str, idempotency_key: str) -> str:
        if not tenant_id:
            # Same guard as campaia_core.infra.IdempotencyStore._key -- this store is a
            # drop-in for that interface and must refuse a tenant-less key identically,
            # not just when persistence happens to be disabled.
            from campaia_core.errors import TenantIsolationViolation

            raise TenantIsolationViolation("Operacao sem tenant_id nao e permitida.")
        return f"{tenant_id}\x1f{idempotency_key}"

    def get(self, tenant_id: str, idempotency_key: str):
        from campaia_core.infra import StoredResult

        row = self._table.get_for_tenant(
            self._composite_id(tenant_id, idempotency_key), tenant_id
        )
        if row is None:
            return None
        return StoredResult(
            tenant_id=tenant_id,
            idempotency_key=idempotency_key,
            result=row["result"],
            stored_at=row["stored_at"],
        )

    def execute(self, tenant_id: str, idempotency_key: str, operation):
        from datetime import timezone

        # F3: one DB unit-of-work covers the idempotency reservation check, every
        # RecordTable mutation performed by operation(), audit writes and result storage.
        # A raised exception rolls back all durable effects.
        with self._table.transaction():
            # Conservative F3 concurrency boundary: serialize critical persisted
            # mutations per tenant even when callers use different Idempotency-Keys.
            # This favors correctness over intra-tenant write throughput until finer
            # resource locks are proven safe. Different tenants remain concurrent.
            self._table.lock_key(f"tenant:{tenant_id}")
            composite_id = self._composite_id(tenant_id, idempotency_key)
            self._table.lock_key(composite_id)
            existing = self.get(tenant_id, idempotency_key)
            if existing is not None:
                return existing.result, True

            result = operation()
            self._table.put(
                composite_id,
                tenant_id,
                {
                    "tenant_id": tenant_id,
                    "idempotency_key": idempotency_key,
                    "result": result,
                    "stored_at": datetime.now(timezone.utc),
                },
            )
            return result, False


class PersistentSeenEventStore:
    """SQLite-backed drop-in for ``campaia_core.webhooks.SeenEventStoreLike``.

    Cronograma mestre, Etapa 1, item 1.1 (24/09/2026): webhook dedupe (``WebhookReceiver``
    and ``AsaasWebhookReceiver``) was in-memory only, losing the guarantee across a process
    restart between two deliveries of the same "at-least-once" event -- same category of gap
    ``PersistentIdempotencyStore`` above already fixes for charge/HTTP idempotency, now for
    the receiving side. Swapped into ``AppState.asaas_webhook`` only when persistence is
    enabled, same convention as every other persisted field here.

    Known limitation, same one already accepted by ``PersistentIdempotencyStore`` above: the
    get-then-put here is not atomic against concurrent callers for the exact same
    ``(provider, event_id)``. This BFF has no real concurrency story yet (single SQLite
    connection, no worker pool) -- fixing that is a bigger change than this item's scope.
    """

    def __init__(self, table: RecordTable) -> None:
        self._table = table

    @staticmethod
    def _composite_id(provider: str, event_id: str) -> str:
        return f"{provider}\x1f{event_id}"

    def mark_if_new(self, provider: str, event_id: str) -> bool:
        key = self._composite_id(provider, event_id)
        # F3: atomic get+put. Concurrent deliveries on separate SQLite connections are
        # serialized by BEGIN IMMEDIATE; PostgreSQL uses the same store contract.
        with self._table.transaction():
            self._table.lock_key(key)
            if self._table.get_for_tenant(key, provider) is not None:
                return False
            self._table.put(
                key,
                provider,
                {
                    "provider": provider,
                    "event_id": event_id,
                    "seen_at": datetime.now(timezone.utc),
                },
            )
            return True

    def contains(self, provider: str, event_id: str) -> bool:
        return self._table.get(self._composite_id(provider, event_id)) is not None
