#!/usr/bin/env python3
"""Generate a large US freight loads board."""

from __future__ import annotations

import json
import random
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "loads.json"

CITIES = [
    ("Los Angeles, CA", ["LA", "LAX"]),
    ("Ontario, CA", ["Ontario"]),
    ("San Diego, CA", ["SAN"]),
    ("San Francisco, CA", ["SF", "SFO"]),
    ("Sacramento, CA", ["SAC"]),
    ("Fresno, CA", ["Fresno"]),
    ("Seattle, WA", ["SEA"]),
    ("Portland, OR", ["PDX"]),
    ("Phoenix, AZ", ["PHX"]),
    ("Tucson, AZ", ["Tucson"]),
    ("Las Vegas, NV", ["Vegas", "LAS"]),
    ("Salt Lake City, UT", ["SLC"]),
    ("Denver, CO", ["DEN"]),
    ("Albuquerque, NM", ["ABQ"]),
    ("El Paso, TX", ["El Paso"]),
    ("Dallas, TX", ["DFW", "Dallas"]),
    ("Fort Worth, TX", ["Fort Worth"]),
    ("Houston, TX", ["HOU"]),
    ("Austin, TX", ["AUS"]),
    ("San Antonio, TX", ["SAT"]),
    ("Laredo, TX", ["Laredo"]),
    ("Oklahoma City, OK", ["OKC"]),
    ("Tulsa, OK", ["Tulsa"]),
    ("Kansas City, MO", ["KC"]),
    ("St Louis, MO", ["STL", "St Louis"]),
    ("Memphis, TN", ["MEM"]),
    ("Nashville, TN", ["BNA"]),
    ("Louisville, KY", ["SDF"]),
    ("Indianapolis, IN", ["Indy"]),
    ("Chicago, IL", ["CHI", "Chicago"]),
    ("Milwaukee, WI", ["MKE"]),
    ("Minneapolis, MN", ["MSP"]),
    ("Des Moines, IA", ["DSM"]),
    ("Omaha, NE", ["OMA"]),
    ("Detroit, MI", ["DTW"]),
    ("Columbus, OH", ["CMH"]),
    ("Cleveland, OH", ["CLE"]),
    ("Cincinnati, OH", ["CVG"]),
    ("Pittsburgh, PA", ["PIT"]),
    ("Philadelphia, PA", ["Philly", "PHL"]),
    ("New York, NY", ["NYC", "NY"]),
    ("Newark, NJ", ["EWR"]),
    ("Boston, MA", ["BOS"]),
    ("Hartford, CT", ["BDL"]),
    ("Baltimore, MD", ["BWI"]),
    ("Washington, DC", ["DC", "IAD"]),
    ("Richmond, VA", ["RIC"]),
    ("Charlotte, NC", ["CLT"]),
    ("Raleigh, NC", ["RDU"]),
    ("Atlanta, GA", ["ATL"]),
    ("Jacksonville, FL", ["JAX"]),
    ("Orlando, FL", ["MCO"]),
    ("Tampa, FL", ["TPA"]),
    ("Miami, FL", ["MIA"]),
    ("Birmingham, AL", ["BHM"]),
    ("New Orleans, LA", ["MSY"]),
    ("Little Rock, AR", ["LIT"]),
    ("Jackson, MS", ["JAN"]),
]

EQUIPMENT = [
    ("dry van", 0.45),
    ("reefer", 0.22),
    ("flatbed", 0.18),
    ("step deck", 0.05),
    ("box truck", 0.04),
    ("hotshot", 0.03),
    ("power only", 0.03),
]

CARGO_BY_EQUIP = {
    "dry van": [
        "General freight",
        "Palletized retail",
        "Amazon/e-commerce",
        "Paper products",
        "Auto parts",
        "Beverages",
        "Building materials",
        "Apparel",
        "Furniture",
        "Electronics",
    ],
    "reefer": [
        "Produce",
        "Frozen food",
        "Dairy",
        "Meat",
        "Pharmaceuticals",
        "Floral",
        "Ice cream",
        "Fresh seafood",
    ],
    "flatbed": [
        "Steel coils",
        "Lumber",
        "Machinery",
        "Pipe",
        "Concrete panels",
        "Roofing materials",
        "Construction equipment",
    ],
    "step deck": [
        "Tall machinery",
        "Industrial equipment",
        "Prefabricated walls",
        "Generators",
    ],
    "box truck": [
        "Partial pallets",
        "Local retail",
        "Moving freight",
        "Store delivery",
    ],
    "hotshot": [
        "Urgent auto parts",
        "Oilfield parts",
        "Expedited machinery",
        "Time-critical freight",
    ],
    "power only": [
        "Loaded trailer pickup",
        "Drop & hook",
        "Trailer relocate",
        "Loaded van trailer",
    ],
}

PAYMENTS = [
    "2-day quick pay",
    "quick pay",
    "same day pay",
    "net 15",
    "net 30",
    "factoring OK",
]

NOTES = [
    "",
    "no touch",
    "driver assist",
    "appointment pickup",
    "first come first serve",
    "tarps required",
    "team preferred",
    "TWIC not required",
    "liftgate not required",
    "drop trailer",
    "live unload",
]


def pick_equipment() -> str:
    roll = random.random()
    total = 0.0
    for name, weight in EQUIPMENT:
        total += weight
        if roll <= total:
            return name
    return "dry van"


def estimate_miles(a: str, b: str) -> int:
    # Rough deterministic distance proxy from city name hashes.
    base = 180 + (abs(hash(a) - hash(b)) % 1600)
    return int(base)


