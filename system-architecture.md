# Basketball Coaching Intelligence Platform — System Architecture

---

## 1. System Overview

### Architecture Summary

The system is a **three-tier architecture**: portable capture → edge processing → cloud reporting. The key insight is that you're not building a real-time broadcast system — you're building a **coaching decision-support system** that happens to use video as a primary input.

```
┌─────────────────────────────────────────────────────────────────┐
│                        CAPTURE TIER                             │
│                                                                 │
│   ┌──────────────┐         ┌──────────────────┐                │
│   │  Portable     │   OR    │  Existing Live   │                │
│   │  Camera       │────────▶│  Stream (RTMP/   │                │
│   │  (you bring)  │         │  HLS/YouTube)    │                │
│   └──────┬───────┘         └────────┬─────────┘                │
│          │ HDMI/USB/WiFi            │ Network pull              │
│          └──────────┬───────────────┘                           │
│                     ▼                                           │
├─────────────────────────────────────────────────────────────────┤
│                     EDGE TIER (Mac mini)                        │
│                                                                 │
│   ┌─────────────┐  ┌──────────────┐  ┌───────────────────┐    │
│   │ Video       │  │ CV Pipeline  │  │ Event Extraction  │    │
│   │ Ingestion   │──▶│ (Detection + │──▶│ (Possessions,    │    │
│   │ + Recording │  │  Tracking)   │  │  Zones, Events)   │    │
│   └─────────────┘  └──────────────┘  └────────┬──────────┘    │
│                                                │               │
│   ┌──────────────────┐    ┌───────────────────┐│               │
│   │ Local SQLite     │◀───│ Live Dashboard    ││               │
│   │ + Video Store    │    │ (localhost web)   │◀┘               │
│   └────────┬─────────┘    └───────────────────┘                │
│            │                                                    │
├────────────┼────────────────────────────────────────────────────┤
│            ▼         CLOUD TIER                                 │
│   ┌────────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│   │ Data Sync      │  │ LLM Report   │  │ Coach Dashboard  │  │
│   │ (post-game     │──▶│ Generation   │──▶│ (web app)       │  │
│   │  batch upload) │  │ (Claude API) │  │                  │  │
│   └────────────────┘  └──────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Role Definitions

| Component | Role | When Active |
|---|---|---|
| **Portable camera** | Single wide-angle video source you physically bring and set up | During games |
| **Live stream** | Alternative video source when games are already streamed | During games (when available) |
| **Mac mini (edge)** | Ingests video, runs CV models, extracts events, serves live dashboard, stores everything locally | During games + immediate post-game |
| **Cloud backend** | Receives synced data post-game, runs LLM-powered report generation, hosts persistent coach dashboard | Post-game, scouting, prep |
| **Reporting layer** | Generates three report types from structured event data | Post-game and on-demand |

### Why This Architecture

- **Edge-first** because gym WiFi is unreliable. You can't depend on cloud connectivity during a live game.
- **Batch sync to cloud** because real-time cloud upload adds fragility for marginal benefit. The coach next to you needs insights NOW; the full report can wait 30 minutes.
- **Portable-first** because your constraint explicitly rules out fixed installations. The entire system must fit in a backpack + pelican case.

---

## 2. Video Source Strategy

### Comparison

| Factor | Existing Live Stream | Your Own Portable Camera |
|---|---|---|
| **Setup time** | 0 min (pull URL) | 5-10 min (tripod, angle, connect) |
| **Reliability** | Depends on streamer; can drop, lag, or end | You control it — high reliability |
| **Video quality** | Variable (720p-1080p, often compressed, 30fps) | You control (1080p60 ideal) |
| **Camera angle** | Usually sideline, often bad for CV | You choose — elevated corner is optimal |
| **Availability** | Not all games are streamed | Always available (you bring it) |
| **AI accuracy impact** | Lower — compression artifacts, bad angles, overlays | Higher — clean feed, consistent angle |
| **Cost** | Free | $300-800 camera + $100-200 tripod |
| **Portability** | N/A | Must carry gear |

### Recommendation: Start with BOTH, but prioritize portable camera

**Phase 1 MVP**: Use existing live streams or post-game clips. This lets you build the software pipeline without hardware investment. You're processing clips manually anyway.

**Phase 2**: Invest in portable camera. This is where real CV accuracy becomes possible. The stream is a fallback, not the primary.

**Why**: Live streams have three fatal problems for CV — (1) compression destroys edge detection, (2) you don't control the angle so player tracking becomes inconsistent game-to-game, (3) graphics overlays and camera cuts break continuous tracking. Your own camera gives you a **consistent, clean, uninterrupted** feed which is mandatory for reliable tracking.

**Hybrid approach**: When a stream exists, still bring your camera. Use the stream as a secondary reference (for scoreboard/clock sync) and your camera as the CV source.

---

## 3. Portable Camera Design

### Recommended Setup

**Camera**: A wide-angle action camera or PTZ camera on a tall tripod.

**Best option for MVP**: **GoPro Hero 12/13 Black** or **Insta360 Ace Pro**
- Why: Wide-angle lens captures full court from corner, 1080p60 or 4K30, USB-C power passthrough, WiFi streaming to Mac mini, small/portable
- Cost: ~$350-400

**Better option (Phase 3+)**: **PTZ Optics or similar USB PTZ camera**
- Why: Optical zoom, wider dynamic range, direct USB/HDMI to Mac mini, designed for this
- Cost: ~$600-1200
- Downside: Heavier, larger, less portable

### Camera Angle

```
                    ┌─────────────────────────────┐
                    │          COURT              │
                    │                             │
                    │                             │
                    │                             │
                    │                             │
                    │                             │
                    │                             │
                    └─────────────────────────────┘
                   ╱
                  ╱  30-45° angle down
                 ╱
              📷 ← CAMERA HERE
              │
          ┌───┴───┐
          │TRIPOD │  (elevated corner, ~8-12 feet high)
          │~10ft  │
          └───────┘
