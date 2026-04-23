"""Side-by-side comparison: DadoVida vs Lingo, both flat on their backs."""

import os
import cadquery as cq
import trimesh

from mobit.export_glb import export_glb

CACHED_GLB = "cad/dadovida.glb"
OUTPUT = "cad/dadovida_vs_lingo.glb"

# Load cached DadoVida assembly
if not os.path.exists(CACHED_GLB):
    print(f"Error: {CACHED_GLB} not found. Run 'task build' first.")
    exit(1)

dadovida_scene = trimesh.load(CACHED_GLB)
dv_bounds = dadovida_scene.bounds
dv_width = dv_bounds[1][0] - dv_bounds[0][0]

# Lingo: 35mm diameter, 5mm thick cylinder
LINGO_D = 35.0
LINGO_H = 5.0

# Place DadoVida on the left, Lingo on the right
# Both flat on their backs (Z up), spaced apart
gap = 10.0
lingo_x = dv_width / 2 + gap + LINGO_D / 2

lingo = (
    cq.Workplane("XY")
    .circle(LINGO_D / 2)
    .extrude(LINGO_H)
    .translate((lingo_x, 0, 0))
)

# CR3032: 30mm diameter, 3.2mm thick
CR3032_D = 30.0
CR3032_H = 3.2
cr3032_x = lingo_x + LINGO_D / 2 + gap + CR3032_D / 2

cr3032 = (
    cq.Workplane("XY")
    .circle(CR3032_D / 2)
    .extrude(CR3032_H)
    .translate((cr3032_x, 0, 0))
)

# Build GLB
glb_shapes = []
glb_shapes.append(("Lingo", "references", "*", lingo))
glb_shapes.append(("CR3032", "references", "*", cr3032))

labels = [
    ("DadoVida", (0, 0, dv_bounds[1][2] + 1.5), 2.5),
    ("Lingo", (lingo_x, 0, LINGO_H + 1.5), 2.5),
    ("35x5mm", (lingo_x, 0, LINGO_H + 4.5), 1.5),
    ("CR3032", (cr3032_x, 0, CR3032_H + 1.5), 2.5),
    ("30x3.2mm", (cr3032_x, 0, CR3032_H + 4.5), 1.5),
    ("500mAh", (cr3032_x, 0, CR3032_H + 7.0), 1.5),
]

export_glb(glb_shapes, output_path=OUTPUT, labels=labels, cached_scene=dadovida_scene)
print(f"\nShareable: open in 3dviewer.net")
