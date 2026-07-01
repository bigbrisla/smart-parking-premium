# Smart Parking Premium

A parking management system built around the concept of a **Digital Twin**: the
real-time virtual representation of the physical state of the parking (slot by slot),
which enables all the downstream features.

Scenario: Gran Reno shopping mall (Bologna) + a neighboring federated parking.

> Note: the code, comments and documentation are in English; the **bot and dashboard
> UI are intentionally in Italian** (the live demo is presented in Italian).

## Architecture

Two levels, with a clear separation between what is IoT/local and what requires the internet.

```
EDGE / LOCAL (works OFFLINE)                  CLOUD / FEDERATION (requires internet)
  webcam + mockup                              Telegram bot (end user)
   -> vision -> ROI mapping                    federation between Digital Twins of
   -> Digital Twin (real-time slot state)       different owners: exchange of ONLY
  car GPS position                              the aggregate "X free spots"
   -> Haversine -> barrier unlock (simulated)
```

Each parking is an identical **instance** of the backend; only the configuration file
(`config/*.yaml`) changes. The instances talk to each other over HTTP, exchanging only
the aggregate availability, never the detailed state (a realistic B2B boundary).

## Features

- **Digital Twin core** — in-memory, thread-safe slot state with a 3-state machine
  (`FREE` / `OCCUPIED` / `RESERVED`) and explicit precedence rules.
- **Vision → Twin** — a webcam frames a paper mockup; the occupancy is detected and
  the twin is updated in real time. The detector is **pluggable** (default: classic CV;
  optional: YOLO). Pretrained YOLOv11 does **not** recognize the top-down toy cars
  (measured: 0 detections), so the robust baseline is classic computer vision. The CV
  detector is hardened against **shadows** (HSV suppression) and the **hand** moving
  the cars (YCrCb skin detection + border-blob removal + temporal debounce).
- **GPS + Haversine + barrier** — the distance from the entrance is computed with the
  hand-implemented Haversine formula; under a threshold the (simulated) barrier opens.
  It can require an active reservation (`unlock_requires_reservation`).
- **Telegram bot** — availability, reservation (inline keyboard), cancellation, GPS
  position, plate; parking switch (`/parcheggio`) discovered via federation.
- **B2B federation** — `/suggest` proposes the neighboring parking when full.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt          # includes YOLO/OpenCV (heavy download)
# For the edge level without vision, these are enough: fastapi uvicorn pydantic pyyaml httpx
```

## How to run

### 1. Calibrate the slots
Automatic calibration from a photo/webcam of the EMPTY mockup (black rectangles on
white paper), then paste the printed YAML into `config/granreno.yaml`:
```bash
python scripts/auto_calibrate.py --webcam 0 --layout rows
# manual alternative (draw the ROIs with the mouse):
python scripts/calibrate_roi.py --webcam 0
```

### 2. Start an edge instance
```bash
python scripts/run_edge.py --config config/granreno.yaml
# Dashboard: http://127.0.0.1:8001/   |   API docs: http://127.0.0.1:8001/docs
```
The default detection is **classic CV**: at startup (with the mockup EMPTY) it captures
the background; then each car placed in a ROI marks the slot as occupied. If the
lighting/framing changes, press "Cattura sfondo" in the dashboard or `POST /vision/reference`.

> Note: `scripts/spike_detect.py` remains to test YOLO on the mockup. It was verified
> that pretrained YOLOv11 does not see the toy cars -> that is why the default is CV.

### 3. Barrier unlock demo (GPS via Haversine, offline)
```bash
python scripts/simulate_gps.py --config config/granreno.yaml
```

### 4. Federation (two instances, two terminals)
```bash
python scripts/run_edge.py --config config/granreno.yaml   # port 8001 (with webcam)
python scripts/run_edge.py --config config/ikea.yaml       # port 8002 (vision off)
# The Gran Reno dashboard shows IKEA's availability. /suggest proposes the
# alternative when the parking is full.
```
The IKEA instance has vision disabled (a single laptop = a single webcam): its state is
driven by hand from the dashboard or via `POST /twin/debug/occupy`.

### 5. Telegram bot
Create a bot with @BotFather, put the token in `.env` (see `.env.example`), then:
```bash
python scripts/run_bot.py                       # connects to EDGE_URL (default :8001)
python scripts/run_bot.py --edge-url http://127.0.0.1:8001
```
Commands: `/parcheggio` `/disponibilita` `/prenota` `/annulla` `/posizione` `/vai <lat> <lon>` `/targa`.
When the parking is full the bot automatically proposes the federated parking.

## Main endpoints

| Method | Endpoint | Level | Description |
|--------|----------|-------|-------------|
| GET  | `/twin/state` | edge | detailed state of all slots |
| GET  | `/availability` | edge | aggregate availability |
| POST | `/reservations` | cloud | reserve a slot (-> RESERVED) |
| DELETE | `/reservations/{id}` | cloud | cancel a reservation |
| POST | `/vehicle/position` | edge | GPS position -> Haversine -> barrier |
| GET  | `/barrier` | edge | barrier state |
| POST | `/vision/reference` | edge | (re)capture the empty background (CV method) |
| GET  | `/federation/availability` | cloud | shared B2B aggregate |
| GET  | `/federation/peers` | cloud | availability of the federated parkings |
| GET  | `/suggest` | cloud | suggest alternatives when full |
| POST | `/twin/debug/occupy` | dev | force state without a webcam |

## Structure

```
src/
  common/config.py        YAML config loading + .env loader
  edge/
    geo/haversine.py      Haversine formula (by hand)
    twin/                 models, store (state+transitions), service (facade)
    barrier/simulator.py  simulated barrier
    vision/               camera, detector (YOLO), roi, occupancy (CV), approach
    runner.py             loop camera->detect->twin (+ approach tracker)
  api/                    FastAPI: main + routes + dashboard + MJPEG stream
  federation/client.py    queries the peers (aggregate only)
  bot/                    Telegram bot: client.py (EdgeClient) + handlers + bot
scripts/                  run_edge, run_bot, auto_calibrate, calibrate_roi,
                          simulate_gps, list_cameras, spike_detect
web/dashboard.html        live dashboard
docs/                     ARCHITETTURA.md, DEMO.md, SCALETTA_VIDEO.md
tests/                    Haversine, store, service
```

## Slot state machine

`FREE` ⇄ `OCCUPIED` (from the sensor) and `FREE` → `RESERVED` (from the bot).
A reservation "protects" the slot until the expected car arrives: when the sensor
detects the car in a `RESERVED` slot, it becomes `OCCUPIED` (reservation consumed).
Logic in `src/edge/twin/store.py`.