```

**Optimal placement**: Elevated corner position, behind the baseline on the side of your bench, angled to capture the full court. The corner gives you depth — you can see both the width and length of the court, which is critical for zone detection.

**Why NOT sideline center**: Sideline center is what broadcasts use, but it creates occlusion problems — players stack on top of each other from that angle. Corner elevation separates them spatially.

### Specs That Matter

| Parameter | Minimum | Ideal | Why |
|---|---|---|---|
| **Resolution** | 1080p | 1080p (not 4K) | 4K wastes compute; 1080p is plenty for detection. You'll downscale to 720p for inference anyway. |
| **Frame rate** | 30fps | 60fps | 60fps helps with fast motion (drives, fast breaks). 30fps is workable. |
| **FOV** | 100°+ | 120-150° | Must see full court from corner position |
| **Bitrate** | 15 Mbps | 25-40 Mbps | Higher bitrate = less compression = better detection |
| **Connection** | USB-C | USB-C or HDMI capture card | WiFi adds latency and drops frames |

### Power

- Game = ~2.5 hours including warmups
- GoPro internal battery: ~1 hour → **not enough**
- Solution: USB-C power bank (20,000 mAh) or direct power from Mac mini USB-C port
- If using HDMI: camera on its own power, HDMI capture card powered by Mac mini

### Portability Kit

Everything should fit in a single bag:
1. Camera (~200g)
2. Tall monopod/tripod with clamp (~1.5 kg) — a 10ft light stand with a camera mount works
3. USB-C cable (3m) or HDMI cable + capture card
4. Power bank
5. Mac mini + power adapter (~1 kg)
6. Small portable monitor or iPad (optional, for live dashboard)

**Total weight**: ~4-5 kg. Fits in a backpack.

### What a Single Portable Camera Cannot Do

Be honest about limitations:
- **No multi-angle replay** — one perspective only
- **Occlusion is real** — players will block each other, especially in the paint
- **No automatic pan/tilt** — you'll lose a few seconds during fast transitions if you use a very tight angle
- **Inconsistent between games** — different gyms = different heights, different corners, different lighting
- **Player identity from appearance alone is hard** — jersey numbers from a corner angle at 1080p are borderline readable

These are acceptable tradeoffs for an MVP. The system should be designed to work **despite** these limitations.

---

## 4. Edge Processing Design (Mac mini)

### Hardware

**Recommended**: Mac mini M2 Pro or M4 (16GB RAM minimum, 32GB ideal)
- **Why M-series**: The Neural Engine (16-core) runs CoreML models efficiently. PyTorch with MPS backend also works. You get ~15-25 fps inference on YOLO-class models without a GPU.
- **Why not a laptop**: Mac mini is cheaper, fanless under moderate load, always plugged in, and you're not using the screen (headless operation).
- **Storage**: 512GB SSD minimum. A full game at 1080p30 = ~15-20 GB. You'll want to store at least 5-10 games locally before syncing.

### What Runs on the Mac mini

```
┌─────────────────────────────────────────────────────┐
│                  Mac mini (Edge)                     │
│                                                      │
│  ┌──────────────────────────────────────────────┐   │
│  │ 1. VIDEO INGESTION                           │   │
│  │    - FFmpeg captures from USB/HDMI/RTMP       │   │
│  │    - Writes raw video to disk (segments)      │   │
│  │    - Feeds frames to CV pipeline              │   │
│  └──────────────┬───────────────────────────────┘   │
│                 ▼                                     │
│  ┌──────────────────────────────────────────────┐   │
│  │ 2. CV PIPELINE (real-time, ~10-15 fps)       │   │
│  │    - YOLOv8/v9 person detection               │   │
│  │    - Ball detection (separate small model)    │   │
│  │    - ByteTrack/BoTSORT multi-object tracking  │   │
│  │    - Court homography (map pixels → court)    │   │
│  │    - Team classification (jersey color)        │   │
│  └──────────────┬───────────────────────────────┘   │
│                 ▼                                     │
│  ┌──────────────────────────────────────────────┐   │
│  │ 3. EVENT EXTRACTION (near-real-time)          │   │
│  │    - Possession detection (which team has ball)│   │
│  │    - Zone occupancy per team                   │   │
│  │    - Transition vs half-court classification   │   │
│  │    - Shot clock / game clock (if visible)      │   │
│  │    - Team movement centroid + spread           │   │
│  └──────────────┬───────────────────────────────┘   │
│                 ▼                                     │
│  ┌──────────────────────────────────────────────┐   │
│  │ 4. LOCAL STORAGE                              │   │
│  │    - SQLite: events, tracking data, metrics   │   │
│  │    - Video segments: 2-min chunks on disk     │   │
│  │    - Aggregated stats per quarter              │   │
│  └──────────────┬───────────────────────────────┘   │
│                 ▼                                     │
│  ┌──────────────────────────────────────────────┐   │
│  │ 5. LIVE DASHBOARD (localhost:8080)            │   │
│  │    - Flask/FastAPI serving simple web UI       │   │
│  │    - Updates every 5-10 seconds               │   │
│  │    - Accessed via iPad/phone on same WiFi     │   │
│  └──────────────────────────────────────────────┘   │
│                                                      │
└─────────────────────────────────────────────────────┘
```

### Video Ingestion

From USB camera or HDMI capture card using FFmpeg, or in Python using OpenCV:

```python
cap = cv2.VideoCapture(0)  # USB camera
# or
cap = cv2.VideoCapture("rtmp://stream-url")  # live stream
```

The Mac mini simultaneously **records** the full video to disk and **feeds frames** to the CV pipeline. Recording is non-negotiable — you always want the raw video for post-game reprocessing.

### What Should Be Real-Time vs Delayed

| Task | Timing | Why |
|---|---|---|
| Person detection + tracking | Real-time (~10-15 fps) | Feeds everything else |
| Team color classification | Real-time | Needed for team-level metrics |
| Court homography | Calibrated once at setup, refined periodically | Stable camera = stable mapping |
| Zone occupancy heatmap | Updated every 10-15 seconds | Useful live |
| Possession estimation | Near-real-time (5-10s delay) | Requires short temporal window |
| Transition detection | Near-real-time | Needs possession change + movement |
| Player re-identification | **Post-game** | Too expensive and unreliable live |
| Play classification | **Post-game** | Requires full possession context |
| Report generation | **Post-game** | LLM-based, needs cloud |

### Realistic Performance Expectations

On an M2 Pro Mac mini:
- YOLOv8m at 640px: **~20-25 fps** via CoreML
- YOLOv8s at 640px: **~35-45 fps** via CoreML
- Tracking overhead (ByteTrack): **negligible** (~1ms per frame)
- Total pipeline at 1080p input, 640px inference: **15-20 fps realistic**
- This means you process every 2nd-3rd frame from a 30fps source, which is fine

**Memory**: ~4-6 GB for the full pipeline. Leaves plenty for recording and dashboard.

**Thermal**: Mac mini will run warm but won't throttle under this workload. It's designed for sustained loads.

---

## 5. Live Match Mode (Real-Time Insights)

### What Is Realistically Achievable During a Live Game

#### Achievable Live (< 15 second latency)

**1. Team-Level Heat Maps**

```
┌────────────────────────────────┐
│  ██░░░░░░░░░░░░░░░░░░░░░░██  │
│  ██████░░░░░░░░░░░░░░██████  │
│  ██████████░░░░░░██████████  │  "Your team is spending 
│  ░░░░████████████████░░░░░░  │   70% of defensive time
│  ░░░░░░░░████████░░░░░░░░░░  │   in the paint zone"
│  ░░░░░░░░░░████░░░░░░░░░░░░  │
└────────────────────────────────┘
   ▓▓ = high density  ░░ = low density
