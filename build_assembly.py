"""Build a stacked assembly of BNO085 + XIAO + LiPo battery with pin markers."""

import json
import math

import cadquery as cq

# Load components
bno = cq.importers.importStep("cad/bno085.step")
xiao = cq.importers.importStep("cad/xiao_nrf54l15.step")

bb_bno = bno.val().BoundingBox()
bb_xiao = xiao.val().BoundingBox()

# Stack parameters
GAP = 0.5
BATT_L, BATT_W, BATT_H = 26.0, 19.8, 3.8
bno_z_start = BATT_H + GAP

# Battery
battery = cq.Workplane("XY").box(BATT_L, BATT_W, BATT_H).translate((0, 0, BATT_H / 2))

# BNO085 — center on XY, place above battery
bno_centered = bno.translate((-bb_bno.xlen / 2, -bb_bno.ylen / 2, bno_z_start))

# XIAO — rotate to lay flat, chip side up, then 90° Z rotation
xiao_rotated = xiao.rotate((0, 0, 0), (1, 0, 0), -90)
xiao_rotated = xiao_rotated.rotate((0, 0, 0), (0, 1, 0), 180)
xiao_rotated = xiao_rotated.rotate((0, 0, 0), (0, 0, 1), 90)

bb_xr = xiao_rotated.val().BoundingBox()
xiao_z_start = bno_z_start + bb_bno.zlen + GAP
xiao_cx = (bb_xr.xmin + bb_xr.xmax) / 2
xiao_cy = (bb_xr.ymin + bb_xr.ymax) / 2
xiao_positioned = xiao_rotated.translate((-xiao_cx, -xiao_cy, xiao_z_start - bb_xr.zmin))
bb_xp = xiao_positioned.val().BoundingBox()

# Feather for scale
feather = cq.importers.importStep("cad/feather_nrf52840.step")
bb_feather = feather.val().BoundingBox()
feather_x_offset = max(bb_xp.xmax, bb_bno.xlen / 2, BATT_L / 2) + 5.0 + bb_feather.xlen / 2
feather_positioned = feather.translate((
    feather_x_offset - (bb_feather.xmin + bb_feather.xmax) / 2,
    -(bb_feather.ymin + bb_feather.ymax) / 2,
    -bb_feather.zmin
))

# --- Pin markers ---
# Place a sphere at every pin location on both boards to validate positions
SPHERE_RADIUS = 0.5  # mm, visible but not huge

# Load pin maps
with open("cad/pins_xiao.json") as f:
    xiao_pin_data = json.load(f)
with open("cad/pins_bno085.json") as f:
    bno_pin_data = json.load(f)

# XIAO pins: transform local coords through the same rotations as the board
# Local space: X is width, Y is thickness, Z is length
# Transforms: rot X(-90), rot Y(180), rot Z(90), then translate
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

R_xiao = rot_z(90) @ rot_y(180) @ rot_x(-90)
T_xiao = np.array([-xiao_cx, -xiao_cy, xiao_z_start - bb_xr.zmin])

T_bno = np.array([-bb_bno.xlen / 2, -bb_bno.ylen / 2, bno_z_start])

pin_spheres = []

print("=== XIAO pin markers ===")
for name, pin in xiao_pin_data["pins"].items():
    local = np.array([pin["x"], pin["y"], pin["z"]])
    assy = R_xiao @ local + T_xiao
    print(f"  {name:6s} -> ({assy[0]:7.2f}, {assy[1]:7.2f}, {assy[2]:7.2f})")
    sphere = cq.Workplane("XY").sphere(SPHERE_RADIUS).translate(tuple(assy))
    pin_spheres.append((f"xiao_{name}", sphere, (0.0, 1.0, 0.0)))  # green

print("\n=== BNO085 pin markers ===")
for name, pin in bno_pin_data["pins"].items():
    local = np.array([pin["x"], pin["y"], pin["z"]])
    assy = local + T_bno
    print(f"  {name:6s} -> ({assy[0]:7.2f}, {assy[1]:7.2f}, {assy[2]:7.2f})")
    sphere = cq.Workplane("XY").sphere(SPHERE_RADIUS).translate(tuple(assy))
    pin_spheres.append((f"bno_{name}", sphere, (1.0, 0.0, 1.0)))  # magenta

# --- Summary ---
print(f"\n=== Assembly Summary ===")
print(f"Total height: {bb_xp.zmax:.2f} mm")
footprint_x = max(bb_xp.xmax, bb_bno.xlen/2, BATT_L/2) - min(bb_xp.xmin, -bb_bno.xlen/2, -BATT_L/2)
footprint_y = max(bb_xp.ymax, bb_bno.ylen/2, BATT_W/2) - min(bb_xp.ymin, -bb_bno.ylen/2, -BATT_W/2)
diag = math.sqrt(footprint_x**2 + footprint_y**2)
print(f"Footprint: {footprint_x:.2f} x {footprint_y:.2f} mm, diagonal: {diag:.2f} mm")

# --- Export ---
assembly = cq.Assembly()
assembly.add(battery, name="lipo_battery", color=cq.Color("gray"))
assembly.add(bno_centered, name="bno085_breakout", color=cq.Color("purple"))
assembly.add(xiao_positioned, name="xiao_nrf54l15", color=cq.Color("green"))
assembly.add(feather_positioned, name="feather_nrf52840_scale", color=cq.Color(0.2, 0.2, 0.8, 0.5))

for name, sphere, color in pin_spheres:
    assembly.add(sphere, name=name, color=cq.Color(*color, 1.0))

assembly.save("cad/dadovida_stack.step")
print(f"\nExported: cad/dadovida_stack.step")
print(f"Pin markers: {len(pin_spheres)} spheres ({sum(1 for n,_,_ in pin_spheres if n.startswith('xiao'))} XIAO, {sum(1 for n,_,_ in pin_spheres if n.startswith('bno'))} BNO085)")
