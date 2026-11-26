#!/usr/bin/env python3
"""Stage, commit and push a working tree in size-bounded batches.

The mirrored tree is a few hundred megabytes. A single `git push` of that size
is easily killed by a reset-prone uplink, so this helper splits the change into
commits of roughly ``--batch-mb`` and pushes each one, retrying on failure.
Every successful batch is already on the remote, so a later failure never loses
the earlier progress.

Usage:
    python scripts/push_batched.py                  # push main, 60 MB batches
    python scripts/push_batched.py --batch-mb 40 --branch main
    python scripts/push_batched.py --dry-run        # show the batching plan
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time

SKIP_DIRS = {".git", "__pycache__", ".venv", "node_modules"}


def git(*args: str, check: bool = False) -> subprocess.CompletedProcess:
    proc = subprocess.run(["git", *args], capture_output=True, text=True)
    if check and proc.returncode != 0:
        sys.stderr.write(proc.stdout + proc.stderr)
        raise SystemExit(f"git {' '.join(args)} failed with {proc.returncode}")
    return proc


def pending_files(root: str) -> list[tuple[str, int]]:
    out = git("status", "--porcelain", "-uall")
    if out.returncode != 0:
        sys.stderr.write(out.stderr)
        raise SystemExit("not a git repository?")
    items: list[tuple[str, int]] = []
    for line in out.stdout.splitlines():
        if not line.strip():
            continue
        path = line[3:].strip().strip('"')
        if any(part in SKIP_DIRS for part in path.replace("\\", "/").split("/")):
            continue
        full = os.path.join(root, path)
        if os.path.isfile(full):
            items.append((path, os.path.getsize(full)))
        elif os.path.isdir(full):
            for dirpath, dirnames, filenames in os.walk(full):
                dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
                for fn in filenames:
                    fp = os.path.join(dirpath, fn)
                    rel = os.path.relpath(fp, root).replace("\\", "/")
                    items.append((rel, os.path.getsize(fp)))
    return sorted(items, key=lambda x: x[1])


def batch(items: list[tuple[str, int]], limit: int) -> list[list[tuple[str, int]]]:
    groups: list[list[tuple[str, int]]] = []
    current: list[tuple[str, int]] = []
    size = 0
    for item in items:
        if current and size + item[1] > limit:
            groups.append(current)
            current, size = [], 0
        current.append(item)
        size += item[1]
    if current:
        groups.append(current)
    return groups


def human(num: int) -> str:
    value = float(num)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--branch", default="main")
    ap.add_argument("--batch-mb", type=float, default=60.0)
    ap.add_argument("--attempts", type=int, default=4)
    ap.add_argument("--message", default="chore(mirror): refresh")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    root = os.getcwd()
    limit = int(args.batch_mb * 1024 * 1024)

    git("config", "core.autocrlf", "false")
    git("config", "core.quotepath", "false")
    git("config", "http.postBuffer", "104857600")
    git("config", "http.version", "HTTP/1.1")

    items = pending_files(root)
    if not items:
        print("nothing to commit")
        return 0
    total = sum(s for _, s in items)
    print(f"pending: {len(items)} files, {human(total)}")

    groups = batch(items, limit)
    print(f"batches: {len(groups)}")
    if args.dry_run:
        for i, g in enumerate(groups, 1):
            print(f"  {i:2d}: {len(g):4d} files, {human(sum(s for _, s in g))}")
        return 0

    for index, group in enumerate(groups, 1):
        size = sum(s for _, s in group)
        spec = os.path.join(root, ".git", "batch-paths.txt")
        with open(spec, "w", encoding="utf-8") as fh:
            fh.write("\n".join(p for p, _ in group))
        add = git("add", "--pathspec-from-file", spec)
        os.remove(spec)
        if add.returncode != 0:
            sys.stderr.write(add.stderr)
            return 1
        msg = f"{args.message} [{index}/{len(groups)}] {human(size)}"
        commit = git("commit", "-m", msg)
        if commit.returncode != 0:
            print(f"batch {index}: nothing staged, skipping")
            continue

        for attempt in range(1, args.attempts + 1):
            started = time.time()
            push = git("push", "origin", f"HEAD:{args.branch}")
            elapsed = time.time() - started
            if push.returncode == 0:
                rate = size / max(elapsed, 0.001) / 1024
                print(f"batch {index}/{len(groups)} OK  {human(size)} in {elapsed:.1f}s ({rate:.0f} KB/s)")
                break
            print(f"batch {index}/{len(groups)} attempt {attempt} failed: "
                  f"{(push.stderr or push.stdout).strip().splitlines()[-1:]}")
            time.sleep(5 * attempt)
        else:
            print("giving up on this batch; everything pushed so far is safe")
            return 1
    print("all batches pushed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
