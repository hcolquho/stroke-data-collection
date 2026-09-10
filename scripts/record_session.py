"""
Walker-Gait Recording Script
=============================
Records synchronized RGB + depth frames from the Orbbec Femto Bolt.
Called directly by run_protocol.py — can also be run standalone.

Output per trial:
    data/raw_video/<participant>/<block>/<condition>/<trial_N>/
    ├── color/              # 000000.png ...  (BGR uint8)
    ├── depth/              # 000000.png ...  (16-bit uint, mm)
    ├── timestamps.csv      # frame_idx, color_ts_ms, depth_ts_ms
    ├── intrinsics.json     # fx, fy, cx, cy, depth_scale, width, height
    └── metadata.json       # all session parameters

Keybindings (preview window):
    S  — mark 2m  crossing (10MWT start)
    E  — mark 12m crossing (10MWT end)
    Q  — stop recording early

Usage (standalone):
    python scripts/record_session.py --session data/raw_video/P001/block1_healthy_baseline/comfortable/trial_01
    python scripts/record_session.py --session <path> --duration 30 --no-preview
"""

import argparse
import csv
import json
import time
from pathlib import Path

import cv2
import numpy as np

# ── SDK import ────────────────────────────────────────────────────────────────
try:
    from pyorbbecsdk import Pipeline, Config, OBSensorType, OBFormat, FrameSet
    SDK_NAME = "pyorbbecsdk"
except ImportError:
    try:
        from pyorbbecsdk2 import Pipeline, Config, OBSensorType, OBFormat, FrameSet
        SDK_NAME = "pyorbbecsdk2"
    except ImportError:
        raise ImportError(
            "Cannot import pyorbbecsdk or pyorbbecsdk2.\n"
            "Install with: pip install pyorbbecsdk2"
        )

# ── Camera defaults ───────────────────────────────────────────────────────────
COLOR_WIDTH  = 1280
COLOR_HEIGHT = 960
COLOR_FPS    = 30
DEPTH_WIDTH  = 640
DEPTH_HEIGHT = 576
DEPTH_FPS    = 30
SYNC_TOLERANCE_MS = 16


def parse_args():
    parser = argparse.ArgumentParser(description="Walker-Gait recording script")
    parser.add_argument("--session",   required=True, help="Output session directory")
    parser.add_argument("--duration",  type=float, default=60.0,
                        help="Maximum recording duration in seconds (default: 60)")
    parser.add_argument("--no-preview", action="store_true",
                        help="Disable live preview window")
    parser.add_argument("--subject",   type=str, default="", help="Participant ID")
    parser.add_argument("--condition", type=str, default="", help="Condition slug")
    parser.add_argument("--notes",     type=str, default="", help="Free-text notes")
    return parser.parse_args()


def setup_dirs(session_dir: Path):
    (session_dir / "color").mkdir(parents=True, exist_ok=True)
    (session_dir / "depth").mkdir(parents=True, exist_ok=True)


def start_pipeline() -> Pipeline:
    pipeline = Pipeline()
    config   = Config()
    try:
        cp = pipeline.get_stream_profile_list(OBSensorType.COLOR_SENSOR)
        config.enable_stream(
            cp.get_video_stream_profile(COLOR_WIDTH, 0, OBFormat.RGB, COLOR_FPS)
        )
    except Exception as e:
        print(f"[WARN] Color profile: {e}. Using default.")
    try:
        dp = pipeline.get_stream_profile_list(OBSensorType.DEPTH_SENSOR)
        config.enable_stream(
            dp.get_video_stream_profile(DEPTH_WIDTH, 0, OBFormat.Y16, DEPTH_FPS)
        )
    except Exception as e:
        print(f"[WARN] Depth profile: {e}. Using default.")
    pipeline.enable_frame_sync()
    pipeline.start(config)
    return pipeline


