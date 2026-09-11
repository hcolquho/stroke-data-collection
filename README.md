# Walker-Gait Data Collection

Structured recording system for post-stroke gait analysis using an Orbbec Femto Bolt
depth camera mounted on a rollator walker. Records synchronized RGB + depth video at
30 fps across a six-block walking protocol.

---

## Quick Start

```bash
conda activate gait-pose
cd C:\Users\hanna\Documents\USRA\data-collection

# Test the camera first
python scripts/test_cam_full.py

# Run the protocol
python scripts/run_protocol.py --participant <id> --session-id 1 --affected-side right
```

---

## Scripts

| Script | Purpose |
|---|---|
| `run_protocol.py` | **Main entry point** — interactive six-block protocol runner |
| `record_session.py` | Records one trial (called by run_protocol.py) |
| `verify_session.py` | Sanity-checks a completed trial |
| `test_cam_full.py` | Confirms camera, depth, sync, and intrinsics before recording |
| `test_recording.py` | 10-second test recording + immediate verification |
| `generate_aruco_markers.py` | Prints 10MWT floor markers |
| `detect_timing_marks.py` | Post-hoc ArUco crossing detection (Block 6 only) |

---

## Setup

### 1. Install dependencies

```bash
conda activate gait-pose
pip uninstall opencv-python -y
pip install -r requirements.txt
pip install pyyaml
```

### 2. Confirm camera works

```bash
python scripts/test_cam_full.py
```

All six checks must pass before recording. The most common failure is a USB 2.0 port
(use the blue USB 3.0 port) or a previous pipeline that did not release the camera
(unplug, wait 5 seconds, replug).

### 3. Run a test recording

```bash
python scripts/test_recording.py
```

Confirms the full recording pipeline: camera → frames → verify. Check
`data/raw_video/test/trial_00/` to confirm colour JPEGs and depth `.npy` files
are being saved correctly.

---

## Camera and Mount

- **Camera:** Orbbec Femto Bolt (serial CL8S16100V3, firmware 1.1.3)
  - Colour: 1280×960 @ 30 fps, JPEG
  - Depth: 640×576 @ 30 fps, `.npy` uint16 (values in mm)
  - Intrinsics: fx=1004.1, fy=1003.7, cx=640.1, cy=487.6
  - Hardware frame sync: on; colour/depth gap ≈ 1.1 ms
- **Mount:** SmallRig 4862 super clamp + magic arm, clamped to the bar below the
  walker seat (backrest and seat cushion removed)
- **Walker:** Evolution Mini Trillium rollator, suited to users 4'10"–5'4"
- **View:** angled downward, captures hips to floor of the walker user

---

## Corridor Setup (do once per location)

```
│←──2m──→│←────────────10m (analysis window)────────────→│←──2m──→│
│        │                                                 │        │
[START] [ID 0]                                         [ID 1]   [END]
        ArUco 2m marker                             ArUco 12m marker
```

- Minimum corridor length: **14m**, straight, flat, unobstructed
- Tape the ArUco markers flat to the floor at the 2m and 12m lines
- Leave markers down for the entire session — all 6 blocks use the same corridor
- Walk from 0m through to 14m — **never stop at the 12m marker**
- Return along the side of the corridor after each trial

### Generate and print markers

```bash
python scripts/generate_aruco_markers.py
# → markers/2m_marker.png  (ArUco ID 0)
# → markers/12m_marker.png (ArUco ID 1)
```

Print at **≥ 15 × 15 cm**, laminate, tape flat to the floor.

### ArUco note

ArUco detection was reliable at slow walking speeds but produced motion-blurred frames
at brisk pace, making automatic crossing detection unreliable. During pilot data
collection, **manual Q-press timing** replaced ArUco for all blocks. ArUco detection
(`detect_timing_marks.py`) is retained for Block 6 sessions where a second operator
is available.

---

## Before You Record

- [ ] Wear tight, light-coloured clothing (shorts preferred)
- [ ] Light-coloured socks or bare feet — avoid dark shoes
- [ ] Camera mounted and USB 3.0 connected
- [ ] `test_cam_full.py` passes all six checks
- [ ] ArUco markers taped at 2m and 12m
- [ ] Metronome app on phone set to correct BPM for the condition
- [ ] 3 practice walks at comfortable pace before Block 1

---

## Running the Protocol

```bash
# Session 1 — right side affected, all 6 blocks
python scripts/run_protocol.py --participant han --session-id 1 --affected-side right

# Session 2 — left side affected (swap sides between sessions)
python scripts/run_protocol.py --participant han --session-id 2 --affected-side left

# Resume from a specific block
python scripts/run_protocol.py --participant han --session-id 1 --start-block 3 --affected-side right --skip-checklist

# Check progress
python scripts/run_protocol.py --participant han --summary
python scripts/run_protocol.py --participant han --session-id 1 --summary
```

### At each prompt

| Input | Meaning |
|---|---|
| `y` | Trial was good — log it and continue |
| `n` | Trial was bad — discard and redo immediately |
| `r` | Retry immediately without logging |
| `s` | Skip this condition |
| `q` | Quit and save progress (safe to resume later) |