```

How: Accumulate all tracked person positions (mapped to court coordinates via homography), separated by team color. Bin into court zones. Update every 10-15 seconds. This is a **rolling window** (last 2-3 minutes), not cumulative.

Accuracy: **Good enough**. Even with tracking drops and occlusion, the aggregate pattern is meaningful because you're looking at density, not individual paths.

**2. Zone-Based Movement Patterns**

Divide the court into 6-8 zones:

```
┌──────────┬──────────┬──────────┐
│          │          │          │
│  LEFT    │  PAINT   │  RIGHT   │
│  WING    │          │  WING    │
│          │          │          │
├──────────┼──────────┼──────────┤
│          │          │          │
│  LEFT    │  TOP     │  RIGHT   │
│  CORNER  │  OF KEY  │  CORNER  │
│          │          │          │
└──────────┴──────────┴──────────┘
```

Track: How many seconds per possession each team occupies each zone. This tells you spacing patterns without needing player identity.

**3. Transition vs Half-Court Classification**

Detection logic:
- **Transition**: Ball crosses half court within ~4 seconds of possession change, team centroid moving fast
- **Half-court**: Ball crosses half court slowly or team sets up before action
- **Fast break**: Transition where attacking team outnumbers defense (count players in front court)

Update: Per-possession. Display running ratio: "Opponent: 40% transition, 60% half-court this quarter."

**4. Simple Alerts**

Rule-based triggers pushed to the dashboard:
- "Opponent has scored on 4 of last 5 transition possessions"
- "Your team's defensive spread is collapsing — everyone inside the paint"
- "Opponent favoring right side of court (65% of possessions)"

These require only zone data + simple counters. No ML needed for the rules themselves.

#### Achievable Near-Real-Time (post-quarter, ~2-3 min delay)

- Quarter-over-quarter trend comparisons
- Possession efficiency estimates (if you can detect made baskets — hard but possible with ball trajectory)
- Timeout/dead ball detection and possession count

#### NOT Achievable Live (Post-Game Only)

- Individual player tracking and stats
- Play-type classification (pick and roll, iso, etc.)
- Shot chart generation
- Assist/turnover attribution
- Detailed opponent scouting

### Live Dashboard Design

Served from Mac mini at `localhost:8080`, accessed via iPad on a hotspot network.

```
┌─────────────────────────────────────────────────────┐
│  BASKETBALL INTELLIGENCE — LIVE        Q3  4:32     │
├──────────────────────┬──────────────────────────────┤
│                      │                              │
│   YOUR TEAM HEATMAP  │   OPPONENT HEATMAP           │
│   (last 3 min)       │   (last 3 min)               │
│   ┌────────────┐     │   ┌────────────┐             │
│   │  ▓▓░░░░▓▓  │     │   │  ░░▓▓▓▓░░  │             │
│   │  ▓▓▓▓░░▓▓  │     │   │  ░░▓▓▓▓▓▓  │             │
│   │  ░░▓▓▓▓░░  │     │   │  ▓▓▓▓░░░░  │             │
│   └────────────┘     │   └────────────┘             │
│                      │                              │
├──────────────────────┼──────────────────────────────┤
│  PACE                │  ALERTS                      │
│  Trans: 35% HC: 65%  │  ⚠ Opp 4/5 on transition    │
│  Opp Trans: 55%      │  ⚠ Your paint density: 72%  │
│                      │  ℹ Opp shifted right wing    │
│  ZONES (Opp Offense) │                              │
│  Paint: 45%          │                              │
│  Wings: 30%          │                              │
│  Corners: 25%        │                              │
└──────────────────────┴──────────────────────────────┘
```

### Latency Budget

```
Camera → Mac mini:        ~50ms  (USB/HDMI)
Frame decode:              ~5ms
Detection (YOLO):         ~40ms  (at 640px on M2 Pro)
Tracking (ByteTrack):      ~2ms
Homography transform:      ~1ms
Zone aggregation:          ~1ms
Dashboard update:        5-10s   (batch, not per-frame)
─────────────────────────────────
Total per-frame:          ~100ms
Dashboard refresh:        5-10s
```

The coach sees data that's 5-10 seconds old. That's fine — they're looking at patterns, not reacting to individual plays.

---

## 6. Computer Vision Design

### Model Stack

```
Layer 1: Person Detection
├── Model: YOLOv8m or YOLOv9s (pretrained on COCO)
├── Input: 640x640 (downscaled from 1080p)
├── Output: bounding boxes + confidence for "person" class
├── Speed: ~25 fps on M2 Pro via CoreML
└── Note: COCO-pretrained works out of the box. No fine-tuning needed for detection.

