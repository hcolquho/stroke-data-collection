"""
Walker-Gait: ArUco Timing Mark Detection
==========================================
Post-hoc detection of 10MWT timing line crossings from ArUco floor markers.

Scans saved colour frames, finds the last frame each marker is visible
(= the crossing frame as the walker rolls past), and writes timing_marks.json.

ArUco marker assignment:
    ID 0  →  2m  line  (10MWT timing start)
    ID 1  →  12m line  (10MWT timing end)

Usage:
    python scripts/detect_timing_marks.py --session data/raw_video/session_001
    python scripts/detect_timing_marks.py --session data/raw_video/session_001 --visualise
    python scripts/detect_timing_marks.py --session data/raw_video/session_001 --quiet

Note: If timing_marks_manual.json exists from keypress logging during recording,
      it will be merged with the ArUco results. ArUco takes priority if both have a detection.
"""


import argparse
import csv
import json
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parent.parent # works from any directory


# ── ArUco config ──────────────────────────────────────────────────────────────
ARUCO_DICT_ID   = cv2.aruco.DICT_4X4_50
MARKER_ID_2M    = 0
MARKER_ID_12M   = 1

# Scan only the bottom portion of each frame — floor markers live there
ROI_TOP_FRACTION = 0.45   # ignore top 45% of frame


def parse_args():
    parser = argparse.ArgumentParser(
        description="Detect ArUco floor markers and log 10MWT crossing frames."
    )
    parser.add_argument("--session", required=True,
                        help="Session directory (e.g. data/raw_video/session_001)")
    parser.add_argument("--visualise", action="store_true",
                        help="Save annotated frames around each crossing for verification")
    parser.add_argument("--viz-window", type=int, default=8,
                        help="Number of frames either side of crossing to visualise (default: 8)")
    parser.add_argument("--quiet", action="store_true",
                        help="Suppress per-frame detection output")
    parser.add_argument("--force", action="store_true",
                        help="Overwrite existing timing_marks.json if present")
    return parser.parse_args()