def save_intrinsics(pipeline: Pipeline, session_dir: Path):
    try:
        p = pipeline.get_camera_param()
        data = {
            "fx": float(p.rgb_intrinsic.fx),
            "fy": float(p.rgb_intrinsic.fy),
            "cx": float(p.rgb_intrinsic.cx),
            "cy": float(p.rgb_intrinsic.cy),
            "depth_scale": 1.0,
            "width":       COLOR_WIDTH,
            "height":      COLOR_HEIGHT,
            "depth_width": DEPTH_WIDTH,
            "depth_height": DEPTH_HEIGHT,
        }
    except Exception as e:
        print(f"[WARN] Intrinsics unavailable: {e}")
        data = {
            "fx": 0.0, "fy": 0.0, "cx": 0.0, "cy": 0.0,
            "depth_scale": 1.0,
            "width": COLOR_WIDTH, "height": COLOR_HEIGHT,
            "depth_width": DEPTH_WIDTH, "depth_height": DEPTH_HEIGHT,
            "warning": "Intrinsics not read — calibrate manually.",
        }
    with open(session_dir / "intrinsics.json", "w") as f:
        json.dump(data, f, indent=2)
    print(f"Intrinsics: fx={data['fx']:.1f} fy={data['fy']:.1f} "
          f"cx={data['cx']:.1f} cy={data['cy']:.1f}")


def save_metadata(session_dir: Path, args, start_iso: str):
    import datetime
    meta = {
        "subject_id":        args.subject,
        "condition":         args.condition,
        "notes":             args.notes,
        "recording_start":   start_iso,
        "color_resolution":  f"{COLOR_WIDTH}x{COLOR_HEIGHT}",
        "depth_resolution":  f"{DEPTH_WIDTH}x{DEPTH_HEIGHT}",
        "fps":               COLOR_FPS,
        "camera":            "Orbbec Femto Bolt",
        "sdk":               SDK_NAME,
    }
    with open(session_dir / "metadata.json", "w") as f:
        json.dump(meta, f, indent=2)


def decode_color(frame) -> np.ndarray:
    data = np.frombuffer(frame.get_data(), dtype=np.uint8)
    img  = data.reshape((frame.get_height(), frame.get_width(), 3))
    return cv2.cvtColor(img, cv2.COLOR_RGB2BGR)


def decode_depth(frame) -> np.ndarray:
    data = np.frombuffer(frame.get_data(), dtype=np.uint16)
    return data.reshape((frame.get_height(), frame.get_width()))