Layer 2: Ball Detection
├── Model: YOLOv8s fine-tuned on basketball datasets
├── Input: 640x640
├── Output: ball bounding box
├── Speed: ~40 fps (smaller model)
└── Note: Ball detection is HARD. Ball is small, fast, often occluded.
          Expect ~60-70% frame-level detection rate.
          Use temporal smoothing (interpolation between detections).

Layer 3: Multi-Object Tracking
├── Algorithm: ByteTrack or BoT-SORT
├── Input: per-frame detections from Layer 1
├── Output: tracked person IDs (persistent across frames)
├── Speed: negligible (~1-2ms)
└── Note: Tracking IDs will drift. Players crossing paths causes ID swaps.
          This is fine for team-level analysis. Fatal for player-level.

Layer 4: Team Classification
├── Method: K-means clustering on jersey color (HSV space)
├── Input: cropped bounding box of each tracked person
├── Process: Extract dominant colors from torso region,
│            cluster into 2-3 groups (team A, team B, referee)
├── Speed: negligible
└── Note: Works well when jerseys are distinct colors.
          Fails when both teams wear similar colors.
          Calibrate at start of each game (semi-manual).

Layer 5: Court Homography
├── Method: Manual calibration (4-point correspondence)
├── Input: 4 known court points clicked in camera view
├── Output: 3x3 homography matrix
├── Process: Map any pixel coordinate → court coordinate (in feet)
├── Speed: one-time computation
└── Note: Do this ONCE per game during setup.
          If camera moves, recalibrate. Fixed tripod = no drift.
```

### How to Track Players Without Reliable Identity

**You don't need player identity for MVP.** This is the most important architectural decision.

Instead of tracking "Player #23 is in the left wing," you track:
- "A player on Team A is in the left wing"
- "Team A has 3 players in the paint"
- "Team A's centroid is at (35, 22) on the court"

This gives you:
- Team heat maps (aggregate positions)
- Team spacing (convex hull area of team positions)
- Zone occupancy by team
- Movement flow by team

All of these are **useful coaching insights** without knowing which player is which.

### Player Identity — When to Add It

Phase 5+ only. Approaches in order of practicality:

1. **Manual tagging**: Coach or assistant tags players in first frame. System tracks from there. Re-tag on ID swap. Realistic but labor-intensive.
2. **Jersey number OCR**: Works sometimes from good angles at high resolution. Unreliable from a corner angle at 1080p. Don't depend on this.
3. **Re-ID models**: Appearance-based re-identification using a small embedding network. Needs fine-tuning on basketball data. Phase 6 territory.
4. **Pose + anthropometrics**: Height estimation from bounding box + homography. Can distinguish tall center from short guard. Rough but useful as a supplementary signal.

### Team Classification Detail

```python
# Pseudocode for team classification
def classify_team(bbox, frame):
    # Crop upper body (jersey region)
    x1, y1, x2, y2 = bbox
    jersey_crop = frame[y1:y1+(y2-y1)//2, x1:x2]  # top half of bbox
    
    # Convert to HSV, compute histogram
    hsv = cv2.cvtColor(jersey_crop, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1], None, [30, 32], [0, 180, 0, 256])
    
    # At game start, run k-means (k=3) on all detected persons
    # Cluster 1 = Team A, Cluster 2 = Team B, Cluster 3 = Refs
    # For subsequent frames, assign to nearest cluster centroid
    return nearest_cluster(hist, centroids)
