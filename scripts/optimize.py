"""Generic board rotation optimizer.

Scores candidate rotations of board A relative to board B by:
1. Wire crossing count (fewer is better)
2. Median wire length (shorter is better)

All board-specific config is at the bottom in main().
"""

import json
import math
import statistics

import numpy as np

from mobit.geometry import rot_x, rot_y, rot_z, pin_to_assembly, load_pins, load_connections


def segments_cross_2d(a1, a2, b1, b2):
    """Check if segment (a1→a2) crosses (b1→b2) projected onto XY."""
    def cross2(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    d1 = cross2(b1, b2, a1)
    d2 = cross2(b1, b2, a2)
    d3 = cross2(a1, a2, b1)
    d4 = cross2(a1, a2, b2)
    return ((d1 > 0 and d2 < 0) or (d1 < 0 and d2 > 0)) and \
           ((d3 > 0 and d4 < 0) or (d3 < 0 and d4 > 0))


# --- Core optimizer ---

def evaluate(candidates, pins_a, pins_b, connections, transform_b):
    """Evaluate a list of candidates and return scored results.

    Each candidate is a dict with:
        name: str           — human-readable label
        rotation: 3x3 array — full rotation matrix for board A
        translation: 3-vec  — translation for board A
    """
    rot_b, trans_b = transform_b

    scored = []
    for cand in candidates:
        rot_a = cand["rotation"]
        trans_a = cand["translation"]

        # Compute wire endpoints
        wire_endpoints = []
        wire_dists = []
        wire_details = []
        for conn in connections:
            pa = pin_to_assembly(pins_a[conn["from"]["pin"]], rot_a, trans_a)
            pb = pin_to_assembly(pins_b[conn["to"]["pin"]], rot_b, trans_b)
            dist = float(np.linalg.norm(pa - pb))
            wire_endpoints.append(((pa[0], pa[1]), (pb[0], pb[1])))
            wire_dists.append(dist)
            wire_details.append((conn["signal"], conn["from"]["pin"], conn["to"]["pin"], dist))

        # Count crossings
        crossings = 0
        for i in range(len(wire_endpoints)):
            for j in range(i + 1, len(wire_endpoints)):
                if segments_cross_2d(wire_endpoints[i][0], wire_endpoints[i][1],
                                     wire_endpoints[j][0], wire_endpoints[j][1]):
                    crossings += 1

        scored.append({
            "name": cand["name"],
            "crossings": crossings,
            "median": statistics.median(wire_dists),
            "mean": statistics.mean(wire_dists),
            "max": max(wire_dists),
            "total": sum(wire_dists),
            "wires": wire_details,
        })

    scored.sort(key=lambda s: (s["crossings"], s["median"]))
    return scored


def print_results(scored, board_a_name, board_b_name):
    print("Rotation Optimization Results (ranked by crossings, then median)")
    print("=" * 88)
    print(f"{'Rank':<6} {'Config':<20} {'Cross':>7} {'Median':>8} {'Mean':>8} {'Max':>8} {'Total':>8}")
    print(f"{'----':<6} {'------':<20} {'-----':>7} {'------':>8} {'----':>8} {'---':>8} {'-----':>8}")
    for i, s in enumerate(scored):
        marker = " <--" if i == 0 else ""
        print(f"{i+1:<6} {s['name']:<20} {s['crossings']:>5}   {s['median']:>7.2f}  {s['mean']:>7.2f}  {s['max']:>7.2f}  {s['total']:>7.2f}{marker}")

    best = scored[0]
    print(f"\nWinner: {best['name']} ({best['crossings']} crossings, {best['median']:.2f}mm median)")
    print(f"\nPer-wire breakdown:")
    for signal, pin_a, pin_b, dist in best["wires"]:
        print(f"  {signal:<6} {board_a_name}:{pin_a:<6} → {board_b_name}:{pin_b:<6} {dist:>6.2f} mm")


# --- DadoVida-specific config ---

def main():
    # Load pin data
    pins_a = load_pins("cad/pins_xiao.json")
    pins_b = load_pins("cad/pins_bno085.json")
    connections = load_connections("cad/connections.json")

    # Board B (BNO085) transform — fixed
    transform_b = (np.eye(3), np.array([-12.70, -11.43, 4.30]))

    # Board A (XIAO) base rotations
    chip_up = rot_y(180) @ rot_x(-90)
    chip_down = rot_x(-90)
    translation_a = np.array([0.19, 0.00, 10.02])

    # Build all candidates
    candidates = []
    for z_deg in [0, 90, 180, 270]:
        for flip_name, base_rot in [("chip-up", chip_up), ("chip-down", chip_down)]:
            candidates.append({
                "name": f"{z_deg}° {flip_name}",
                "rotation": rot_z(z_deg) @ base_rot,
                "translation": translation_a,
            })

    scored = evaluate(candidates, pins_a, pins_b, connections, transform_b)
    print_results(scored, "xiao", "bno085")


if __name__ == "__main__":
    main()