### Trial flow

1. Read the condition instructions and BPM on screen
2. Set your metronome to the listed BPM
3. Press `y` at the ready prompt — the recording window opens
4. Walk to the 0m start line and stand still for **3 seconds**
5. Begin walking at the target cadence through the full corridor
6. After passing the 12m marker, continue to the 14m end
7. Press **Q** in the preview window — the last 3 seconds are discarded automatically
8. Wait for verification to print, then answer `y/n/r`

> **Important:** the preview window must have focus for Q to register. Click on it
> before pressing Q. If the timer expires naturally that is also fine.

---

## Protocol — Six Blocks

All conditions use the 14m corridor. The affected side stays the same across all
6 blocks within a session. Swap sides in a new session.

### Block 1 — Healthy Baseline

Ground truth for the pipeline. Walk normally — no mimicry.

| Condition | Duration | Metronome |
|---|---|---|
| Comfortable (self-selected pace) | 30s | None |
| Brisk | 25s | 125 BPM |
| Slow healthy | 35s | 85 BPM |

### Block 2 — Speed Reduction (Symmetric)

Slow symmetric gait across the post-stroke speed range (0.18–1.03 m/s).
Keep steps equal in length and timing.

| Condition | Duration | Metronome | Approx. speed |
|---|---|---|---|
| Mild slow | 35s | 72 BPM | ~0.7 m/s |
| Moderate slow | 45s | 58 BPM | ~0.5 m/s |
| Severe slow | 90s | 44 BPM | ~0.25 m/s |

### Block 3 — Temporal Asymmetry

Delay push-off of the **affected foot** — the foot lingers in stance longer.
Keep step *lengths* roughly equal. Only the *timing* changes.
Mental cue: **the affected foot is sticky**.

| Condition | Duration | Metronome | Target asymmetry |
|---|---|---|---|
| Mild | 35s | 80 BPM | ~15% step time difference |
| Moderate | 40s | 70 BPM | ~25% step time difference |
| Severe | 45s | 55 BPM | ~40% step time difference |

### Block 4 — Spatial Asymmetry

Take a **shorter step** with the affected foot. Keep timing even.
The unaffected foot lands on the beat; the affected foot plants early.
Mental cue: **the affected leg has a shorter range**.

| Condition | Duration | Metronome | Target asymmetry |
|---|---|---|---|
| Mild | 35s | 80 BPM | ~15% shorter step |
| Moderate | 40s | 70 BPM | ~25% shorter step |
| Combined (temporal + spatial) | 45s | 60 BPM | Both — most realistic |

### Block 5 — Compensatory Patterns

Stress tests for specific pipeline components.

| Condition | Duration | Metronome | Instruction |
|---|---|---|---|
| Foot drop | 45s | 55 BPM | Keep affected ankle stiff through swing, toe-first landing. **Safety first — only attempt if you can do so without tripping.** |
| Circumduction | 45s | 55 BPM | Swing affected leg outward in a wide lateral arc to clear the foot |
| Shuffling | 60s | 46 BPM | Very small steps, feet barely clear the floor, no heel strike |

### Block 6 — 10MWT Ground-Truth Validation

Standardised 10-Meter Walk Test with ArUco timing. Run after all mimicry blocks.
The elapsed time between the 2m and 12m markers gives ground-truth walking speed for
cross-validation against the pipeline's computed speed.

| Condition | Duration | Metronome |
|---|---|---|
| Comfortable | 30s | None |
| Fast | 25s | None |
| Slow (severe) | 90s | 44 BPM |
| Combined asymmetry | 60s | 60 BPM |

---

## Recording Durations Summary

| Block | Condition | Duration | Metronome |
|---|---|---|---|
| 1 — Baseline | Comfortable | 30s | None |
| 1 — Baseline | Brisk | 25s | 125 BPM |
| 1 — Baseline | Slow healthy | 35s | 85 BPM |
| 2 — Speed reduction | Mild slow | 35s | 72 BPM |
| 2 — Speed reduction | Moderate slow | 45s | 58 BPM |
| 2 — Speed reduction | Severe slow | **90s** | 44 BPM |
| 3 — Temporal asymmetry | Mild | 35s | 80 BPM |
| 3 — Temporal asymmetry | Moderate | 40s | 70 BPM |
| 3 — Temporal asymmetry | Severe | 45s | 55 BPM |
| 4 — Spatial asymmetry | Mild | 35s | 80 BPM |
| 4 — Spatial asymmetry | Moderate | 40s | 70 BPM |
| 4 — Spatial asymmetry | Combined | 45s | 60 BPM |
| 5 — Compensatory | Foot drop | 45s | 55 BPM |
| 5 — Compensatory | Circumduction | 45s | 55 BPM |
| 5 — Compensatory | Shuffling | **60s** | 46 BPM |
| 6 — 10MWT | Comfortable | 30s | None |
| 6 — 10MWT | Fast | 25s | None |
| 6 — 10MWT | Slow (severe) | **90s** | 44 BPM |
| 6 — 10MWT | Combined asym | 60s | 60 BPM |