```

**Initialization:** At the start of the game, accumulate jersey crops for 30 seconds, run k-means, manually confirm which cluster is which team (one-time click). The clusters are stable because jersey colors don't change mid-game.

### Court Mapping (Homography)

```
Pixel space (camera)          Court space (real world)
┌─────────────────┐           ┌─────────────────┐
│    .A         .B│           │A               B│
│                 │    H      │                 │
│                 │  ─────►   │                 │
│                 │           │                 │
│  .C          .D │           │C               D│
└─────────────────┘           └─────────────────┘

H = homography matrix (3x3)
Maps any pixel (x,y) → court coordinate (X,Y) in feet
```

**Calibration workflow (semi-manual, done once per game):**
1. Display first frame of video
2. Click 4 known court points (e.g., four corners of the half-court line, or free-throw line intersections)
3. System computes homography matrix
4. All subsequent detections are transformed to court coordinates
5. Takes 30 seconds. Do it during warmups.

**If the camera moves:** Homography breaks. Solutions:
- Lock the camera down tight (fluid head + no one bumps the tripod)
- Detect drift via court line positions and re-calibrate automatically (Phase 5)
- For MVP: if it moves, re-calibrate at the next break

### What NOT to Attempt Early

| Don't Attempt | Why |
|---|---|
| Individual player identification | Jersey OCR is a hard problem. Team-level data is more valuable initially anyway. |
| Ball tracking through dribbles/passes | Ball is 9.4" diameter, often occluded by hands/bodies, moves 20+ mph. Detection rate will be <50%. |
| Play classification (PnR, iso, motion) | Requires reliable player tracking + understanding of offensive sets. Years of R&D at companies like Second Spectrum. |
| Automatic shot detection + make/miss | Requires ball tracking near rim + trajectory analysis. Very hard from single sideline camera. |
| 3D pose estimation | Overkill and compute-heavy. You need positions, not body angles. |
| Automatic scorekeeping | OCR on scoreboard is possible but fragile. Manual input is more reliable. |

---

## 7. Data Flow and Storage

### Full Pipeline

```
VIDEO FRAMES (1080p30/60)
    │
    ▼
┌─────────────────────────┐
│ DETECTION               │  Output: List of bounding boxes per frame
│ (YOLO, ~15-20 fps)      │  [{x, y, w, h, conf, class}, ...]
└───────────┬─────────────┘
            ▼
┌─────────────────────────┐
│ TRACKING                │  Output: Tracked objects with persistent IDs
│ (ByteTrack)             │  [{track_id, x, y, w, h, team}, ...]
└───────────┬─────────────┘
            ▼
┌─────────────────────────┐
│ COURT MAPPING           │  Output: Court coordinates per track
│ (Homography)            │  [{track_id, court_x, court_y, team}, ...]
└───────────┬─────────────┘
            ▼
┌─────────────────────────┐
│ EVENT EXTRACTION        │  Output: Structured events
│ (Rule-based logic)      │  {type: "possession_change", team: "A",
│                         │   timestamp: 1234, zone: "left_wing"}
└───────────┬─────────────┘
            ▼
┌─────────────────────────┐
│ AGGREGATION             │  Output: Periodic summaries
│ (10-15 sec windows)     │  {team_a_heatmap: [...], team_b_zones: {...},
│                         │   transition_rate: 0.35, ...}
└───────────┬─────────────┘
            ▼
    ┌───────┴────────┐
    ▼                ▼
LOCAL STORAGE    LIVE DASHBOARD
(SQLite + disk)  (localhost web)
    │
    ▼ (post-game sync)
CLOUD STORAGE
(S3 + Postgres)
    │
    ▼
REPORT GENERATION
(Claude API + templates)
    │
    ▼
COACH DASHBOARD
(web app)
```

### Storage Schema (Local — SQLite)

```sql
-- Raw tracking data (high volume, ~10-20 rows per frame)
CREATE TABLE tracking_data (
    id INTEGER PRIMARY KEY,
    game_id TEXT,
    frame_number INTEGER,
    timestamp_ms INTEGER,
    track_id INTEGER,
    team TEXT,  -- 'A', 'B', 'ref', 'unknown'
    court_x REAL,
    court_y REAL,
    bbox_x REAL, bbox_y REAL, bbox_w REAL, bbox_h REAL,
    confidence REAL
);

-- Events (derived from tracking, ~5-20 per minute)
CREATE TABLE events (
    id INTEGER PRIMARY KEY,
    game_id TEXT,
    timestamp_ms INTEGER,
    event_type TEXT,  -- 'possession_change', 'transition', 'timeout', etc.
    team TEXT,
    zone TEXT,
    metadata JSON  -- flexible additional data
);

-- Aggregated metrics (per-window summaries)
CREATE TABLE metrics (
    id INTEGER PRIMARY KEY,
    game_id TEXT,
    period TEXT,  -- 'Q1', 'Q2', etc. or time window
    window_start_ms INTEGER,
    window_end_ms INTEGER,
    team TEXT,
    metric_type TEXT,  -- 'heatmap', 'zone_occupancy', 'transition_rate'
    value JSON
);

