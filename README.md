# Walker-Gait Recording Package

Structured data collection for post-stroke gait analysis.
Six-block protocol with automated session naming, completion tracking,
and ArUco-based timing detection on every trial.

---

## Scripts

| Script | Purpose |
|---|---|
| `run_protocol.py` | **Main entry point** — interactive protocol runner |
| `record_session.py` | Records one trial (called by run_protocol.py) |
| `detect_timing_marks.py` | ArUco-based crossing detection (runs after every trial) |
| `generate_aruco_markers.py` | Print floor markers |
| `verify_session.py` | Sanity check a completed session |

---

## Setup

```bash
conda activate gait-pose
pip uninstall opencv-python -y
pip install -r requirements.txt
pip install pyyaml
```

---

## Physical Corridor Setup

All 6 blocks use the same 14m corridor with ArUco markers. Set up once
per location and leave the markers down for the entire session.

|<--2m-->|<-----------10m (analysis window)----------->|<--2m-->|
| | | |
[START] [ID 0] [ID 1] [END]
2m marker 12m marker

- Total corridor: at least 14m, straight, flat, clear
- ArUco ID 0 at the 2m line, ID 1 at the 12m line
- Walk from 0m through to 14m — never stop at the 12m marker
- Return along the side of the corridor, not back down the centre

Gait metrics are computed only on the 10m steady-state window between
the two markers. The 2m run-ins ensure you are at your target cadence
before the analysis window begins.

**Generate and print markers:**

```bash
python scripts/generate_aruco_markers.py
```

Print at 15cm x 15cm or larger, laminate, tape flat to floor.

**Validate markers before first session:**

```bash
python scripts/record_session.py --session data/raw_video/aruco_test --duration 30 --subject test --condition aruco_validation
python scripts/detect_timing_marks.py --session data/raw_video/aruco_test --visualise
```

Both marker IDs must appear in the terminal output and the 10MWT speed
must be between 0.5 and 1.8 m/s for a comfortable walk.

---

## Recording Duration Reference

| Block | Condition | Duration | Metronome |
|---|---|---|---|
| 1 — Baseline | Comfortable | 30s | None |
| 1 — Baseline | Brisk | 25s | 125 BPM |
| 1 — Baseline | Slow healthy | 35s | 85 BPM |
| 2 — Speed reduction | Mild slow | 35s | 72 BPM |
| 2 — Speed reduction | Moderate slow | 45s | 58 BPM |
| 2 — Speed reduction | Severe slow | 90s | 44 BPM |
| 3 — Temporal asymmetry | Mild | 35s | 80 BPM |
| 3 — Temporal asymmetry | Moderate | 40s | 70 BPM |
| 3 — Temporal asymmetry | Severe | 45s | 55 BPM |
| 4 — Spatial asymmetry | Mild | 35s | 80 BPM |
| 4 — Spatial asymmetry | Moderate | 40s | 70 BPM |
| 4 — Spatial asymmetry | Combined | 45s | 60 BPM |
| 5 — Compensatory | Foot drop | 45s | 55 BPM |
| 5 — Compensatory | Circumduction | 45s | 55 BPM |
| 5 — Compensatory | Shuffling | 60s | 46 BPM |
| 6 — 10MWT | Comfortable | 30s | None |
| 6 — 10MWT | Fast | 25s | None |
| 6 — 10MWT | Slow (severe) | 90s | 44 BPM |
| 6 — 10MWT | Combined asym | 60s | 60 BPM |

Total per full session (3 trials x 18 conditions):
54 recordings, roughly 35-40 min of net recording time plus rest breaks (about 50 min total).

---

## What Happens After Each Trial

run_protocol.py automatically runs after every trial:

1. **ArUco detection** — finds the 2m and 12m crossing frames, writes
   timing_marks.json into the trial folder
2. **Session verification** — checks frame count, timestamps, depth
   validity, and intrinsics
3. **Trial confirmation prompt** — you confirm y/n/r before it logs

For Block 6 trials the timing marks also give you the ground-truth
10MWT walking speed for cross-validation.

---