def weight_for(equip: str) -> int:
    ranges = {
        "dry van": (28000, 45000),
        "reefer": (30000, 43000),
        "flatbed": (32000, 48000),
        "step deck": (25000, 42000),
        "box truck": (5000, 16000),
        "hotshot": (2000, 12000),
        "power only": (30000, 44000),
    }
    lo, hi = ranges[equip]
    return random.randint(lo, hi)


def rate_for(miles: int, equip: str) -> tuple[int, float]:
    rpm_base = {
        "dry van": 2.1,
        "reefer": 2.6,
        "flatbed": 2.8,
        "step deck": 3.0,
        "box truck": 2.4,
        "hotshot": 3.2,
        "power only": 2.0,
    }[equip]
    rpm = round(rpm_base + random.uniform(-0.35, 0.85), 2)
    rpm = max(1.4, rpm)
    rate = int(miles * rpm)
    # Round to nearest 25
    rate = int(round(rate / 25.0) * 25)
    return rate, rpm


def main() -> None:
    random.seed(42)
    today = date(2026, 7, 24)
    loads: list[dict] = []
    used_pairs: set[tuple[str, str, str]] = set()

    city_map = {name: aliases for name, aliases in CITIES}
    hubs = [
        "Chicago, IL",
        "Dallas, TX",
        "Los Angeles, CA",
        "Atlanta, GA",
        "Houston, TX",
        "New York, NY",
        "Phoenix, AZ",
        "Ontario, CA",
        "Memphis, TN",
        "Laredo, TX",
    ]

    target = 1500
    attempts = 0
    while len(loads) < target and attempts < target * 30:
        attempts += 1
        # Bias ~55% of lanes to involve a major hub so popular searches are dense.
        if random.random() < 0.55:
            hub = random.choice(hubs)
            other_name, other_aliases = random.choice(CITIES)
            if random.random() < 0.5:
                origin, o_aliases = hub, city_map[hub]
                destination, d_aliases = other_name, other_aliases
            else:
                origin, o_aliases = other_name, other_aliases
                destination, d_aliases = hub, city_map[hub]
        else:
            origin, o_aliases = random.choice(CITIES)
            destination, d_aliases = random.choice(CITIES)
        if origin == destination:
            continue
        equip = pick_equipment()
        key = (origin, destination, equip)
        # allow limited duplicates on popular lanes
        if key in used_pairs and random.random() > 0.35:
            continue
        used_pairs.add(key)

        miles = estimate_miles(origin, destination)
        # bias short-haul for box/hotshot
        if equip in {"box truck", "hotshot"}:
            miles = min(miles, random.randint(80, 450))
        rate, rpm = rate_for(miles, equip)
        pickup = today + timedelta(days=random.randint(0, 5))
        note = random.choice(NOTES)
        cargo = random.choice(CARGO_BY_EQUIP[equip])

        load = {
            "id": f"US-{1000 + len(loads) + 1}",
            "origin": origin,
            "destination": destination,
            "origin_aliases": o_aliases,
            "destination_aliases": d_aliases,
            "cargo": cargo,
            "weight_lbs": weight_for(equip),
            "truck_type": equip,
            "rate": rate,
            "currency": "USD",
            "payment": random.choice(PAYMENTS),
            "distance_miles": miles,
            "rate_per_mile": rpm,
            "loading_date": pickup.isoformat(),
            "contact": f"+1 ({200 + (len(loads) % 700):03d}) 555-{1000 + (len(loads) % 9000):04d} Broker",
            "source": "us-board",
        }
        if note:
            load["notes"] = note
        loads.append(load)

    # Ensure high-demand lanes always present with multiple equipment options
    must_have = [
        ("Chicago, IL", "Dallas, TX"),
        ("Los Angeles, CA", "Phoenix, AZ"),
        ("Atlanta, GA", "Miami, FL"),
        ("Dallas, TX", "Los Angeles, CA"),
        ("Houston, TX", "Atlanta, GA"),
        ("New York, NY", "Chicago, IL"),
        ("Seattle, WA", "Denver, CO"),
        ("Ontario, CA", "Dallas, TX"),
        ("Memphis, TN", "Atlanta, GA"),
        ("Laredo, TX", "Chicago, IL"),
    ]
    for origin, destination in must_have:
        for equip in ("dry van", "reefer", "flatbed"):
            if any(
                x["origin"] == origin
                and x["destination"] == destination
                and x["truck_type"] == equip
                for x in loads
            ):
                continue
            miles = estimate_miles(origin, destination)
            rate, rpm = rate_for(miles, equip)
            loads.append(
                {
                    "id": f"US-{1000 + len(loads) + 1}",
                    "origin": origin,
                    "destination": destination,
                    "origin_aliases": [origin.split(",")[0]],
                    "destination_aliases": [destination.split(",")[0]],
                    "cargo": random.choice(CARGO_BY_EQUIP[equip]),
                    "weight_lbs": weight_for(equip),
                    "truck_type": equip,
                    "rate": rate,
                    "currency": "USD",
                    "payment": "2-day quick pay",
                    "distance_miles": miles,
                    "rate_per_mile": rpm,
                    "loading_date": today.isoformat(),
                    "contact": "+1 (800) 555-0199 Load Desk",
                    "source": "us-board",
                    "notes": "high volume lane",
                }
            )

    # Re-id sequentially
    for i, load in enumerate(loads, start=1):
        load["id"] = f"US-{1000 + i}"

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(loads, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(loads)} loads to {OUT}")


if __name__ == "__main__":
    main()
