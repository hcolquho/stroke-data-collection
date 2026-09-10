"""
Walker-Gait: Session Verification
====================================
Quick check after recording to confirm:
    - Frame count and continuity
    - Timestamps are monotonically increasing
    - Depth frames contain valid (non-zero) data
    - Intrinsics are non-zero
    - timing_marks.json is present

Usage:
    python scripts/verify_session.py --session data/raw_video/self/session_01/block1_healthy_baseline/comfortable/trial_01
    python scripts/verify_session.py --latest        # auto-finds most recent trial
"""

import argparse
import csv
import json
from pathlib import Path

import cv2
import numpy as np

# ── Path resolution — works regardless of which directory you run from ────────
ROOT      = Path(__file__).resolve().parent.parent
DATA_ROOT = ROOT / "data" / "raw_video"


def find_latest_trial() -> Path | None:
    """Return the most recently modified trial folder under DATA_ROOT."""
    trial_dirs = [
        p for p in DATA_ROOT.rglob("trial_*")
        if p.is_dir() and (p / "timestamps.csv").exists()
    ]
    if not trial_dirs:
        return None
    return max(trial_dirs, key=lambda p: p.stat().st_mtime)


def verify_session(session_dir: Path) -> bool:
    ok = True
    print(f"\nVerifying: {session_dir}\n{'─'*50}")

    # ── File structure ────────────────────────────────────────────────────────
    for expected in ["color", "depth", "timestamps.csv", "intrinsics.json", "metadata.json"]:
        path = session_dir / expected
        exists = path.exists()
        status = "✓" if exists else "✗"
        print(f"  {status}  {expected}")
        if not exists:
            ok = False

    # ── Frame counts ──────────────────────────────────────────────────────────
    color_frames = sorted((session_dir / "color").glob("*.jpg"))
    depth_frames = sorted((session_dir / "depth").glob("*.npy"))
    print(f"\n  Colour frames: {len(color_frames)}")
    print(f"  Depth  frames: {len(depth_frames)}")
    if len(color_frames) != len(depth_frames):
        print(f"  ✗ Frame count mismatch!")
        ok = False
    else:
        print(f"  ✓ Frame counts match")

    # ── Timestamps ────────────────────────────────────────────────────────────
    ts_path = session_dir / "timestamps.csv"
    if ts_path.exists():
        timestamps = []
        with open(ts_path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                timestamps.append(float(row["color_ts_ms"]))

        if len(timestamps) < 2:
            print(f"  ✗ Too few timestamps ({len(timestamps)})")
            ok = False
        else:
            diffs = np.diff(timestamps)
            mean_dt = np.mean(diffs)
            fps_est = 1000.0 / mean_dt if mean_dt > 0 else 0
            n_backwards = (diffs <= 0).sum()
            n_gaps = (diffs > mean_dt * 3).sum()

            print(f"\n  Timestamps: {len(timestamps)} entries")
            print(f"  Est. FPS  : {fps_est:.1f}")
            print(f"  Duration  : {(timestamps[-1] - timestamps[0]) / 1000:.1f}s")

            if n_backwards > 0:
                print(f"  ✗ {n_backwards} non-monotonic timestamps!")
                ok = False
            else:
                print(f"  ✓ Timestamps are monotonically increasing")

            if n_gaps > 0:
                print(f"  ⚠ {n_gaps} large timing gaps (dropped frames?)")

    # ── Sample depth validity ─────────────────────────────────────────────────
    if depth_frames:
        sample_indices = np.linspace(0, len(depth_frames) - 1, 5, dtype=int)
        valid_ratios = []
        for idx in sample_indices:
            depth = np.load(str(depth_frames[idx]))
            ratio = (depth > 0).mean()
            valid_ratios.append(ratio)

        mean_valid = np.mean(valid_ratios) * 100
        print(f"\n  Depth valid pixels: {mean_valid:.1f}% (sampled 5 frames)")
        if mean_valid < 30:
            print(f"  ✗ Very few valid depth pixels — check USB 3.0 connection")
            ok = False
        elif mean_valid < 60:
            print(f"  ⚠ Moderate depth coverage — may affect backprojection quality")
        else:
            print(f"  ✓ Good depth coverage")

    # ── Intrinsics ────────────────────────────────────────────────────────────
    intr_path = session_dir / "intrinsics.json"
    if intr_path.exists():
        with open(intr_path) as f:
            intr = json.load(f)
        fx, fy = intr.get("fx", 0), intr.get("fy", 0)
        print(f"\n  Intrinsics: fx={fx:.1f}, fy={fy:.1f}")
        if fx == 0 or fy == 0:
            print(f"  ✗ Intrinsics are zero — were they read from the device?")
            ok = False
        else:
            print(f"  ✓ Intrinsics look valid")

    # ── Timing marks ─────────────────────────────────────────────────────────
    tm_path        = session_dir / "timing_marks.json"
    tm_manual_path = session_dir / "timing_marks_manual.json"

    if tm_manual_path.exists():
        with open(tm_manual_path) as f:
            tm = json.load(f)
        window = tm.get("analysis_window", {})
        if window:
            start_f = window.get("start_frame", "?")
            end_f   = window.get("end_frame", "?")
            print(f"\n  Analysis window: frames {start_f} → {end_f}")
            print(f"  ✓ Analysis window logged (manual stop method)")
        mwt = tm.get("10mwt")
        if mwt:
            print(f"  10MWT: {mwt['elapsed_s']}s → {mwt['walking_speed_m_per_s']} m/s")
    elif tm_path.exists():
        with open(tm_path) as f:
            tm = json.load(f)
        mwt = tm.get("10mwt")
        if mwt:
            print(f"\n  10MWT: {mwt['elapsed_s']}s → {mwt['walking_speed_m_per_s']} m/s")
            print(f"  ✓ Timing marks present (ArUco)")
        else:
            print(f"\n  ⚠ timing_marks.json present but 10MWT could not be computed")
    else:
        print(f"\n  ⚠ No analysis window logged — press Q after passing 12m mark")

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{'─'*50}")
    if ok:
        print(f"  ✓ Session looks good\n")
    else:
        print(f"  ✗ Session has issues — review above\n")

    return ok


def main():
    parser = argparse.ArgumentParser(description="Verify a recording session")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--session",
                       help="Path to trial directory to verify")
    group.add_argument("--latest", action="store_true",
                       help="Auto-find and verify the most recently recorded trial")
    args = parser.parse_args()

    if args.latest:
        session_dir = find_latest_trial()
        if session_dir is None:
            print(f"No recorded trials found under {DATA_ROOT}")
            return
        print(f"Latest trial: {session_dir}")
    else:
        session_dir = Path(args.session)
        if not session_dir.is_absolute():
            # Accept paths relative to project root OR cwd
            if not session_dir.exists():
                session_dir = ROOT / session_dir

    verify_session(session_dir)


if __name__ == "__main__":
    main()