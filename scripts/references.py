"""Generate a GLB with the DadoVida assembly surrounded by reference objects for scale."""

import cadquery as cq
import numpy as np
import trimesh

from mobit.export_glb import export_glb

# Reference objects: (name, shape_type, dimensions, description)
REFERENCES = [
    ("Lingo", "cylinder", {"d": 35.0, "h": 5.0}, "Abbott Lingo CGM (target form factor)"),
    ("Libre 3", "cylinder", {"d": 21.0, "h": 2.9}, "FreeStyle Libre 3"),
    ("Dexcom G7", "box", {"x": 27.3, "y": 24.1, "z": 4.7}, "Dexcom G7 sensor"),
    ("CR2032", "cylinder", {"d": 20.0, "h": 3.2}, "CR2032 coin cell"),
    ("CR2025", "cylinder", {"d": 20.0, "h": 2.5}, "CR2025 coin cell"),
    ("CR1632", "cylinder", {"d": 16.0, "h": 3.2}, "CR1632 coin cell"),
    ("LIR2032", "cylinder", {"d": 20.0, "h": 3.2}, "LIR2032 rechargeable"),
    ("CR2430", "cylinder", {"d": 24.0, "h": 3.0}, "CR2430 (270mAh)"),
    ("CR2450", "cylinder", {"d": 24.0, "h": 5.0}, "CR2450 (600mAh)"),
    ("CR2477", "cylinder", {"d": 24.0, "h": 7.7}, "CR2477 (1000mAh)"),
    ("CR3032", "cylinder", {"d": 30.0, "h": 3.2}, "CR3032 (500mAh)"),
    ("SR626SW", "cylinder", {"d": 6.8, "h": 2.6}, "SR626SW (28mAh, Libre battery)"),
]

# Layout: place references in a row to the right of where the assembly would be
SPACING = 35.0  # mm between each reference
START_X = 30.0  # offset from origin

glb_shapes = []
labels = []

for i, (name, shape_type, dims, desc) in enumerate(REFERENCES):
    x_offset = START_X + i * SPACING
    y_offset = 0

    if shape_type == "cylinder":
        shape = (
            cq.Workplane("XY")
            .circle(dims["d"] / 2)
            .extrude(dims["h"])
            .translate((x_offset, y_offset, 0))
        )
        label_z = dims["h"] + 1.0
        dim_text = f'{dims["d"]:.0f}x{dims["h"]:.1f}'
    else:  # box
        shape = (
            cq.Workplane("XY")
            .box(dims["x"], dims["y"], dims["z"])
            .translate((x_offset, y_offset, dims["z"] / 2))
        )
        label_z = dims["z"] + 1.0
        dim_text = f'{dims["x"]:.0f}x{dims["y"]:.0f}x{dims["z"]:.1f}'

    glb_shapes.append((name, "references", "*", shape))

    # Name label on top
    labels.append((name, (x_offset, y_offset, label_z), 2.0))
    # Dimension label below name
    labels.append((dim_text, (x_offset, y_offset, label_z + 2.5), 1.2))

    print(f"  {name}: {dim_text}mm")

# Load the cached DadoVida assembly GLB
import os
CACHED_GLB = "cad/dadovida.glb"
if os.path.exists(CACHED_GLB):
    print(f"  Loading cached assembly: {CACHED_GLB}")
    dadovida_scene = trimesh.load(CACHED_GLB)

    # Get bounding box for label placement
    dadovida_bounds = dadovida_scene.bounds
    dv_height = dadovida_bounds[1][2]
    dv_x = dadovida_bounds[1][0] - dadovida_bounds[0][0]
    dv_y = dadovida_bounds[1][1] - dadovida_bounds[0][1]

    # Add all meshes from the cached scene
    for mesh_name, mesh_geom in dadovida_scene.geometry.items():
        glb_shapes.append((f"DadoVida/{mesh_name}", "references", "*", None))

    # We'll add the cached scene directly to the export scene later
    cached_scene = dadovida_scene
else:
    print(f"  Warning: {CACHED_GLB} not found. Run 'task build' first.")
    cached_scene = None
    dv_height = 12
    dv_x = 26
    dv_y = 23

# DadoVida label
labels.append(("DadoVida", (0, 0, dv_height + 1.0), 2.0))
dim_text = f"{dv_x:.0f}x{dv_y:.0f}x{dv_height:.0f}"
labels.append((dim_text, (0, 0, dv_height + 3.5), 1.2))

# Add reference material
import json
materials_path = "cad/materials.json"
with open(materials_path) as f:
    mats = json.load(f)
if "reference_clear" not in mats["materials"]:
    mats["materials"]["reference_clear"] = {
        "baseColor": [0.6, 0.8, 1.0, 0.5],
        "metallic": 0.0,
        "roughness": 0.3,
        "description": "Translucent blue reference shape"
    }
    with open(materials_path, "w") as f:
        json.dump(mats, f, indent=2)

# Add reference assignment
assignments_path = "cad/material_assignments.json"
with open(assignments_path) as f:
    assigns = json.load(f)
assigns["references"] = {"*": "reference_clear"}
with open(assignments_path, "w") as f:
    json.dump(assigns, f, indent=2)

# Filter out the placeholder DadoVida shapes (we'll add from cached scene)
glb_shapes = [s for s in glb_shapes if not s[0].startswith("DadoVida/")]

export_glb(glb_shapes, output_path="cad/dadovida_references.glb", labels=labels, cached_scene=cached_scene)
