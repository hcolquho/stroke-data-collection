"""
Camera test v3 — correct v1.x API, tries multiple profile approaches.
"""

import time
import numpy as np
import cv2

from pyorbbecsdk import Pipeline, Config, OBSensorType, OBFormat

print("Connecting...")
pipeline = Pipeline()
info = pipeline.get_device().get_device_info()
print(f"  {info.get_name()} | {info.get_serial_number()} | fw {info.get_firmware_version()}\n")

config = Config()

# ── Color profile ─────────────────────────────────────────────────────────────
# Use 0 for height = "any height at this width"
color_ok = False
for (w, h, fmt, fps) in [
    (1280, 0, OBFormat.RGB, 30),
    (1280, 0, OBFormat.MJPG, 30),
    (640,  0, OBFormat.RGB, 30),
    (640,  0, OBFormat.MJPG, 30),
]:
    try:
        pl = pipeline.get_stream_profile_list(OBSensorType.COLOR_SENSOR)
        p  = pl.get_video_stream_profile(w, h, fmt, fps)
        config.enable_stream(p)
        print(f"Color profile:  {p.get_width()}x{p.get_height()} @ {p.get_fps()}fps  fmt={fmt}")
        color_ok = True
        break
    except Exception as e:
        print(f"  skip {w}x{h} fmt={fmt}: {e}")

if not color_ok:
    print("  [WARN] Could not set color profile — pipeline will use device default")

# ── Depth profile ─────────────────────────────────────────────────────────────
depth_ok = False
for (w, h, fmt, fps) in [
    (640, 0, OBFormat.Y16, 30),
    (512, 0, OBFormat.Y16, 30),
    (320, 0, OBFormat.Y16, 30),
]:
    try:
        pl = pipeline.get_stream_profile_list(OBSensorType.DEPTH_SENSOR)
        p  = pl.get_video_stream_profile(w, h, fmt, fps)
        config.enable_stream(p)
        print(f"Depth profile:  {p.get_width()}x{p.get_height()} @ {p.get_fps()}fps  fmt={fmt}")
        depth_ok = True
        break
    except Exception as e:
        print(f"  skip {w}x{h} fmt={fmt}: {e}")

if not depth_ok:
    print("  [WARN] Could not set depth profile — pipeline will use device default")

# ── Start ─────────────────────────────────────────────────────────────────────
print("\nStarting pipeline...")
pipeline.enable_frame_sync()
pipeline.start(config)
print("Streaming 5 seconds...\n")

start = time.time()
color_count = depth_count = 0
gaps = []
sample_color = sample_depth = None

while time.time() - start < 5.0:
    fs = pipeline.wait_for_frames(300)
    if not fs:
        continue
    cf = fs.get_color_frame()
    df = fs.get_depth_frame()
    if cf:
        color_count += 1
        if color_count == 15 and sample_color is None:
            d = np.frombuffer(cf.get_data(), dtype=np.uint8)
            img = d.reshape((cf.get_height(), cf.get_width(), 3))
            sample_color = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    if df:
        depth_count += 1
        if depth_count == 15 and sample_depth is None:
            d = np.frombuffer(df.get_data(), dtype=np.uint16)
            sample_depth = d.reshape((df.get_height(), df.get_width()))
    if cf and df:
        gaps.append(abs(float(cf.get_timestamp()) - float(df.get_timestamp())))

pipeline.stop()

# ── Save sample frames ────────────────────────────────────────────────────────
import pathlib
out = pathlib.Path("test_output")
out.mkdir(exist_ok=True)
if sample_color is not None:
    cv2.imwrite(str(out / "color.png"), sample_color)
    print(f"Color sample saved → test_output/color.png")
if sample_depth is not None:
    cv2.imwrite(str(out / "depth_raw.png"), sample_depth)
    vis = cv2.normalize(sample_depth, None, 0, 255, cv2.NORM_MINMAX, cv2.CV_8U)
    cv2.imwrite(str(out / "depth_colourmap.png"),
                cv2.applyColorMap(vis, cv2.COLORMAP_JET))
    valid_pct = float((sample_depth > 0).mean() * 100)
    print(f"Depth sample saved → test_output/depth_colourmap.png  ({valid_pct:.0f}% valid pixels)")

# ── Report ────────────────────────────────────────────────────────────────────
print(f"\n  Color frames : {color_count} ({color_count/5:.1f} fps)")
print(f"  Depth frames : {depth_count} ({depth_count/5:.1f} fps)")
if gaps:
    print(f"  Mean sync gap: {np.mean(gaps):.1f}ms")

ok = color_count > 20 and depth_count > 20
print(f"\n  {'✓ PASS' if ok else '✗ FAIL'}")
print("\nPaste the Color/Depth profile lines above back to Han so record_session.py can be fixed.\n")