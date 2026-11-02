#!/usr/bin/env python3
"""Free disk space in the content studio without touching anything you still need.

Usage: python3 tools/cleanup.py [--dry-run] [--keep-days 7]

- Deletes temp render folders (clone_* in the system temp dir) left by crashed runs.
- In work/<clip>/: deletes intermediate files (stage*.mp4, *.ass, frames/) older than --keep-days.
  Keeps blueprint.md/json, scripts and reports.
- Moves raw clips from inbox/ to archive/ once an export with the same name exists in exports/.
- Never deletes anything in inbox/, exports/ or archive/.
Prints one summary line.
"""
import argparse, glob, os, shutil, tempfile, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def size(p):
    if os.path.isfile(p):
        return os.path.getsize(p)
    return sum(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(p) for f in fs)


def remove(p, dry, freed):
    freed[0] += size(p)
    if not dry:
        shutil.rmtree(p, ignore_errors=True) if os.path.isdir(p) else os.remove(p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--keep-days", type=float, default=7)
    a = ap.parse_args()
    cutoff = time.time() - a.keep_days * 86400
    freed, removed, archived = [0], 0, 0

    for p in glob.glob(os.path.join(tempfile.gettempdir(), "clone_*")):
        remove(p, a.dry_run, freed); removed += 1

    for clip in glob.glob(os.path.join(ROOT, "work", "*")):
        for pat in ("stage*.mp4", "*.ass", "frames"):
            for p in glob.glob(os.path.join(clip, pat)):
                if os.path.getmtime(p) < cutoff:
                    remove(p, a.dry_run, freed); removed += 1

    exports = {os.path.splitext(f)[0].split("_")[0] for f in os.listdir(os.path.join(ROOT, "exports"))
               if not f.startswith(".")}
    for f in os.listdir(os.path.join(ROOT, "inbox")):
        stem = os.path.splitext(f)[0]
        if not f.startswith(".") and stem in exports:
            if not a.dry_run:
                shutil.move(os.path.join(ROOT, "inbox", f), os.path.join(ROOT, "archive", f))
            archived += 1

    tag = "WOULD FREE" if a.dry_run else "FREED"
    print(f"{tag} {freed[0] / 1e6:.1f} MB · {removed} temp items · {archived} raws moved to archive/")


if __name__ == "__main__":
    main()
