#!/usr/bin/env python3
"""Shared, dependency-free helpers for ASCS experiment operator scripts."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any


def run_cmd(
    cmd: list[str], cwd: Path, capture: bool = False
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
        check=False,
    )


def run_git(
    repo: Path, args: list[str], capture: bool = False
) -> subprocess.CompletedProcess[str]:
    return run_cmd(["git"] + args, repo, capture=capture)


def require_success(proc: subprocess.CompletedProcess[str], command_text: str) -> bool:
    if proc.returncode == 0:
        return True
    if proc.stdout:
        print(proc.stdout, end="", file=sys.stderr)
    if proc.stderr:
        print(proc.stderr, end="", file=sys.stderr)
    print(f"FAIL command failed: {command_text}", file=sys.stderr)
    return False


def parse_porcelain_z(output: str) -> list[tuple[str, str]]:
    """Parse `git status --porcelain=v1 -z`, including rename source paths."""
    tokens = output.split("\0")
    entries: list[tuple[str, str]] = []
    index = 0
    while index < len(tokens):
        record = tokens[index]
        index += 1
        if not record:
            continue
        if len(record) < 4 or record[2] != " ":
            raise ValueError(f"malformed porcelain v1 -z record: {record!r}")
        status, path = record[:2], record[3:]
        entries.append((status, path))
        if "R" in status or "C" in status:
            if index >= len(tokens) or not tokens[index]:
                raise ValueError("rename/copy porcelain record is missing its source path")
            entries.append((status, tokens[index]))
            index += 1
    return entries


def event_note_field(event: dict[str, object], field: str) -> str | None:
    note = str(event.get("note", ""))
    match = re.search(rf"(?:^|;\s*){re.escape(field)}=([^;]+)", note)
    return match.group(1).strip() if match else None


class PairEventJournal:
    """Recoverable pair-wide event transaction shared by experiment helpers."""

    def __init__(
        self,
        pair_arms: Mapping[str, tuple[str, str]],
        arm_from_name: Callable[[str], Any],
        load_events: Callable[[Any], list[dict[str, object]]],
        record_event: Callable[..., int],
        fail: Callable[[str], int],
    ) -> None:
        self.pair_arms = pair_arms
        self.arm_from_name = arm_from_name
        self.load_events = load_events
        self.record_event = record_event
        self.fail = fail

    def arms(self, pair: str) -> list[Any]:
        return [self.arm_from_name(name) for name in self.pair_arms[pair]]

    def transaction_event_ids(
        self, arm: Any, event_name: str, target_event: str | None = None
    ) -> set[str]:
        transaction_ids = set()
        for event in self.load_events(arm):
            if event.get("event") != event_name:
                continue
            if (
                target_event is not None
                and event_note_field(event, "target_event") != target_event
            ):
                continue
            transaction_id = event_note_field(event, "txid")
            if transaction_id:
                transaction_ids.add(transaction_id)
        return transaction_ids

    def arm_has_transaction_stage(
        self,
        arm: Any,
        event_name: str,
        transaction_id: str,
        target_event: str | None = None,
    ) -> bool:
        return transaction_id in self.transaction_event_ids(
            arm, event_name, target_event
        )

    def transaction_stage_notes(
        self,
        arm: Any,
        event_name: str,
        transaction_id: str,
        target_event: str | None = None,
    ) -> list[str]:
        notes = []
        for event in self.load_events(arm):
            if event.get("event") != event_name:
                continue
            if event_note_field(event, "txid") != transaction_id:
                continue
            if (
                target_event is not None
                and event_note_field(event, "target_event") != target_event
            ):
                continue
            notes.append(str(event.get("note", "")))
        return notes

    def pair_event_committed(self, pair: str, event_name: str) -> bool:
        arms = self.arms(pair)
        if all(
            any(
                event.get("event") == event_name
                and event_note_field(event, "txid") is None
                for event in self.load_events(arm)
            )
            for arm in arms
        ):
            return True

        committed_ids: set[str] | None = None
        for arm in arms:
            arm_ids = self.transaction_event_ids(arm, event_name)
            arm_ids &= self.transaction_event_ids(
                arm, "pair-event-commit", event_name
            )
            committed_ids = arm_ids if committed_ids is None else committed_ids & arm_ids
        return bool(committed_ids)

    def pair_event_pending(self, pair: str, event_name: str) -> bool:
        arms = self.arms(pair)
        untagged = [
            any(
                event.get("event") == event_name
                and event_note_field(event, "txid") is None
                for event in self.load_events(arm)
            )
            for arm in arms
        ]
        if any(untagged) and not all(untagged):
            return True

        transaction_ids = set()
        for arm in arms:
            transaction_ids |= self.transaction_event_ids(arm, event_name)
            for stage in ("pair-event-prepare", "pair-event-commit", "pair-event-abort"):
                transaction_ids |= self.transaction_event_ids(
                    arm, stage, event_name
                )
        for transaction_id in transaction_ids:
            if not all(
                self.arm_has_transaction_stage(arm, event_name, transaction_id)
                and self.arm_has_transaction_stage(
                    arm, "pair-event-commit", transaction_id, event_name
                )
                for arm in arms
            ):
                return True
        return False

    def record_pair_event(
        self, pair: str, event_name: str, note: str, transaction_id: str
    ) -> int:
        """Idempotently record a pair event with prepare/commit recovery markers."""
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", transaction_id):
            return self.fail("pair transaction ID contains unsupported characters")
        arms = self.arms(pair)
        stage_notes = (
            (
                "pair-event-prepare",
                f"txid={transaction_id}; pair={pair}; target_event={event_name}",
            ),
            (event_name, f"{note}; txid={transaction_id}"),
            (
                "pair-event-commit",
                f"txid={transaction_id}; pair={pair}; target_event={event_name}",
            ),
        )
        for stage_name, stage_note in stage_notes:
            target_filter = event_name if stage_name.startswith("pair-event-") else None
            for arm in arms:
                existing_notes = self.transaction_stage_notes(
                    arm, stage_name, transaction_id, target_filter
                )
                if existing_notes:
                    if any(
                        existing_note != stage_note for existing_note in existing_notes
                    ):
                        return self.fail(
                            f"pair transaction payload mismatch for {arm.name}/{stage_name}"
                        )
                    continue
                if self.record_event(
                    arm,
                    stage_name,
                    stage_note,
                    pair_id=pair,
                    condition=arm.condition,
                    transaction_id=transaction_id,
                ):
                    abort_note = (
                        f"txid={transaction_id}; pair={pair}; target_event={event_name}; "
                        f"failed_stage={stage_name}"
                    )
                    for abort_arm in arms:
                        if not self.arm_has_transaction_stage(
                            abort_arm,
                            "pair-event-abort",
                            transaction_id,
                            event_name,
                        ):
                            if self.record_event(
                                abort_arm,
                                "pair-event-abort",
                                abort_note,
                                pair_id=pair,
                                condition=abort_arm.condition,
                                transaction_id=transaction_id,
                            ):
                                print(
                                    "WARN could not record abort marker for "
                                    f"{abort_arm.name}",
                                    file=sys.stderr,
                                )
                    print(
                        "PAIR EVENT RECOVERY: no pair claim is committed; fix the "
                        f"event writer and retry the same command (txid={transaction_id})",
                        file=sys.stderr,
                    )
                    return 1
        print(f"PASS committed pair event {event_name} ({transaction_id})")
        return 0


def sha256_file(path: Path) -> str:
    if not path.exists():
        return "missing"
    return hashlib.sha256(path.read_bytes()).hexdigest()


def scaffold_file_hashes(root: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            hashes[path.relative_to(root).as_posix()] = sha256_file(path)
    return hashes


def scaffold_tree_hash(root: Path) -> str:
    file_hashes = scaffold_file_hashes(root)
    payload = json.dumps(file_hashes, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(payload).hexdigest()