-- Games
CREATE TABLE games (
    id TEXT PRIMARY KEY,
    date TEXT,
    opponent TEXT,
    our_team TEXT,
    location TEXT,
    video_path TEXT,
    homography_matrix JSON,
    team_colors JSON,  -- calibrated jersey colors
    synced_to_cloud BOOLEAN DEFAULT FALSE
);
```

### What Lives Where

| Data | Local (Mac mini) | Cloud |
|---|---|---|
| Raw video | Yes (full game, segmented) | Optional (upload overnight if bandwidth allows) |
| Tracking data | Yes (SQLite) | Yes (synced post-game) |
| Events | Yes (SQLite) | Yes (synced post-game) |
| Aggregated metrics | Yes (SQLite) | Yes (synced post-game) |
| Game metadata | Yes | Yes |
| Generated reports | No | Yes (generated in cloud) |
| Clips (tagged) | Yes (local references) | Yes (uploaded with tags) |

### Clip Organization

```
/games/
  /2026-04-07_vs_TeamName/
    /raw/
      game_001.mp4  (2-min segment)
      game_002.mp4
      ...
    /clips/
      transition_q2_0432.mp4  (auto-tagged)
      paint_zone_q3_0215.mp4
    /data/
      tracking.db   (SQLite)
      calibration.json
      metrics.json
    /reports/
      postgame_report.md
      postgame_report.pdf
```

---

## 8. Reporting Layer

### Three Report Types

#### 1. Live Coach Insights (During Game)

**Delivery**: Dashboard on iPad/phone via local WiFi
**Update frequency**: Every 10-15 seconds
**Content**:
- Team heat maps (rolling 3-minute window)
- Transition vs half-court ratio
- Zone occupancy breakdown
- Pattern alerts
**Generation method**: 100% rule-based. No LLM. No cloud dependency.

```python
# Example alert rules
def check_alerts(metrics, window_minutes=3):
    alerts = []
    
    if metrics.opponent_transition_score_rate > 0.6:
        alerts.append("Opponent scoring on 60%+ of transitions")
    
    if metrics.our_paint_occupancy > 0.7:
        alerts.append("Your defense is collapsing — 70%+ in paint")
    
    if metrics.opponent_right_side_pct > 0.65:
        alerts.append("Opponent favoring right side (65%)")
    
    return alerts
```

#### 2. Postgame Coach Report

**Delivery**: PDF or web page, available 30-60 min after game
**Content**:
- Full-game heat maps by quarter
- Possession breakdown
- Transition vs half-court stats with efficiency notes
- Zone analysis (where did opponent attack most)
- Key trend shifts (e.g., "Q3 opponent shifted to right wing after your zone adjustment")
- Narrative summary
**Generation method**: Stats computed from structured data (rule-based), narrative written by Claude API (LLM).

```
POSTGAME REPORT — vs Lincoln High — April 7, 2026
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

OVERALL SUMMARY
Lincoln ran 45% transition offense, highest we've seen this season.
Their transition efficiency dropped from 68% in Q1-Q2 to 31% in Q3-Q4
after you shifted to a full-court press.

QUARTER BREAKDOWN
Q1: Lincoln dominated paint zone (58% occupancy). Your perimeter
    defense left right wing open — they exploited it 7 times.
Q2: Similar pattern but your zone tightened. Paint occupancy dropped
    to 42%.
Q3: Major shift. Your press forced 8 backcourt turnovers. Lincoln's
    half-court offense was disorganized — spacing collapsed.
Q4: Lincoln adjusted with skip passes but your zone held.

[Heat maps for each quarter]

KEY INSIGHT
Lincoln's half-court offense is weak when forced to play slow.
Their motion offense breaks down when denied the right wing entry.
Recommendation: Start in press next matchup.
```

**LLM prompt structure**:

```python
prompt = f"""
You are a basketball analytics assistant generating a postgame
coach report. Use the following structured data to write a concise,
actionable report. Focus on patterns and recommendations.

Game: {game_metadata}
Quarter-by-quarter metrics:
{json.dumps(quarter_metrics, indent=2)}

Key events:
{json.dumps(key_events)}

Write a 300-500 word report with:
1. One-paragraph summary
2. Quarter-by-quarter breakdown (2-3 sentences each)
3. 2-3 key insights with tactical recommendations
"""
```

#### 3. Opponent Scouting Report

**Delivery**: PDF or web page, generated from multiple games against same opponent
**Content**:
- Opponent tendencies across multiple games
- Preferred zones, transition rate, spacing patterns
- Game-to-game consistency vs variability
- Recommended defensive approach
**Generation method**: Stats aggregated across games (rule-based), narrative and recommendations by Claude API.
**Data sources**: CV data from your games against them + GameChanger stats (when available) + manually input notes.

### What Should Be Rule-Based vs Stats-Based vs LLM-Generated

| Component | Method | Why |
|---|---|---|
| Heat map generation | Rule-based (spatial binning) | Deterministic, fast |
| Zone occupancy % | Stats computation | Simple aggregation |
| Transition classification | Rule-based (velocity + possession change) | Needs to be real-time |
| Live alerts | Rule-based (threshold triggers) | Must be reliable, no hallucination |
| Trend detection | Stats-based (quarter comparison) | Objective measurement |
| Narrative summaries | LLM (Claude API) | Natural language synthesis |
| Tactical recommendations | LLM (Claude API) with stats context | Requires reasoning over patterns |
| Cross-game scouting | LLM (Claude API) with aggregated stats | Requires synthesis across datasets |

**Rule**: Never use LLM for anything that needs to be real-time or deterministic. Use LLM only for post-hoc narrative generation where latency and occasional imprecision are acceptable.

---

## 9. Phase-by-Phase Build Plan

### Phase 1: Postgame Analysis from Clips + Manual Input
**Timeline**: Weeks 1-4

| Aspect | Detail |
|---|---|
| **Features** | Upload clips, add manual annotations, generate basic reports |
| **Inputs** | 20-30 second highlight clips (MP4), GameChanger box scores (manual CSV/paste), coach notes (free text) |
| **Outputs** | Structured game summaries, basic opponent profiles, LLM-generated postgame narrative |
| **Manual** | Everything: clip upload, tagging ("this is a transition bucket"), stats entry |
| **Automated** | Report generation from structured inputs (LLM), template formatting |
| **Stack** | Python CLI or simple web app, SQLite, Claude API |
| **Difficulty** | Low — no CV, no hardware, pure software |
| **Success criteria** | Coach receives a useful postgame report within 1 hour of data entry. Coach says "this saves me time." |

**What you're really building**: The data model and report templates. This is the foundation everything else plugs into.

```
PHASE 1 FLOW:
  Coach records game (phone video / existing stream)
      │
      ▼
  After game: upload 10-15 clips + enter box score
      │
      ▼
  System organizes clips, generates report with LLM
      │
      ▼
  Coach reviews postgame report (PDF/web)