Full session (3 trials × 18 conditions): ~54 recordings, ~35–40 min net recording
time, ~50 min including rest breaks.

---

## Analysis Window

Each trial discards the first 3 seconds (acceleration) and everything after the Q
keypress (deceleration/stopping). The remaining frames are the **analysis window**,
stored in `timing_marks_manual.json`:

```json
{
  "analysis_window": {
    "start_frame": 90,
    "end_frame": 402,
    "discard_start_s": 3.0,
    "discard_end_s": 3.0
  }
}
```

The processing pipeline (`process_session.py` in the walker-gait repo) reads this file
and slices the keypoint sequence to this window before computing gait metrics.

---

## Data Architecture

```
data/raw_video/
└── han/
    ├── session_01/                         ← right side affected
    │   ├── session_info.json               ← affected side, start time, status
    │   ├── completion_log.json             ← auto-maintained by run_protocol.py
    │   ├── block1_healthy_baseline/
    │   │   ├── comfortable_right/
    │   │   │   ├── trial_01/
    │   │   │   │   ├── color/              # 000000.jpg ... (JPEG BGR uint8)
    │   │   │   │   ├── depth/              # 000000.npy ... (uint16, mm)
    │   │   │   │   ├── timestamps.csv      # frame_idx, color_ts_ms, depth_ts_ms
    │   │   │   │   ├── intrinsics.json     # fx, fy, cx, cy, depth_scale
    │   │   │   │   ├── metadata.json       # subject, condition, bpm, notes
    │   │   │   │   └── timing_marks_manual.json  ← analysis window
    │   │   │   ├── trial_02/
    │   │   │   └── trial_03/
    │   │   ├── brisk_right/
    │   │   └── slow_healthy_right/
    │   ├── block2_speed_reduction/
    │   ├── block3_temporal_asymmetry/
    │   ├── block4_spatial_asymmetry/
    │   ├── block5_compensatory_patterns/
    │   └── block6_10mwt_validation/
    └── session_02/                         ← left side affected
```

### Known quirk: timestamp count

`timestamps.csv` sometimes has ~86 fewer rows than there are frames. The missing rows
always fall in the discard zone at the end of the recording (after the Q press).
The analysis window is unaffected. `process_session.py` derives timestamps as
`frame_index / 30.0` and does not read the CSV.

---

## Gait Mimicry Reference

| Pattern | What changes | Mental cue | Primary metric |
|---|---|---|---|
| Comfortable | Nothing — true baseline | — | Baseline |
| Brisk | Speed only | — | Cadence, speed |
| Slow symmetric | Speed only, steps stay even | — | Speed, cadence |
| Temporal mild | Timing: +15% stance on affected side | Sticky foot | Step time SI |
| Temporal moderate | Timing: +25% stance | Foot peels slowly | Step time SI |
| Temporal severe | Timing: +40% stance | Full extra beat | Step time SI |
| Spatial mild | Length: affected step ~15% shorter | Short range | Step length SI |
| Spatial moderate | Length: affected step ~25% shorter | Foot plants early | Step length SI |
| Combined | Both shorter step AND delayed push-off | Sticky and short | All asymmetry |
| Foot drop | No dorsiflexion, toe-first | Ankle in a cast | Event detector |
| Circumduction | Lateral leg arc on swing | Draw a half-circle | Backprojection |
| Shuffling | Tiny steps, no foot clearance | Feet are heavy | Event detector |

**SI = Symmetry Index = |L − R| / (0.5 × (L + R)) × 100%**

---

## Troubleshooting

**`HResult 0xc00d3704` — Hardware MFT failed**
Previous pipeline did not release the camera. Unplug USB, wait 5 seconds, replug into
USB 3.0 (blue) port.

**Camera not detected**
USB 3.0 port required. Close Orbbec Device Manager if open — it holds the camera
exclusively.

**`wait_for_frames` TypeError**
Remove `timeout_ms=` keyword — the argument is positional only:
`pipeline.wait_for_frames(200)` not `pipeline.wait_for_frames(timeout_ms=200)`.

**Low FPS (below 20)**
Depth must be saved as `.npy` and colour as `.jpg` (not `.png`). Record to an SSD.

**ArUco markers not detected**
Print at ≥ 15 cm. Check the yellow ROI boundary line in `timing_viz/` frames — if
markers appear above it, lower `ROI_TOP_FRACTION` in `detect_timing_marks.py`.
At brisk walking pace, motion blur makes detection unreliable — use manual Q-press
for all blocks above comfortable pace.

**`getsockname failed: Not a socket` (SSH config)**
Windows OpenSSH does not support `ControlMaster`. Remove `ControlMaster`,
`ControlPath`, and `ControlPersist` from `~/.ssh/config`.

---

## pyorbbecsdk API Gotchas (v1.x)

```python
# Use 0 for height — exact WxH combos raise OBError
cp.get_video_stream_profile(1280, 0, OBFormat.RGB, 30)
dp.get_video_stream_profile(640,  0, OBFormat.Y16, 30)

# Positional only — timeout_ms= keyword raises TypeError
pipeline.wait_for_frames(200)

# Must precede pipeline.start()
pipeline.enable_frame_sync()
```
