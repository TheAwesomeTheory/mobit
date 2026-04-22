"""Build the assembly with pathfinding-routed wires."""

import cadquery as cq
import numpy as np

from geometry import rot_x, rot_z, load_pins, load_connections, BoardInScene
from wire_router import route_wires

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

# Position XIAO: chip-down 180°
xiao_r = xiao.rotate((0, 0, 0), (1, 0, 0), -90)
xiao_r = xiao_r.rotate((0, 0, 0), (0, 0, 1), 180)
bb_xr = xiao_r.val().BoundingBox()
xiao_cx = (bb_xr.xmin + bb_xr.xmax) / 2
xiao_cy = (bb_xr.ymin + bb_xr.ymax) / 2
xiao_pos = xiao_r.translate((-xiao_cx, -xiao_cy, bno_top + GAP - bb_xr.zmin))
bb_xp = xiao_pos.val().BoundingBox()

print(f"BNO085:  Z {bno_z_start:.2f} to {bno_top:.2f}")
print(f"XIAO:    Z {bb_xp.zmin:.2f} to {bb_xp.zmax:.2f}")
print(f"Total:   {bb_xp.zmax:.2f}mm")

# Board transforms
R_xiao = rot_z(180) @ rot_x(-90)
T_xiao = np.array([-xiao_cx, -xiao_cy, bno_top + GAP - bb_xr.zmin])
T_bno = np.array([-bb_bno.xlen / 2, -bb_bno.ylen / 2, bno_z_start])

# PCB surface Z values (from actual PCB solid geometry)
# XIAO PCB: local Y=-0.66 (non-chip) to Y=0.85 (chip surface)
xiao_chip_z = float((R_xiao @ np.array([0, 0.85, 0]) + T_xiao)[2])
xiao_nonchip_z = float((R_xiao @ np.array([0, -0.66, 0]) + T_xiao)[2])
# BNO085 PCB: local Z=0.00 (non-chip) to Z=1.57 (chip surface)
bno_chip_z = 1.57 + bno_z_start
bno_nonchip_z = 0.00 + bno_z_start

# Create BoardInScene objects
xiao_board = BoardInScene(
    name="xiao",
    pins=load_pins("cad/pins_xiao.json"),
    rotation=R_xiao,
    translation=T_xiao,
    chip_side_z=xiao_chip_z,
    non_chip_side_z=xiao_nonchip_z,
)

bno_board = BoardInScene(
    name="bno085",
    pins=load_pins("cad/pins_bno085.json"),
    rotation=np.eye(3),
    translation=T_bno,
    chip_side_z=bno_chip_z,
    non_chip_side_z=bno_nonchip_z,
)

# Get pin positions on chip side (facing each other)
xiao_assy_pins = xiao_board.all_pins(chip_side=True)
bno_assy_pins = bno_board.all_pins(chip_side=True)

connections = load_connections("cad/connections.json")

# Build assembly
assembly = cq.Assembly()
assembly.add(bno_centered, name="bno085")
assembly.add(xiao_pos, name="xiao")

battery = cq.importers.importStep("cad/lipo_150mah.step")
bb_bat = battery.val().BoundingBox()
battery_pos = battery.translate((
    -(bb_bat.xmin + bb_bat.xmax) / 2,
    -(bb_bat.ymin + bb_bat.ymax) / 2,
    -bb_bat.zmin,
))
assembly.add(battery_pos, name="battery")

# Route wires — exit straight down from XIAO, enter straight down into BNO085
print("\n=== Routing Wires ===")
wire_shapes = route_wires(
    board_shapes=[bno_centered, xiao_pos],
    pin_positions_a=xiao_assy_pins,
    pin_positions_b=bno_assy_pins,
    connections=connections,
    wire_radius=0.3,
    grid_resolution=0.5,
    clearance=0.5,
    exit_dir_a=np.array([0, 0, -1]),
    entry_dir_b=np.array([0, 0, -1]),
    exit_distance=1.5,
)

for name, shape, color in wire_shapes:
    assembly.add(shape, name=name, color=cq.Color(*color, 1.0))

assembly.save("cad/dadovida_routed.step")
print(f"\nExported: cad/dadovida_routed.step")