def load_timestamps(session_dir: Path) -> dict[int, float]:
    """Load frame_idx → color_ts_ms mapping from timestamps.csv."""
    ts_path = session_dir / "timestamps.csv"
    timestamps = {}
    if ts_path.exists():
        with open(ts_path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                timestamps[int(row["frame_idx"])] = float(row["color_ts_ms"])
    else:
        print("[WARN] timestamps.csv not found — timing_marks will have no timestamps.")
    return timestamps


def build_detector() -> cv2.aruco.ArucoDetector:
    aruco_dict = cv2.aruco.getPredefinedDictionary(ARUCO_DICT_ID)
    params = cv2.aruco.DetectorParameters()

    for attr, value in [
        ("adaptiveThreshWinSizeMin",  3),
        ("adaptiveThreshWinSizeMax",  25),
        ("adaptiveThreshWinSizeStep", 4),
        ("minMarkerPerimeterRate",    0.02),
        ("maxMarkerPerimeterRate",    0.5),
        ("polygonApproxAccuracyRate", 0.05),
        ("cornerRefinementMethod",    cv2.aruco.CORNER_REFINE_SUBPIX),
    ]:
        try:
            setattr(params, attr, value)
        except AttributeError:
            pass

    return cv2.aruco.ArucoDetector(aruco_dict, params)


def detect_crossings(session_dir: Path, verbose: bool = True) -> dict:
    """
    Scan colour frames for ArUco markers.

    Crossing frame = last frame a marker is detected before it passes
    under the walker. At that frame the walker's leading edge is on the line.

    Returns a result dict ready to be written to timing_marks.json.
    """
    color_dir  = session_dir / "color"
    frame_paths = sorted(color_dir.glob("*.jpg"))

    if not frame_paths:
        raise FileNotFoundError(f"No colour frames in {color_dir}. "
                                f"Check the session path.")

    timestamps = load_timestamps(session_dir)
    detector   = build_detector()

    # last_seen[marker_id] = frame_idx of most recent detection
    last_seen    = {}
    last_seen_ts = {}

    total = len(frame_paths)
    for i, frame_path in enumerate(frame_paths):
        frame_idx = int(frame_path.stem)

        if not verbose and i % 50 == 0:
            print(f"  Scanning {i}/{total} frames...", end="\r")

        frame = cv2.imread(str(frame_path))
        if frame is None:
            continue

        # Restrict to the lower portion of the frame
        h    = frame.shape[0]
        roi_top = int(h * ROI_TOP_FRACTION)
        roi  = frame[roi_top:, :]

        corners, ids, _ = detector.detectMarkers(roi)

        if ids is not None:
            for marker_id in ids.flatten():
                mid = int(marker_id)
                last_seen[mid]    = frame_idx
                last_seen_ts[mid] = timestamps.get(frame_idx)

                if verbose:
                    print(f"  Frame {frame_idx:06d}: marker ID {mid} detected")

    print()  # newline after \r progress

    # ── Build result ──────────────────────────────────────────────────────────
    result = {
        "session"    : str(session_dir),
        "aruco_dict" : "DICT_4X4_50",
        "method"     : "aruco_post_hoc",
        "timing_marks": {},
    }

    for marker_id, label in [(MARKER_ID_2M, "2m_line"), (MARKER_ID_12M, "12m_line")]:
        if marker_id in last_seen:
            result["timing_marks"][label] = {
                "crossing_frame": last_seen[marker_id],
                "crossing_ts_ms": last_seen_ts.get(marker_id),
                "marker_id"     : marker_id,
            }
        else:
            result["timing_marks"][label] = {
                "crossing_frame": None,
                "crossing_ts_ms": None,
                "marker_id"     : marker_id,
                "warning"       : (
                    "Marker not detected in any frame. "
                    "Check: marker is printed large enough, "
                    "lighting is adequate, marker lies within camera FOV."
                ),
            }

    # ── Compute 10MWT ─────────────────────────────────────────────────────────
    t2m  = result["timing_marks"]["2m_line"]["crossing_ts_ms"]
    t12m = result["timing_marks"]["12m_line"]["crossing_ts_ms"]

    if t2m is not None and t12m is not None:
        elapsed_ms  = t12m - t2m
        elapsed_s   = elapsed_ms / 1000.0
        speed_ms    = 10.0 / elapsed_s if elapsed_s > 0 else None
        result["10mwt"] = {
            "elapsed_s"               : round(elapsed_s, 3),
            "walking_speed_m_per_s"   : round(speed_ms, 3) if speed_ms else None,
            "walking_speed_m_per_min" : round(speed_ms * 60, 1) if speed_ms else None,
        }
        print(f"10MWT: {elapsed_s:.2f}s  →  {speed_ms:.3f} m/s  "
              f"({speed_ms * 60:.1f} m/min)")
    else:
        result["10mwt"] = None
        missing = [
            label for label, mark in result["timing_marks"].items()
            if mark["crossing_frame"] is None
        ]
        print(f"[WARN] Could not compute 10MWT — missing: {', '.join(missing)}")

    return result


def visualise_crossings(
    session_dir: Path,
    result: dict,
    window: int = 8,
):
    """Write annotated frames around each detected crossing for manual verification."""
    color_dir  = session_dir / "color"
    viz_dir    = session_dir / "timing_viz"
    viz_dir.mkdir(exist_ok=True)

    detector = build_detector()

    for label, mark in result["timing_marks"].items():
        cf = mark.get("crossing_frame")
        if cf is None:
            print(f"  [VIZ] Skipping {label} — no crossing detected.")
            continue

        for offset in range(-window, window + 1):
            fidx  = cf + offset
            fpath = color_dir / f"{fidx:06d}.jpg"
            if not fpath.exists():
                continue

            frame = cv2.imread(str(fpath))
            h = frame.shape[0]
            roi_top = int(h * ROI_TOP_FRACTION)
            roi = frame[roi_top:, :]

            corners, ids, _ = detector.detectMarkers(roi)
            if ids is not None:
                cv2.aruco.drawDetectedMarkers(roi, corners, ids)

            # Annotations
            colour = (0, 0, 255) if offset == 0 else (0, 180, 255)
            text   = f"CROSSING: {label}" if offset == 0 else f"offset {offset:+d}"
            cv2.putText(frame, text, (15, 45),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, colour, 2)
            cv2.putText(frame, f"frame {fidx}", (15, 85),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 1)

            # ROI boundary line
            cv2.line(frame, (0, roi_top), (frame.shape[1], roi_top), (255, 255, 0), 1)

            out_name = f"{label}_f{fidx:06d}_{offset:+03d}.png"
            cv2.imwrite(str(viz_dir / out_name), frame)

    print(f"Verification frames saved to {viz_dir}/")


def merge_with_manual(session_dir: Path, aruco_result: dict) -> dict:
    """
    If timing_marks_manual.json exists from keypress logging during recording,
    merge it with ArUco results. ArUco takes priority if both have a detection.
    """
    manual_path = session_dir / "timing_marks_manual.json"
    if not manual_path.exists():
        return aruco_result

    with open(manual_path) as f:
        manual = json.load(f)

    merged = aruco_result.copy()
    for label, mark in manual.get("timing_marks", {}).items():
        if aruco_result["timing_marks"].get(label, {}).get("crossing_frame") is None:
            # ArUco missed it — use the manual mark
            mark["method"] = "manual_keypress"
            merged["timing_marks"][label] = mark
            print(f"  [MERGE] {label}: using manual keypress mark (ArUco missed it).")
        else:
            aruco_frame  = aruco_result["timing_marks"][label]["crossing_frame"]
            manual_frame = mark["crossing_frame"]
            diff = abs(aruco_frame - manual_frame)
            print(f"  [MERGE] {label}: ArUco frame {aruco_frame}, "
                  f"manual frame {manual_frame} (diff={diff} frames).")

    return merged


def main():
    args = parse_args()
    session_dir = Path(args.session)
    if not session_dir.is_absolute() and not session_dir.exists():
        session_dir = ROOT / session_dir

    out_path = session_dir / "timing_marks.json"
    if out_path.exists() and not args.force:
        print(f"timing_marks.json already exists. Use --force to overwrite.")
        return

    print(f"\nScanning session: {session_dir}")
    print(f"Looking for ArUco markers: ID {MARKER_ID_2M}=2m, ID {MARKER_ID_12M}=12m\n")

    result = detect_crossings(session_dir, verbose=not args.quiet)
    result = merge_with_manual(session_dir, result)

    # Save
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\nSaved: {out_path}")

    if args.visualise:
        visualise_crossings(session_dir, result, window=args.viz_window)


if __name__ == "__main__":
    main()
