"""Build the assembly with pathfinding-routed wires."""

import cadquery as cq
import numpy as np

from mobit.geometry import rot_x, rot_z, load_pins, load_connections, BoardInScene, import_step_with_colors
from mobit.wire_router import route_wires

# Load geometry (plain import for transforms/bounding boxes)
bno = cq.importers.importStep("cad/bno085.step")
xiao = cq.importers.importStep("cad/xiao_nrf54l15.step")
bb_bno = bno.val().BoundingBox()

# Color-preserving imports for the final assembly
bno_colored = import_step_with_colors("cad/bno085.step")
xiao_colored = import_step_with_colors("cad/xiao_nrf54l15.step")
battery_colored = import_step_with_colors("cad/lipo_150mah.step")

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

# Battery board
battery_plain = cq.importers.importStep("cad/lipo_150mah.step")
bb_bat = battery_plain.val().BoundingBox()
T_bat = np.array([-(bb_bat.xmin + bb_bat.xmax) / 2, -(bb_bat.ymin + bb_bat.ymax) / 2, -bb_bat.zmin])
battery_pos = battery_plain.translate(tuple(T_bat))

battery_board = BoardInScene(
    name="battery",
    pins=load_pins("cad/pins_battery.json"),
    rotation=np.eye(3),
    translation=T_bat,
    chip_side_z=1.90 + T_bat[2],      # mid-height (wire exit point)
    non_chip_side_z=1.90 + T_bat[2],  # same — no top/bottom distinction
)

# Get pin positions on chip side (facing each other) for I2C
xiao_assy_pins = xiao_board.all_pins(chip_side=True)
bno_assy_pins = bno_board.all_pins(chip_side=True)
battery_assy_pins = battery_board.all_pins(chip_side=True)

# Battery pads on XIAO are on the non-chip side (top in chip-down config)
# Override just the BAT pins with non-chip side Z
xiao_bat_pins = {
    "BAT+": xiao_board.get_pin("BAT+", chip_side=False),
    "BAT-": xiao_board.get_pin("BAT-", chip_side=False),
}
# Merge into a copy for battery routing
xiao_assy_pins_for_battery = dict(xiao_assy_pins)
xiao_assy_pins_for_battery.update(xiao_bat_pins)

connections = load_connections("cad/connections.json")

# Split connections by board pair
i2c_connections = [c for c in connections if c["from"]["board"] != "battery" and c["to"]["board"] != "battery"]
battery_connections = [c for c in connections if c["from"]["board"] == "battery" or c["to"]["board"] == "battery"]

# Build assembly with color-preserving sub-assemblies
assembly = cq.Assembly()

# BNO085 with original colors
bno_loc = cq.Location(cq.Vector(-bb_bno.xlen / 2, -bb_bno.ylen / 2, bno_z_start))
assembly.add(bno_colored, name="bno085", loc=bno_loc)

# XIAO with original colors (rotate then translate)
xiao_loc = (
    cq.Location(cq.Vector(-xiao_cx, -xiao_cy, bno_top + GAP - bb_xr.zmin))
    * cq.Location(cq.Vector(0, 0, 0), cq.Vector(0, 0, 1), 180)
    * cq.Location(cq.Vector(0, 0, 0), cq.Vector(1, 0, 0), -90)
)
assembly.add(xiao_colored, name="xiao", loc=xiao_loc)

# Battery with original colors
bat_loc = cq.Location(cq.Vector(*T_bat))
assembly.add(battery_colored, name="battery", loc=bat_loc)

# USB-C keepout zone — 10mm box extending from the USB-C connector opening
# USB-C is at Y≈4.3 to 11.6 in assembly space, extend further in +Y
usb_keepout = cq.Workplane("XY").box(12, 10, 5).translate((0, 16, 9))

# Route I2C wires — between XIAO and BNO085
print("\n=== Routing I2C Wires ===")
wire_shapes = route_wires(
    board_shapes=[bno_centered, xiao_pos, battery_pos, usb_keepout],
    pin_positions_a=xiao_assy_pins,
    pin_positions_b=bno_assy_pins,
    connections=i2c_connections,
    wire_radius=0.3,
    grid_resolution=0.5,
    clearance=0.5,
    exit_dir_a=np.array([0, 0, -1]),
    entry_dir_b=np.array([0, 0, -1]),
    exit_distance=1.5,
)

# Route battery wires — from battery to XIAO
print("\n=== Routing Battery Wires ===")
# Battery wires exit sideways (out past the board edge) then route up around the stack
# Battery pads are near center XY, so exit in +Y direction (toward the nearest edge)
battery_wire_shapes = route_wires(
    board_shapes=[bno_centered, xiao_pos, battery_pos, usb_keepout],
    pin_positions_a=battery_assy_pins,
    pin_positions_b=xiao_assy_pins_for_battery,
    connections=battery_connections,
    wire_radius=0.3,
    grid_resolution=0.5,
    clearance=0.3,
    exit_dir_a=np.array([1, 0, 0]),    # exit out the short edge (+X direction)
    entry_dir_b=np.array([0, 0, -1]), # approach from above the XIAO
    exit_distance=2.0,                # tighter — shorter paths
    padding=5.0,
)
wire_shapes.extend(battery_wire_shapes)

for name, shape, color in wire_shapes:
    assembly.add(shape, name=name, color=cq.Color(*color, 1.0))

assembly.save("cad/dadovida_routed.step")
print(f"\nExported: cad/dadovida_routed.step")

# --- GLB export with PBR materials ---
from mobit.export_glb import export_glb

print("\n=== GLB Export ===")
glb_shapes = []


def collect_board_parts(colored_assy, board_key, board_loc):
    """Iterate a colored assembly, apply board transform, collect for GLB."""
    parts = []
    for shape, name, loc, col in colored_assy:
        # Strip the top-level prefix (e.g., "PCB Component/Board:1" → "Board:1")
        comp_name = name.split("/")[-1] if "/" in name else name
        # Apply component location then board location
        moved_shape = shape.moved(loc).moved(board_loc)
        wp = cq.Workplane().add(moved_shape)
        parts.append((f"{board_key}/{comp_name}", board_key, comp_name, wp))
    return parts


glb_shapes.extend(collect_board_parts(bno_colored, "bno085", bno_loc))
glb_shapes.extend(collect_board_parts(xiao_colored, "xiao", xiao_loc))

# Battery
glb_shapes.append(("battery", "battery", "*", battery_pos))

# Wires
for wire_name, wire_shape, wire_color in wire_shapes:
    glb_shapes.append((wire_name, "wires", wire_name, wire_shape))

export_glb(glb_shapes, output_path="cad/dadovida.glb")
