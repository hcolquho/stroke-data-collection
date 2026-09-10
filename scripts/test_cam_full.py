"""
Full camera test: color + depth sync, timestamps, intrinsics.
Saves a sample color PNG and depth PNG to test_output/ for visual inspection.
Run from your walker-recording-v2/ folder.
"""

import json
import time
from pathlib import Path

import cv2
import numpy as np

try:
    from pyorbbecsdk import Pipeline, Config, OBSensorType, OBFormat
except ImportError:
    from pyorbbecsdk2 import Pipeline, Config, OBSensorType, OBFormat

OUT = Path("test_output")
OUT.mkdir(exist_ok=True)

results = {} # Store results for JSON output

# Check camera connection and get device info
print("\n[1/5] Connecting...")
pipeline = Pipeline()
info     = pipeline.get_device().get_device_info()
print(f"  Device : {info.get_name()}  |  Serial: {info.get_serial_number()}")
results["device"] = info.get_name()

# Check camera intrinsics
print("[2/5] Reading intrinsics...")
config = Config()
try:
    cp = pipeline.get_stream_profile_list(OBSensorType.COLOR_SENSOR)
    config.enable_stream(cp.get_video_stream_profile(1280, 960, OBFormat.RGB, 30))
    dp = pipeline.get_stream_profile_list(OBSensorType.DEPTH_SENSOR)
    config.enable_stream(dp.get_video_stream_profile(640, 576, OBFormat.Y16, 30))
except Exception as e:
    print(f"  [WARN] Profile error: {e} — using defaults")

pipeline.enable_frame_sync()
pipeline.start(config)

try:
    param = pipeline.get_camera_param()
    fx, fy = param.rgb_intrinsic.fx, param.rgb_intrinsic.fy
    cx, cy = param.rgb_intrinsic.cx, param.rgb_intrinsic.cy
    intrinsics_ok = fx > 0 and fy > 0
    print(f"  fx={fx:.1f}  fy={fy:.1f}  cx={cx:.1f}  cy={cy:.1f}")
    results["intrinsics"] = {"fx": fx, "fy": fy, "cx": cx, "cy": cy}
    results["intrinsics_ok"] = intrinsics_ok
    with open(OUT / "intrinsics.json", "w") as f:
        json.dump(results["intrinsics"], f, indent=2)
except Exception as e:
    print(f"  [WARN] Could not read intrinsics: {e}")
    results["intrinsics_ok"] = False

# Capture frames for 10 seconds, checking sync and timestamps
print("[3/5] Capturing frames (10 seconds)...")

frame_count   = 0
sync_gaps     = []
timestamps    = []
sample_color  = None
sample_depth  = None

start = time.time()
while time.time() - start < 10.0:
    fs = pipeline.wait_for_frames(200)
    if fs is None:
        continue

    cf = fs.get_color_frame()
    df = fs.get_depth_frame()
    if cf is None or df is None:
        continue

    ct = float(cf.get_timestamp())
    dt = float(df.get_timestamp())
    sync_gap = abs(ct - dt)
    sync_gaps.append(sync_gap)
    timestamps.append(ct)
    frame_count += 1

    # Save one sample frame (around frame 30)
    if frame_count == 30:
        data  = np.frombuffer(cf.get_data(), dtype=np.uint8)
        img   = data.reshape((cf.get_height(), cf.get_width(), 3))
        sample_color = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

        ddata = np.frombuffer(df.get_data(), dtype=np.uint16)
        sample_depth = ddata.reshape((df.get_height(), df.get_width()))

pipeline.stop()

# Analysis of results 
print("[4/5] Analysing results...")
fps_actual  = frame_count / 10.0
mean_gap    = float(np.mean(sync_gaps)) if sync_gaps else 999
n_large_gap = sum(g > 16 for g in sync_gaps)  # >16ms = outside one-frame sync window

# Timestamp monotonicity
ts_arr  = np.array(timestamps)
n_backwards = int((np.diff(ts_arr) <= 0).sum()) if len(ts_arr) > 1 else 0

# Depth validity
if sample_depth is not None:
    valid_pct = float((sample_depth > 0).mean() * 100)
else:
    valid_pct = 0.0

results.update({
    "fps":            round(fps_actual, 1),
    "mean_sync_gap_ms": round(mean_gap, 2),
    "large_sync_gaps":  n_large_gap,
    "non_monotonic_ts": n_backwards,
    "depth_valid_pct":  round(valid_pct, 1),
})

# Save sample frames and report the results
print("[5/5] Saving sample frames and report...\n")

if sample_color is not None:
    cv2.imwrite(str(OUT / "sample_color.png"), sample_color)
    print(f"  Color sample → test_output/sample_color.png")

if sample_depth is not None:
    # Save depth as 16-bit PNG (raw mm values)
    cv2.imwrite(str(OUT / "sample_depth_raw.png"), sample_depth)
    # Also save a normalised 8-bit version for easy visual inspection
    depth_vis = cv2.normalize(sample_depth, None, 0, 255, cv2.NORM_MINMAX, cv2.CV_8U)
    depth_col = cv2.applyColorMap(depth_vis, cv2.COLORMAP_JET)
    cv2.imwrite(str(OUT / "sample_depth_colourmap.png"), depth_col)
    print(f"  Depth sample → test_output/sample_depth_colourmap.png  (colourised for inspection)")

with open(OUT / "test_results.json", "w") as f:
    json.dump(results, f, indent=2)

# Report results in a human-readable table
checks = [
    ("FPS ≥ 25",              fps_actual >= 25,
     f"{fps_actual:.1f} fps",
     "Low — check USB 3.0 port and close other USB devices"),
    ("Sync gap < 16ms (mean)", mean_gap < 16,
     f"{mean_gap:.1f}ms mean",
     "High — hardware sync may not be active"),
    ("Large sync gaps < 5%",   n_large_gap / max(frame_count, 1) < 0.05,
     f"{n_large_gap}/{frame_count} frames",
     "Too many — USB bandwidth issue"),
    ("Timestamps monotonic",   n_backwards == 0,
     "✓" if n_backwards == 0 else f"{n_backwards} inversions",
     "Timestamp rollover or clock issue"),
    ("Depth valid pixels > 40%", valid_pct > 40,
     f"{valid_pct:.1f}%",
     "Low — point camera at a surface within 4m, check USB 3.0"),
    ("Intrinsics non-zero",    results.get("intrinsics_ok", False),
     "✓" if results.get("intrinsics_ok") else "✗",
     "Intrinsics returned zeros — may need firmware update"),
]

print(f"{'─'*58}")
print(f"  {'CHECK':<35} {'VALUE':<12} STATUS")
print(f"{'─'*58}")
all_pass = True
for label, passed, value, fix in checks:
    icon = "✓" if passed else "✗"
    print(f"  {icon}  {label:<35} {value}")
    if not passed:
        print(f"        → {fix}")
        all_pass = False
print(f"{'─'*58}")
print(f"\n  {'✓ All checks passed' if all_pass else '✗ Some checks failed — see above'}")
print(f"  Full results: test_output/test_results.json\n")