"""Compute the 3D distance between two pins across boards in the assembly."""

import sys

import numpy as np

from mobit.geometry import rot_x, rot_y, rot_z, load_pins, pin_to_assembly


# Assembly transforms (from build script)
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


def main():
    if len(sys.argv) != 5:
        print(f"Usage: uv run python {sys.argv[0]} <board1> <pin1> <board2> <pin2>")
        print(f"  e.g.: uv run python {sys.argv[0]} xiao D4 bno085 SDA")
        print(f"")
        print(f"Boards: {', '.join(PIN_FILES.keys())}")
        for name in PIN_FILES:
            pins = load_pins(PIN_FILES[name])
            print(f"  {name} pins: {', '.join(pins.keys())}")
        sys.exit(1)

    board1, pin1, board2, pin2 = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]

    pins1 = load_pins(PIN_FILES[board1])
    pins2 = load_pins(PIN_FILES[board2])

    if pin1 not in pins1:
        print(f"Error: pin '{pin1}' not found on {board1}")
        print(f"  Available: {', '.join(pins1.keys())}")
        sys.exit(1)
    if pin2 not in pins2:
        print(f"Error: pin '{pin2}' not found on {board2}")
        print(f"  Available: {', '.join(pins2.keys())}")
        sys.exit(1)

    t1 = TRANSFORMS[board1]
    t2 = TRANSFORMS[board2]
    p1 = pin_to_assembly(pins1[pin1], t1["rotation"], t1["translation"])
    p2 = pin_to_assembly(pins2[pin2], t2["rotation"], t2["translation"])
    dist = float(np.linalg.norm(p1 - p2))

    fn1 = pins1[pin1].get("function", "")
    fn2 = pins2[pin2].get("function", "")

    print(f"{board1}:{pin1} ({fn1})")
    print(f"  assembly: ({p1[0]:.2f}, {p1[1]:.2f}, {p1[2]:.2f})")
    print(f"{board2}:{pin2} ({fn2})")
    print(f"  assembly: ({p2[0]:.2f}, {p2[1]:.2f}, {p2[2]:.2f})")
    print(f"distance: {dist:.2f} mm")


if __name__ == "__main__":
    main()