```

---

### Phase 2: Structured Reporting System
**Timeline**: Weeks 5-8

| Aspect | Detail |
|---|---|
| **Features** | Persistent game database, multi-game opponent profiles, trend tracking, scouting report generation |
| **Inputs** | Same as Phase 1 + data accumulates across games |
| **Outputs** | Opponent scouting reports (cross-game), season trend dashboard, game comparison views |
| **Manual** | Data entry still manual, but templated (forms not free text) |
| **Automated** | Cross-game aggregation, trend detection, scouting report generation |
| **Stack** | Web app (Next.js or similar), Postgres, Claude API, simple charts |
| **Difficulty** | Medium — standard web dev, data modeling |
| **Success criteria** | Coach can pull up opponent scouting report before a game and it contains actionable tendencies from prior matchups. |

---

### Phase 3: Clip Tagging + Pattern Detection
**Timeline**: Weeks 9-14

| Aspect | Detail |
|---|---|
| **Features** | Upload full game video, basic CV extracts possession timestamps, auto-segment into clips, auto-tag transition vs half-court |
| **Inputs** | Full game recordings (post-game upload), can be from phone, stream recording, or camera |
| **Outputs** | Auto-segmented possessions, tagged clips, enhanced stats from video |
| **Manual** | Coach reviews/corrects auto-tags, adds context |
| **Automated** | Possession segmentation, transition classification, basic zone detection |
| **Stack** | Python CV pipeline (YOLOv8 + ByteTrack), runs post-game on Mac mini or cloud VM |
| **Difficulty** | Medium-High — first real CV work, but post-game (not real-time) |
| **Success criteria** | 70%+ of possessions correctly segmented. Coach corrects <30% of auto-tags. System processes a full game in <45 minutes. |

---

### Phase 4: Portable Camera + Live Processing (Mac Mini)
**Timeline**: Weeks 15-22

| Aspect | Detail |
|---|---|
| **Features** | Bring camera + Mac mini to games, real-time team heat maps, zone occupancy, transition alerts on local dashboard |
| **Inputs** | Live video from portable camera via USB/HDMI |
| **Outputs** | Live dashboard (iPad), auto-recorded game video, post-game auto-processed stats |
| **Manual** | Physical setup (camera, tripod, Mac mini), court calibration (click 4 points), team color selection |
| **Automated** | Live CV pipeline, real-time tracking, heatmap generation, alerts, auto-recording |
| **Stack** | Full edge pipeline on Mac mini, local web dashboard, same CV from Phase 3 but optimized for speed |
| **Difficulty** | High — real-time CV, hardware setup, reliability under game conditions |
| **Success criteria** | System runs for a full game without crashing. Dashboard shows meaningful heat maps. Coach glances at iPad 3+ times during game and finds it useful. Setup takes <10 minutes. |

**Setup checklist for game day:**
1. Set up tripod in corner (3 min)
2. Mount camera, connect to Mac mini (2 min)
3. Power on Mac mini, start pipeline (1 min)
4. Calibrate court — click 4 points on screen (2 min)
5. Select team colors — click on each team's jersey (1 min)
6. Pipeline running, dashboard live

---

### Phase 5: Improved CV + Semi-Automation
**Timeline**: Weeks 23-34

| Aspect | Detail |
|---|---|
| **Features** | Automatic court detection, better tracking through occlusion, ball detection, rough shot detection, per-player tracking (experimental) |
| **Inputs** | Same camera setup, possibly add scoreboard OCR |
| **Outputs** | More detailed metrics: ball movement patterns, shot attempts per zone, individual player heat maps (with manual identity assignment) |
| **Manual** | Player identity assignment ("Track #7 is player X"), review/correct automated events |
| **Automated** | Court auto-detection, improved tracking, ball tracking, basic shot detection |
| **Stack** | Fine-tuned CV models, possibly custom training data from your own games |
| **Difficulty** | High — model fine-tuning, accuracy tuning, edge cases |
| **Success criteria** | Court auto-detected in 90%+ of setups. Ball detected 60%+ of frames. Player tracking maintains identity for 80%+ of a quarter without intervention. |

---

### Phase 6: Scalable Repeatable Portable Setup
**Timeline**: Weeks 35-48+

| Aspect | Detail |
|---|---|
| **Features** | One-click setup, automatic everything, coach-facing mobile app, shareable reports, potential multi-team deployment |
| **Inputs** | Plug in camera → everything auto-configures |
| **Outputs** | Full live intelligence dashboard, instant postgame reports, season-long analytics, opponent database |
| **Manual** | Physical setup only (camera + tripod) |
| **Automated** | Everything else |
| **Stack** | Polished product, mobile app, cloud backend with user management |
| **Difficulty** | Very high — productization, reliability, UX polish |
| **Success criteria** | A coach who has never used the system can set up and run it with a 5-minute tutorial. Reports are useful without any manual corrections. |

---

## 10. Tradeoffs and Risks

### Edge vs Cloud Processing

| Factor | Edge (Mac mini) | Cloud (GPU VM) |
|---|---|---|
| **Latency** | ~100ms (local) | 500ms-2s (depends on connectivity) |
| **Reliability** | Works offline. No WiFi dependency. | Dies without internet. Gym WiFi is often terrible. |
| **Cost** | $600-800 one-time (Mac mini) | $0.50-2/hr GPU VM (~$50-200/month) |
| **CV performance** | 15-20 fps (M2 Pro) | 30-60 fps (T4/A10G) |
| **Scalability** | One device per game | Can process multiple streams |
| **Maintenance** | Physical hardware to carry | No hardware management |

**Verdict**: Edge for live games (reliability is non-negotiable). Cloud for post-game reprocessing and report generation.

### Portable Camera vs Existing Live Stream

| Factor | Portable Camera | Existing Stream |
|---|---|---|
| **CV accuracy** | Higher (you control angle, quality, no overlays) | Lower (compression, bad angles, graphics) |
| **Consistency** | You aim for same angle each game | Different streams = different everything |
| **Setup effort** | 5-10 min per game | 0 min (if stream exists) |
| **Availability** | Always (you bring it) | Not always available |
| **Cost** | $300-800 one-time | Free |

**Verdict**: Start with streams/clips (Phase 1-2), transition to portable camera (Phase 4+). Use streams as fallback.

### Biggest Risks and Mitigations

| Risk | Severity | Likelihood | Mitigation |
|---|---|---|---|
| **Setup inconsistency** — Different angle each game degrades tracking | High | High | Create a setup checklist. Use a marked tripod height. Always go to the same corner. Build angle-tolerance into the homography step. |
| **Tracking accuracy** — ID swaps, lost tracks, occlusion | Medium | High | Design around team-level (not player-level) metrics. Team aggregate is tolerant of individual tracking errors. |
| **Mac mini thermal/performance** — Sustained 2-hour load | Low | Low | M-series chips handle sustained loads well. Test with a full simulated game before first real deployment. |
| **Camera angle variation** — Different gyms, different corners | Medium | High | Build a flexible calibration system. Accept that some gyms will give better results. Log quality metrics per game. |
| **Ball detection failures** — Small, fast, occluded | Medium | High | Don't make ball detection critical-path for MVP. Zone and team metrics work without ball. Add ball as enhancement. |
| **Coach doesn't look at it** — Dashboard not useful enough | High | Medium | Start with Phase 1 (reports, not real-time). Validate that coaches want this BEFORE building the hardware setup. |
| **Gym WiFi for dashboard** — Can't access localhost from iPad | Medium | Medium | Run a portable hotspot from the Mac mini or your phone. Dashboard traffic is minimal (<1 Mbps). |
| **GameChanger data gaps** — Not all teams have stats | Low | High | Design system to work with ZERO external data. GameChanger is supplementary, not required. |

---

## 11. Final Recommendation

### What to Build FIRST

**Build Phase 1 — the postgame report system — before buying any hardware.**

Here's why:
1. It validates that coaches actually want structured reports (and what format they prefer)
2. It forces you to define the data model, report templates, and LLM prompts that everything else builds on
3. It costs $0 in hardware — just your time + Claude API credits (~$5-20/month)
4. It produces real value immediately — coaches get better postgame analysis
5. If coaches don't find value in structured reports, they won't find value in live dashboards either

### Is Mac Mini Sufficient for MVP?

**Yes, absolutely.** An M2 Pro Mac mini is more than sufficient through Phase 5. The Neural Engine + unified memory architecture handles YOLO inference + tracking + recording + dashboard serving without breaking a sweat.

Buy the Mac mini when you enter Phase 3 (post-game video processing). You'll use it first as a post-game processing box, then graduate it to the live edge device in Phase 4.

### Portable Camera or Software First?

**Software first.** The portable camera purchase should happen when you start Phase 4. Until then, you're working with existing clips, stream recordings, and phone recordings. The camera is a Phase 4 investment.

### Realistic 30-Day MVP

**Week 1-2: Foundation**
- Define data model (games, clips, stats, events)
- Build CLI or simple web form for data entry
- Set up SQLite database
- Build 3 report templates (postgame, opponent scout, trend summary)
- Integrate Claude API for narrative generation

**Week 3: Integration**
- Ingest a real game's data (manual entry from GameChanger + coach notes)
- Generate first real postgame report
- Generate first opponent scouting report
- Get coach feedback

**Week 4: Polish + Second Game**
- Iterate on report format based on feedback
- Process a second game
- Build cross-game comparison
- Demonstrate trend detection across 2 games

**30-Day Deliverable**: A working system where a coach enters a game's stats and notes (10-15 minutes of work), and receives a postgame report + opponent profile update within 5 minutes. All software. No camera. No CV. But immediately useful.

### The Honest Truth

The CV + live processing system (Phases 4-6) is a 6-12 month project to get reliable. But the reporting system (Phases 1-2) can deliver real coaching value in 30 days. Start there. The hardware and CV are how you scale, but the reports are the product. If the reports aren't valuable, the fanciest CV pipeline in the world won't save you.

**Build the brain before the eyes.**
