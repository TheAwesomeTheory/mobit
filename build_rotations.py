"""Build 180° chip-down at progressively tighter gaps to find minimum clearance."""

import json
import math

import cadquery as cq
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


bno = cq.importers.importStep("cad/bno085.step")
xiao = cq.importers.importStep("cad/xiao_nrf54l15.step")
bb_bno = bno.val().BoundingBox()

BATT_H = 3.8
bno_z_start = BATT_H + 0.5

with open("cad/pins_xiao.json") as f:
    xiao_pins = json.load(f)["pins"]
with open("cad/pins_bno085.json") as f:
    bno_pins = json.load(f)["pins"]
with open("cad/connections.json") as f:
    connections = json.load(f)["connections"]

WIRE_COLORS = {
    "3V3": (1.0, 0.0, 0.0),
    "GND": (0.1, 0.1, 0.1),
    "SDA": (0.0, 0.3, 1.0),
    "SCL": (1.0, 0.9, 0.0),
}
SPHERE_RADIUS = 0.5
WIRE_RADIUS = 0.25
SPACING = 40.0

BNO_T = np.array([-bb_bno.xlen / 2, -bb_bno.ylen / 2, bno_z_start])
bno_top = bno_z_start + bb_bno.zlen

base_rot = rot_x(-90)  # chip-down
R_a = rot_z(180) @ base_rot

assembly = cq.Assembly()

gaps = [2.0, 0.0, -2.0]

for gi, gap in enumerate(gaps):
    x_offset = gi * SPACING
    label = f"gap_{gap:.0f}".replace("-", "neg")

    # BNO085
    bno_pos = bno.translate((-bb_bno.xlen/2 + x_offset, -bb_bno.ylen/2, bno_z_start))
    assembly.add(bno_pos, name=f"{label}_bno", color=cq.Color("purple"))

    # XIAO chip-down 180°
    xiao_r = xiao.rotate((0,0,0), (1,0,0), -90)
    xiao_r = xiao_r.rotate((0,0,0), (0,0,1), 180)
    bb_xr = xiao_r.val().BoundingBox()
    xiao_cx = (bb_xr.xmin + bb_xr.xmax) / 2
    xiao_cy = (bb_xr.ymin + bb_xr.ymax) / 2
    xiao_pos = xiao_r.translate((-xiao_cx + x_offset, -xiao_cy, bno_top + gap - bb_xr.zmin))
    assembly.add(xiao_pos, name=f"{label}_xiao", color=cq.Color("green"))

    bb_xp = xiao_pos.val().BoundingBox()
    T_a = np.array([-xiao_cx + x_offset, -xiao_cy, bno_top + gap - bb_xr.zmin])

    # Wires
    for conn in connections:
        xp_name = conn["from"]["pin"]
        bp_name = conn["to"]["pin"]
        signal = conn["signal"]

        xp = xiao_pins[xp_name]
        xiao_assy = R_a @ np.array([xp["x"], xp["y"], xp["z"]]) + T_a

        bp = bno_pins[bp_name]
        bno_assy = np.array([bp["x"], bp["y"], bp["z"]]) + BNO_T + np.array([x_offset, 0, 0])

        # Pin spheres
        assembly.add(
            cq.Workplane("XY").sphere(SPHERE_RADIUS).translate(tuple(xiao_assy)),
            name=f"{label}_xp_{xp_name}", color=cq.Color(0.0, 1.0, 0.0, 1.0))
        assembly.add(
            cq.Workplane("XY").sphere(SPHERE_RADIUS).translate(tuple(bno_assy)),
            name=f"{label}_bp_{bp_name}", color=cq.Color(1.0, 0.0, 1.0, 1.0))

        # Wire
        color = WIRE_COLORS.get(signal, (0.5, 0.5, 0.5))
        direction = tuple(bno_assy - xiao_assy)
        wire = (
            cq.Workplane("XY")
            .transformed(offset=tuple(xiao_assy))
            .circle(WIRE_RADIUS)
            .workplane(offset=0)
            .transformed(offset=direction)
            .circle(WIRE_RADIUS)
            .loft()
        )
        assembly.add(wire, name=f"{label}_w_{signal}", color=cq.Color(*color, 1.0))

    print(f"gap={gap:>5.1f}mm  stack_height={bb_xp.zmax:.2f}mm")

assembly.save("cad/dadovida_rotations.step")
print(f"\nExported: cad/dadovida_rotations.step")