def record_session(args):
    session_dir  = Path(args.session)
    show_preview = not args.no_preview
    setup_dirs(session_dir)

    print(f"\n{'='*60}")
    print(f"  Session : {session_dir.name}")
    print(f"  Duration: {args.duration}s max")
    if show_preview:
        print(f"  Keys    : S=2m mark  E=12m mark  Q=quit")
    print(f"{'='*60}\n")

    print("Starting camera...")
    pipeline = start_pipeline()
    print(f"Camera ready ({SDK_NAME})\n")

    import datetime
    start_iso = datetime.datetime.now().isoformat()
    save_intrinsics(pipeline, session_dir)
    save_metadata(session_dir, args, start_iso)

    frame_idx    = 0
    manual_marks = {}
    start_wall   = time.time()

    ts_file = open(session_dir / "timestamps.csv", "w", newline="")
    ts_writer = csv.writer(ts_file)
    ts_writer.writerow(["frame_idx", "color_ts_ms", "depth_ts_ms"])

    print("Recording...\n")
    try:
        while time.time() - start_wall < args.duration:
            frameset = pipeline.wait_for_frames(200)
            if frameset is None:
                continue

            color_frame = frameset.get_color_frame()
            depth_frame = frameset.get_depth_frame()
            if color_frame is None or depth_frame is None:
                continue

            color_ts = float(color_frame.get_timestamp())
            depth_ts = float(depth_frame.get_timestamp())

            if abs(color_ts - depth_ts) > SYNC_TOLERANCE_MS:
                print(f"  [WARN] Frame {frame_idx}: sync gap {abs(color_ts - depth_ts):.1f}ms")

            color_bgr = decode_color(color_frame)
            depth_img = decode_depth(depth_frame)

            cv2.imwrite(str(session_dir / "color" / f"{frame_idx:06d}.jpg"), color_bgr,
            [cv2.IMWRITE_JPEG_QUALITY, 95])
            np.save(str(session_dir / "depth" / f"{frame_idx:06d}.npy"), depth_img)
            ts_writer.writerow([frame_idx, color_ts, depth_ts])
            if frame_idx % 100 == 0:
                ts_file.flush()

            elapsed = time.time() - start_wall
            if frame_idx % 30 == 0:
                print(f"  {frame_idx:5d} frames | {elapsed:5.1f}s", end="\r")

            if show_preview:
                preview = cv2.resize(color_bgr, (640, 480))
                for i, (lbl, mark) in enumerate(manual_marks.items()):
                    cv2.putText(preview, f"✓ {lbl} @ {mark['crossing_frame']}",
                                (10, 30 + 30 * i),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                cv2.putText(preview, f"Frame {frame_idx}  {elapsed:.1f}s",
                            (10, 460), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
                cv2.imshow("Walker-Gait  [S=2m  E=12m  Q=quit]", preview)
                key = cv2.waitKey(1) & 0xFF

                if key == ord('s'):
                    manual_marks["2m_line"] = {"crossing_frame": frame_idx,
                                                "crossing_ts_ms": color_ts, "marker_id": 0}
                    print(f"\n  [MARK] 2m  @ frame {frame_idx}")
                elif key == ord('e'):
                    manual_marks["12m_line"] = {"crossing_frame": frame_idx,
                                                 "crossing_ts_ms": color_ts, "marker_id": 1}
                    print(f"\n  [MARK] 12m @ frame {frame_idx}")
                elif key == ord('q'):
                    print("\n  [QUIT] Stopping early.")
                    break

            frame_idx += 1

    except KeyboardInterrupt:
        print("\n  [STOP] Ctrl+C.")
    finally:
        ts_file.close()
        pipeline.stop()
        if show_preview:
            cv2.destroyAllWindows()

    # ── Compute analysis window ───────────────────────────────────────────────
    DISCARD_START_S = 3.0
    DISCARD_END_S   = 3.0
    discard_start_frames = int(DISCARD_START_S * COLOR_FPS)
    discard_end_frames   = int(DISCARD_END_S   * COLOR_FPS)

    analysis_start = discard_start_frames
    analysis_end   = max(analysis_start, frame_idx - discard_end_frames)

    # Map frame indices to timestamps
    start_ts = None
    end_ts   = None
    if analysis_end > 0:
        # Read timestamps back from the CSV we just wrote
        import csv as _csv
        ts_lookup = {}
        with open(session_dir / "timestamps.csv") as f:
            for row in _csv.DictReader(f):
                ts_lookup[int(row["frame_idx"])] = float(row["color_ts_ms"])
        start_ts = ts_lookup.get(analysis_start)
        end_ts   = ts_lookup.get(analysis_end)

    analysis_window = {
        "method"          : "manual_stop_minus_3s",
        "start_frame"     : analysis_start,
        "end_frame"       : analysis_end,
        "start_ts_ms"     : start_ts,
        "end_ts_ms"       : end_ts,
        "discard_start_s" : DISCARD_START_S,
        "discard_end_s"   : DISCARD_END_S,
        "note"            : "First 3s and last 3s discarded to remove "
                            "acceleration and deceleration/stopping frames.",
    }

    # Merge with manual ArUco marks if present (Block 6 with second operator)
    timing_result = {
        "session"         : str(session_dir),
        "method"          : "manual_stop_minus_3s",
        "analysis_window" : analysis_window,
        "timing_marks"    : manual_marks if manual_marks else {},
        "10mwt"           : None,
    }

    # Compute 10MWT if manual S/E marks were logged
    t2m  = manual_marks.get("2m_line",  {}).get("crossing_ts_ms")
    t12m = manual_marks.get("12m_line", {}).get("crossing_ts_ms")
    if t2m and t12m:
        elapsed_s = (t12m - t2m) / 1000.0
        speed     = 10.0 / elapsed_s
        timing_result["10mwt"] = {
            "elapsed_s"              : round(elapsed_s, 3),
            "walking_speed_m_per_s"  : round(speed, 3),
            "walking_speed_m_per_min": round(speed * 60, 1),
        }
        print(f"\n10MWT: {elapsed_s:.2f}s → {speed:.3f} m/s")

    with open(session_dir / "timing_marks_manual.json", "w") as f:
        json.dump(timing_result, f, indent=2)

    print(f"\nAnalysis window: frames {analysis_start} → {analysis_end} "
          f"({analysis_end / COLOR_FPS:.1f}s of usable data)")

    elapsed_total = time.time() - start_wall
    fps_avg = frame_idx / max(elapsed_total, 0.001)
    print(f"Done: {frame_idx} frames | {elapsed_total:.1f}s | {fps_avg:.1f} fps avg")
    print(f"Saved → {session_dir}\n")


if __name__ == "__main__":
    record_session(parse_args())