## Data Architecture
```
data/raw_video/
└── self/
    └── session_01/
        ├── session_info.json               ← affected side, status, timestamps
        ├── completion_log.json             ← auto-maintained by run_protocol.py
        ├── block1_healthy_baseline/
        │   ├── comfortable/
        │   │   ├── trial_01/
        │   │   │   ├── color/              # 000000.jpg ... (JPEG uint8)
        │   │   │   ├── depth/              # 000000.npy ... (uint16 mm)
        │   │   │   ├── timestamps.csv
        │   │   │   ├── intrinsics.json
        │   │   │   ├── metadata.json
        │   │   │   └── timing_marks.json   ← ArUco crossings, every trial
        │   │   ├── trial_02/
        │   │   └── trial_03/
        │   ├── brisk/
        │   └── slow_healthy/
        ├── block2_speed_reduction/
        ├── block3_temporal_asymmetry/
        │   ├── temporal_asym_mild_right/   ← affected side in folder name
        │   ├── temporal_asym_moderate_right/
        │   └── temporal_asym_severe_right/
        ├── block4_spatial_asymmetry/
        ├── block5_compensatory_patterns/
        └── block6_10mwt_validation/
```


---

## Running the Protocol

```bash
# Start session 1, right side affected
python scripts/run_protocol.py --participant self --session-id 1 --affected-side right

# Resume from block 3
python scripts/run_protocol.py --participant self --session-id 1 --start-block 3 --affected-side right

# Start session 2, left side affected, skip blocks 1-2
python scripts/run_protocol.py --participant self --session-id 2 --affected-side left --start-block 3

# Check progress across all sessions
python scripts/run_protocol.py --participant self --summary

# Check progress for one session
python scripts/run_protocol.py --participant self --session-id 1 --summary
```

### At the prompt during a trial

| Input | Meaning |
|---|---|
| `y` | Trial was good — log it |
| `n` | Trial was bad — discard and redo |
| `r` | Retry immediately |
| `s` | Skip this condition |
| `q` | Quit and save progress |

---

## Cross-Validation Check (After Block 6)

Pipeline speed = cadence x mean_step_length
10MWT speed = 10m / elapsed_seconds_from_markers


Agreement within 10% means the pipeline is working correctly.
If they diverge, check depth backprojection first.

---

## Gait Mimicry Reference

| Pattern | Key feature | Mental cue | Main metric |
|---|---|---|---|
| Comfortable | Normal symmetric | — | Baseline |
| Brisk | Fast, symmetric | — | Cadence, speed |
| Slow symmetric | Even steps, low cadence | — | Speed, cadence |
| Temporal mild | Delay push-off ~15% | Sticky foot | Step time SI |
| Temporal moderate | Delay push-off ~25% | Foot peels slowly | Step time SI |
| Temporal severe | Delay push-off ~40% | Full extra beat of stance | Step time SI |
| Spatial mild | Step ~15% shorter | Shorter range | Step length SI |
| Spatial moderate | Step ~25% shorter | Foot plants early | Step length SI |
| Combined | Both shorter and delayed | Sticky and short | All asymmetry |
| Foot drop | No dorsiflexion, toe-first | Ankle in a cast | Event detector |
| Circumduction | Lateral leg swing | Draw a half-circle | Backprojection |
| Shuffling | Tiny steps, no clearance | Feet are heavy | Event detector |

Affected side: keep the same throughout all 6 blocks within a session.
Swap sides in a new session (--session-id 2 --affected-side left).

SI = Symmetry Index = |L - R| / (0.5 x (L + R)) x 100%

---

## Wearing Guide

- Tight, light-coloured clothing
- Light-coloured shorts if possible
- Light socks or bare feet — avoid dark shoes
- Do 3 practice walks before Block 1 each session

---

## Troubleshooting

**HResult 0xc00d3704**
Unplug camera, wait 5 seconds, replug into USB 3.0 port.

**Camera not detected**
USB 3.0 port required. Close Orbbec Device Manager before recording.

**Low FPS (below 20)**
Ensure depth is saved as .npy and colour as .jpg in record_session.py.
Record to an SSD, not an HDD.

**ArUco markers not detected**
Print larger (at least 15cm). Lower ROI_TOP_FRACTION in detect_timing_marks.py
if markers appear above the yellow ROI line in visualisation frames.

**polygonApproxAccuracyRate AttributeError**
Use the setattr version of build_detector() in detect_timing_marks.py.