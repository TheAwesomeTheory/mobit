"""Export CadQuery assembly to GLB with PBR materials.

Reads materials.json for material definitions and material_assignments.json
for component-to-material mapping. Outputs a GLB file viewable in any
web viewer (3dviewer.net, etc.) with proper colors, metallic, roughness.
"""

import json
import fnmatch

import numpy as np
import trimesh
from trimesh.visual.material import PBRMaterial


def load_materials(path="cad/materials.json"):
    with open(path) as f:
        return json.load(f)["materials"]


def load_assignments(path="cad/material_assignments.json"):
    with open(path) as f:
        data = json.load(f)
        data.pop("_doc", None)
        return data


def make_pbr_material(mat_def, name):
    """Create a trimesh PBRMaterial from a material definition dict."""
    base = mat_def["baseColor"]
    return PBRMaterial(
        name=name,
        baseColorFactor=base,
        metallicFactor=mat_def.get("metallic", 0.0),
        roughnessFactor=mat_def.get("roughness", 0.5),
    )


def resolve_material(component_name, board_assignments, materials):
    """Find the material for a component using exact match or wildcard."""
    # Try exact match first
    if component_name in board_assignments:
        mat_name = board_assignments[component_name]
        if mat_name in materials:
            return make_pbr_material(materials[mat_name], mat_name)

    # Try wildcard patterns
    for pattern, mat_name in board_assignments.items():
        if fnmatch.fnmatch(component_name, pattern):
            if mat_name in materials:
                return make_pbr_material(materials[mat_name], mat_name)

    return None


def cq_shape_to_trimesh_with_material(shape, material=None):
    """Convert a CadQuery shape to trimesh with an optional PBR material."""
    if hasattr(shape, "val"):
        solid = shape.val()
    else:
        solid = shape

    vertices, faces = solid.tessellate(0.1)
    v_array = np.array([(v.x, v.y, v.z) for v in vertices])
    f_array = np.array(faces)

    mesh = trimesh.Trimesh(vertices=v_array, faces=f_array)

    if material is not None:
        mesh.visual = trimesh.visual.TextureVisuals(material=material)

    return mesh


def create_label(text, position, font_size=1.0, thickness=0.1):
    """Create 3D extruded text at a position, facing up (+Z).

    Returns a trimesh mesh with white material, or None on failure.
    """
    import cadquery as cq

    try:
        label = cq.Workplane("XY").text(text, font_size, thickness)
        bb = label.val().BoundingBox()
        # Center text horizontally, then move to position
        label = label.translate((
            position[0] - bb.xlen / 2 - bb.xmin,
            position[1] - bb.ylen / 2 - bb.ymin,
            position[2] - bb.zmin,
        ))

        vertices, faces = label.val().tessellate(0.05)
        v_array = np.array([(v.x, v.y, v.z) for v in vertices])
        f_array = np.array(faces)
        mesh = trimesh.Trimesh(vertices=v_array, faces=f_array)

        white_mat = PBRMaterial(
            name=f"label_{text}",
            baseColorFactor=[1.0, 1.0, 1.0, 1.0],
            metallicFactor=0.0,
            roughnessFactor=0.9,
        )
        mesh.visual = trimesh.visual.TextureVisuals(material=white_mat)
        return mesh
    except Exception as e:
        print(f"  Warning: could not create label '{text}': {e}")
        return None


def export_glb(
    assembly_shapes,
    output_path="cad/dadovida.glb",
    materials_path="cad/materials.json",
    assignments_path="cad/material_assignments.json",
    labels=None,
    cached_scene=None,
):
    """Export named shapes to GLB with PBR materials.

    Args:
        assembly_shapes: list of (node_name, board_key, component_name, cq_shape) tuples.
            board_key: key in material_assignments.json (e.g., "bno085", "xiao", "wires")
            component_name: component name to look up in assignments
        output_path: where to write the GLB
        materials_path: path to materials.json
        assignments_path: path to material_assignments.json
    """
    materials = load_materials(materials_path)
    assignments = load_assignments(assignments_path)

    scene = trimesh.Scene()

    for node_name, board_key, component_name, shape in assembly_shapes:
        board_assignments = assignments.get(board_key, {})
        material = resolve_material(component_name, board_assignments, materials)

        if material is None:
            # Default gray
            material = make_pbr_material({
                "baseColor": [0.5, 0.5, 0.5, 1.0],
                "metallic": 0.0,
                "roughness": 0.5,
            }, "default_gray")

        try:
            mesh = cq_shape_to_trimesh_with_material(shape, material)
            if len(mesh.faces) > 0:
                scene.add_geometry(mesh, node_name=node_name)
        except Exception as e:
            print(f"  Warning: could not export {node_name}: {e}")

    # Merge cached scene if provided (e.g., pre-built assembly)
    if cached_scene is not None:
        for mesh_name, mesh_geom in cached_scene.geometry.items():
            scene.add_geometry(mesh_geom, node_name=mesh_name)

    # Add text labels if provided
    # labels: list of (text, (x, y, z), font_size)
    if labels:
        print(f"  Adding {len(labels)} labels...")
        for text, position, font_size in labels:
            mesh = create_label(text, position, font_size=font_size)
            if mesh is not None and len(mesh.faces) > 0:
                scene.add_geometry(mesh, node_name=f"label_{text}")

    scene.export(output_path)
    print(f"Exported: {output_path} ({len(scene.geometry)} meshes)")
