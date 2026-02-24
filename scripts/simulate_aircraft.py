#!/usr/bin/env python3
"""
scripts/simulate_aircraft.py
Simulates live aircraft by writing to aircraft.json every 2 seconds.
Mimics dump1090 output format so the ingest script reads it normally.
Aircraft randomly appear and disappear to simulate real traffic patterns.

Usage: python scripts/simulate_aircraft.py
"""

import json
import math
import os
import random
import time
from pathlib import Path

DATA_FILE = Path(__file__).parent.parent / "web" / "static" / "data" / "aircraft.json"

POLL_SECONDS = 2

CENTER_LAT = 64.13
CENTER_LON = -21.94

DUMMY_AIRCRAFT = [
    {"hex": "4cc581", "flight": "ICE501  ", "category": "A3", "squawk": "2143"},
    {"hex": "4cc4d1", "flight": "ICE48R  ", "category": "A2", "squawk": "2366"},
    {"hex": "4cc2a6", "flight": "ICE63L  ", "category": "A4", "squawk": "3441"},
    {"hex": "3c6444", "flight": "DLH456  ", "category": "A3", "squawk": "1234"},
    {"hex": "a12345", "flight": "AAL789  ", "category": "A3", "squawk": "5678"},
    {"hex": "e12345", "flight": "RYR001  ", "category": "A2", "squawk": "4321"},
    {"hex": "4ac8a8", "flight": "",          "category": "A5", "squawk": "0000"},
    {"hex": "4cc547", "flight": "",          "category": "A3", "squawk": "0000"},
]

# How long aircraft stay visible/hidden (in ticks)
MIN_VISIBLE_TICKS = 30   # ~1 minute
MAX_VISIBLE_TICKS = 150  # ~5 minutes
MIN_HIDDEN_TICKS = 10    # ~20 seconds
MAX_HIDDEN_TICKS = 60    # ~2 minutes

states = {}


def init_state(ac):
    angle = random.uniform(0, 2 * math.pi)
    radius = random.uniform(0.05, 0.25)
    return {
        "lat": CENTER_LAT + radius * math.sin(angle),
        "lon": CENTER_LON + radius * math.cos(angle),
        "track": random.uniform(0, 360),
        "alt_baro": random.choice([1000, 3000, 5000, 8000, 10000, 15000, 30000, 35000]),
        "gs": random.uniform(180, 450),
        "has_position": ac["flight"] != "",
        "messages": random.randint(100, 500),
        "seen": 0.0,
        "seen_pos": 0.0,
        # visibility state
        "visible": random.choice([True, False]),  # start randomly visible or not
        "ticks_remaining": random.randint(MIN_VISIBLE_TICKS, MAX_VISIBLE_TICKS),
    }


def update_visibility(state):
    """Toggle aircraft visibility when timer runs out."""
    state["ticks_remaining"] -= 1

    if state["ticks_remaining"] <= 0:
        state["visible"] = not state["visible"]
        if state["visible"]:
            # just appeared - reset position near center
            state["ticks_remaining"] = random.randint(MIN_VISIBLE_TICKS, MAX_VISIBLE_TICKS)
            state["lat"] = CENTER_LAT + random.uniform(-0.2, 0.2)
            state["lon"] = CENTER_LON + random.uniform(-0.3, 0.3)
            state["track"] = random.uniform(0, 360)
            state["alt_baro"] = random.choice([1000, 3000, 5000, 8000, 10000, 15000, 30000, 35000])
        else:
            state["ticks_remaining"] = random.randint(MIN_HIDDEN_TICKS, MAX_HIDDEN_TICKS)

    return state


def move(state):
    if not state["has_position"]:
        state["messages"] += random.randint(1, 10)
        state["seen"] += POLL_SECONDS
        return state

    track_rad = math.radians(state["track"])
    speed = state["gs"] * 0.00001
    #0.0000025

    state["lat"] += speed * math.cos(track_rad)
    state["lon"] += speed * math.sin(track_rad)
    state["track"] = (state["track"] + random.uniform(-2, 2)) % 360
    state["alt_baro"] += random.randint(-100, 100)
    state["alt_baro"] = max(500, state["alt_baro"])
    state["messages"] += random.randint(1, 10)
    state["seen"] = round(random.uniform(0, 1), 1)
    state["seen_pos"] = state["seen"]

    # Wrap around if too far
    if abs(state["lat"] - CENTER_LAT) > 0.5 or abs(state["lon"] - CENTER_LON) > 0.8:
        state["lat"] = CENTER_LAT + random.uniform(-0.1, 0.1)
        state["lon"] = CENTER_LON + random.uniform(-0.1, 0.1)
        state["track"] = random.uniform(0, 360)

    return state


def build_aircraft_json(aircraft_list, states):
    aircraft = []

    for ac in aircraft_list:
        hex_ = ac["hex"]
        state = states[hex_]

        if not state["visible"]:
            continue

        entry = {
            "hex": hex_,
            "messages": state["messages"],
            "seen": state["seen"],
            "rssi": round(random.uniform(-30, -10), 1),
            "mlat": [],
            "tisb": [],
        }

        if ac["flight"]:
            entry["flight"] = ac["flight"]

        if ac["category"]:
            entry["category"] = ac["category"]

        if ac["squawk"] != "0000":
            entry["squawk"] = ac["squawk"]

        if state["has_position"]:
            entry.update({
                "lat": round(state["lat"], 6),
                "lon": round(state["lon"], 6),
                "alt_baro": state["alt_baro"],
                "alt_geom": state["alt_baro"] - 200,
                "track": round(state["track"], 1),
                "gs": round(state["gs"], 1),
                "seen_pos": state["seen_pos"],
                "nic": 8,
                "rc": 186,
                "version": 2,
                "nic_baro": 1,
                "nac_p": 10,
                "nac_v": 1,
                "sil": 3,
                "sil_type": "perhour",
                "gva": 2,
                "sda": 2,
                "emergency": "none",
            })

        aircraft.append(entry)

    return {
        "now": time.time(),
        "messages": sum(s["messages"] for s in states.values()),
        "aircraft": aircraft,
    }


def run():
    print(f"Simulator writing to: {DATA_FILE}")
    print(f"Simulating up to {len(DUMMY_AIRCRAFT)} aircraft, updating every {POLL_SECONDS}s")
    print("Press Ctrl+C to stop\n")

    for ac in DUMMY_AIRCRAFT:
        states[ac["hex"]] = init_state(ac)

    tick = 0
    while True:
        for ac in DUMMY_AIRCRAFT:
            states[ac["hex"]] = update_visibility(states[ac["hex"]])
            if states[ac["hex"]]["visible"]:
                states[ac["hex"]] = move(states[ac["hex"]])

        payload = build_aircraft_json(DUMMY_AIRCRAFT, states)
        DATA_FILE.write_text(json.dumps(payload, indent=2))

        tick += 1
        visible = [ac["hex"] for ac in DUMMY_AIRCRAFT if states[ac["hex"]]["visible"]]
        print(f"[tick {tick}] {len(visible)}/{len(DUMMY_AIRCRAFT)} aircraft visible: {visible}")

        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    run()