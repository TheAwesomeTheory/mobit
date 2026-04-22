"""Validate pin positions by placing colored spheres on both faces of each board.

Blue = chip side (component face)
Red = non-chip side (opposite face)
"""

import cadquery as cq
import numpy as np

from geometry import rot_x, rot_z, load_pins, BoardInScene

# Load geometry
bno = cq.importers.importStep("cad/bno085.step")
xiao = cq.importers.importStep("cad/xiao_nrf54l15.step")
bb_bno = bno.val().BoundingBox()

# Stack config: 180° chip-down, -2mm gap
BATT_H = 3.8
GAP = -2.0
bno_z_start = BATT_H + 0.5
bno_top = bno_z_start + bb_bno.zlen

# Position BNO085
bno_centered = bno.translate((-bb_bno.xlen / 2, -bb_bno.ylen / 2, bno_z_start))
bb_bc = bno_centered.val().BoundingBox()

# Position XIAO: chip-down 180°
xiao_r = xiao.rotate((0, 0, 0), (1, 0, 0), -90)
xiao_r = xiao_r.rotate((0, 0, 0), (0, 0, 1), 180)
bb_xr = xiao_r.val().BoundingBox()
xiao_cx = (bb_xr.xmin + bb_xr.xmax) / 2
xiao_cy = (bb_xr.ymin + bb_xr.ymax) / 2
xiao_pos = xiao_r.translate((-xiao_cx, -xiao_cy, bno_top + GAP - bb_xr.zmin))
bb_xp = xiao_pos.val().BoundingBox()

# Create BoardInScene objects
# PCB surface Z values (from actual PCB solid geometry, not bounding box)
# XIAO PCB: local Y=-0.66 (non-chip) to Y=0.85 (chip surface)
# After rot_z(180) @ rot_x(-90) + translation:
R_xiao = rot_z(180) @ rot_x(-90)
T_xiao = np.array([-xiao_cx, -xiao_cy, bno_top + GAP - bb_xr.zmin])
xiao_chip_z = float((R_xiao @ np.array([0, 0.85, 0]) + T_xiao)[2])
xiao_nonchip_z = float((R_xiao @ np.array([0, -0.66, 0]) + T_xiao)[2])

# BNO085 PCB: local Z=0.00 (non-chip) to Z=1.57 (chip surface)
bno_chip_z = 1.57 + bno_z_start
bno_nonchip_z = 0.00 + bno_z_start

xiao_board = BoardInScene(
    name="xiao",
    pins=load_pins("cad/pins_xiao.json"),
    rotation=R_xiao,
    translation=T_xiao,
    chip_side_z=xiao_chip_z,        # PCB component surface
    non_chip_side_z=xiao_nonchip_z, # PCB opposite surface
)

bno_board = BoardInScene(
    name="bno085",
    pins=load_pins("cad/pins_bno085.json"),
    rotation=np.eye(3),
    translation=np.array([-bb_bno.xlen / 2, -bb_bno.ylen / 2, bno_z_start]),
    chip_side_z=bno_chip_z,         # PCB component surface
    non_chip_side_z=bno_nonchip_z,  # PCB bottom
)

# Build assembly
assembly = cq.Assembly()
assembly.add(bno_centered, name="bno085", color=cq.Color("purple"))
assembly.add(xiao_pos, name="xiao", color=cq.Color("green"))

SPHERE_RADIUS = 0.4

print("=== XIAO pins ===")
for board in [xiao_board, bno_board]:
    print(f"\n{board.name}: chip_side_z={board.chip_side_z:.2f}, non_chip_side_z={board.non_chip_side_z:.2f}")
    for pin_name in board.pins:
        # Blue sphere on chip side
        chip_pos = board.get_pin(pin_name, chip_side=True)
        sphere_chip = cq.Workplane("XY").sphere(SPHERE_RADIUS).translate(tuple(chip_pos))
        assembly.add(sphere_chip, name=f"{board.name}_{pin_name}_chip",
                     color=cq.Color(0.0, 0.3, 1.0, 1.0))

        # Red sphere on non-chip side
        non_chip_pos = board.get_pin(pin_name, chip_side=False)
        sphere_non = cq.Workplane("XY").sphere(SPHERE_RADIUS).translate(tuple(non_chip_pos))
        assembly.add(sphere_non, name=f"{board.name}_{pin_name}_nonchip",
                     color=cq.Color(1.0, 0.0, 0.0, 1.0))

        print(f"  {pin_name:6s}  chip=({chip_pos[0]:7.2f},{chip_pos[1]:7.2f},{chip_pos[2]:7.2f})  "
              f"non-chip=({non_chip_pos[0]:7.2f},{non_chip_pos[1]:7.2f},{non_chip_pos[2]:7.2f})")

assembly.save("cad/dadovida_pins_validate.step")
print(f"\nExported: cad/dadovida_pins_validate.step")
