#!/usr/bin/env python3
"""Reference implementation for an original, simulated CLI task."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import sys
import tempfile

IDENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")
INTEGER = re.compile(r"[+-]?[0-9]{1,12}\Z")
NONNEGATIVE = re.compile(r"[0-9]{1,12}\Z")
TIMESTAMP = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?(?:Z|[+-][0-9]{2}:[0-9]{2})\Z")
INVENTORY_HEADER = ["sku", "opening_stock"]
REVISION_HEADER = ["event_id", "sku", "delta", "effective_at", "recorded_at", "status"]
OUTPUT_HEADER = ["sku", "opening_stock", "net_change", "closing_stock"]


class TaskError(Exception):
    """A user-facing input or output error."""


class ContractParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        print(f"error: {message}", file=sys.stderr)
        self.exit(2)


def timestamp(value: str) -> datetime:
    if not TIMESTAMP.fullmatch(value):
        raise TaskError(f"invalid timestamp: {value!r}")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except (ValueError, OverflowError) as exc:
        raise TaskError(f"invalid timestamp: {value!r}") from exc


def identifier(value: str, label: str) -> str:
    if not IDENT.fullmatch(value):
        raise TaskError(f"invalid {label}: {value!r}")
    return value


def integer(value: str, label: str, *, nonnegative: bool = False) -> int:
    rule = NONNEGATIVE if nonnegative else INTEGER
    if not rule.fullmatch(value):
        raise TaskError(f"invalid {label}: {value!r}")
    return int(value)


def read_rows(path: Path, header: list[str]) -> list[list[str]]:
    try:
        with path.open("r", encoding="utf-8", newline="") as stream:
            reader = csv.reader(stream, strict=True)
            if next(reader, None) != header:
                raise TaskError(f"invalid CSV header in {path}")
            rows = []
            for row in reader:
                if len(row) != len(header):
                    raise TaskError(f"invalid CSV row in {path} at line {reader.line_num}")
                rows.append(row)
            return rows
    except (OSError, UnicodeError, csv.Error) as exc:
        raise TaskError(f"cannot read CSV {path}: {exc}") from exc


def reconcile(inventory: Path, revisions: Path, cutoff: datetime) -> list[list[object]]:
    opening: dict[str, int] = {}
    for sku_value, quantity in read_rows(inventory, INVENTORY_HEADER):
        sku = identifier(sku_value, "sku")
        if sku in opening:
            raise TaskError(f"duplicate inventory sku: {sku}")
        opening[sku] = integer(quantity, "opening_stock", nonnegative=True)

    # Each event keeps only its maximum eligible recorded time and the distinct
    # semantic payloads at that maximum. Earlier conflicts can be superseded.
    latest: dict[str, tuple[datetime, set[tuple[str, int, datetime, str]]]] = {}
    for event, sku_value, delta_value, effective_value, recorded_value, status in read_rows(revisions, REVISION_HEADER):
        event = identifier(event, "event_id")
        sku = identifier(sku_value, "sku")
        delta = integer(delta_value, "delta")
        effective = timestamp(effective_value)
        recorded = timestamp(recorded_value)
        if status not in {"posted", "void"}:
            raise TaskError(f"invalid status: {status!r}")
        if recorded > cutoff:
            continue
        payload = (sku, delta, effective, status)
        previous = latest.get(event)
        if previous is None or recorded > previous[0]:
            latest[event] = (recorded, {payload})
        elif recorded == previous[0]:
            previous[1].add(payload)

    changes = {sku: 0 for sku in opening}
    for event, (_recorded, payloads) in latest.items():
        if len(payloads) != 1:
            raise TaskError(f"conflicting latest revisions for event: {event}")
        sku, delta, effective, status = next(iter(payloads))
        if status == "void" or effective > cutoff:
            continue
        if sku not in opening:
            raise TaskError(f"active event references unknown sku: {sku}")
        changes[sku] += delta
    return [[sku, opening[sku], changes[sku], opening[sku] + changes[sku]] for sku in sorted(opening)]


def write_atomically(output: Path, rows: list[list[object]]) -> None:
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", dir=output.parent, delete=False) as stream:
            temporary = stream.name
            writer = csv.writer(stream, lineterminator="\n")
            writer.writerow(OUTPUT_HEADER)
            writer.writerows(rows)
        os.replace(temporary, output)
        temporary = None
    except (OSError, UnicodeError, csv.Error) as exc:
        raise TaskError(f"cannot write output {output}: {exc}") from exc
    finally:
        if temporary is not None:
            try:
                os.unlink(temporary)
            except OSError:
                pass


def main(argv: list[str] | None = None) -> int:
    parser = ContractParser(description="Reconcile inventory using versioned stock movements.")
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--revisions", type=Path, required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.output.resolve() in {args.inventory.resolve(), args.revisions.resolve()}:
            raise TaskError("output must differ from both input paths")
        rows = reconcile(args.inventory, args.revisions, timestamp(args.as_of))
        write_atomically(args.output, rows)
    except (TaskError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
