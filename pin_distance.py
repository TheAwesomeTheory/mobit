"""Compute the 3D distance between two pins across boards in the assembly."""

import json
import math
import sys

import numpy as np


def rot_x(d):
    r = math.radians(d); c = math.cos(r); s = math.sin(r)
    return np.array([[1,0,0],[0,c,-s],[0,s,c]])

def rot_y(d):
    r = math.radians(d); c = math.cos(r); s = math.sin(r)
    return np.array([[c,0,s],[0,1,0],[-s,0,c]])

def rot_z(d):
    r = math.radians(d); c = math.cos(r); s = math.sin(r)
    return np.array([[c,-s,0],[s,c,0],[0,0,1]])


# Assembly transforms (from build_assembly.py)
TRANSFORMS = {
    "xiao": {
        "rotation": rot_z(90) @ rot_y(180) @ rot_x(-90),
        "translation": np.array([0.19, 0.00, 10.02]),
    },
    "bno085": {
        "rotation": np.eye(3),
        "translation": np.array([-12.70, -11.43, 4.30]),
    },
}

PIN_FILES = {
    "xiao": "cad/pins_xiao.json",
    "bno085": "cad/pins_bno085.json",
}


def load_board(name):
    with open(PIN_FILES[name]) as f:
        return json.load(f)


def local_to_assembly(board_name, pin_coords):
    t = TRANSFORMS[board_name]
    local = np.array([pin_coords["x"], pin_coords["y"], pin_coords["z"]])
    return t["rotation"] @ local + t["translation"]


def main():
    if len(sys.argv) != 5:
        print(f"Usage: uv run python {sys.argv[0]} <board1> <pin1> <board2> <pin2>")
        print(f"  e.g.: uv run python {sys.argv[0]} xiao D4 bno085 SDA")
        print(f"")
        print(f"Boards: {', '.join(PIN_FILES.keys())}")
        for name in PIN_FILES:
            data = load_board(name)
            pins = ', '.join(data["pins"].keys())
            print(f"  {name} pins: {pins}")
        sys.exit(1)

    board1, pin1, board2, pin2 = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]

    data1 = load_board(board1)
    data2 = load_board(board2)

    if pin1 not in data1["pins"]:
        print(f"Error: pin '{pin1}' not found on {board1}")
        print(f"  Available: {', '.join(data1['pins'].keys())}")
        sys.exit(1)
    if pin2 not in data2["pins"]:
        print(f"Error: pin '{pin2}' not found on {board2}")
        print(f"  Available: {', '.join(data2['pins'].keys())}")
        sys.exit(1)

    p1 = local_to_assembly(board1, data1["pins"][pin1])
    p2 = local_to_assembly(board2, data2["pins"][pin2])
    dist = float(np.linalg.norm(p1 - p2))

    fn1 = data1["pins"][pin1].get("function", "")
    fn2 = data2["pins"][pin2].get("function", "")

    print(f"{board1}:{pin1} ({fn1})")
    print(f"  assembly: ({p1[0]:.2f}, {p1[1]:.2f}, {p1[2]:.2f})")
    print(f"{board2}:{pin2} ({fn2})")
    print(f"  assembly: ({p2[0]:.2f}, {p2[1]:.2f}, {p2[2]:.2f})")
    print(f"distance: {dist:.2f} mm")


if __name__ == "__main__":
    main()
