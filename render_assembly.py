"""Render the stacked assembly to PNG using cadquery-png-plugin."""

import cadquery as cq
from cadquery_png_plugin.plugin import (
    convert_assembly_to_vtk,
    setup_render_window,
    setup_camera,
    save_render_window_to_png,
)

# Load the full assembly STEP (built by build_assembly.py)
shape = cq.importers.importStep("cad/dadovida_stack.step")

assembly = cq.Assembly()
assembly.add(shape, name="dadovida_stack", color=cq.Color(0.3, 0.3, 0.3, 1))


def render_view(assy, view, filename, width=1200, height=900, zoom=1.0):
    face_actors, edge_actors = convert_assembly_to_vtk(
        assy, edge_width=1, color_theme="default", edge_color=(0, 0, 0)
    )
    render_window = setup_render_window(
        face_actors, edge_actors, width, height, background_color=(0.9, 0.9, 0.9)
    )
    setup_camera(render_window.GetRenderers().GetFirstRenderer(), view, zoom=zoom)
    save_render_window_to_png(render_window, filename)
    print(f"Rendered: {filename}")


render_view(assembly, "front-top-right", "docs/assembly_iso.png", zoom=0.7)
render_view(assembly, "top", "docs/assembly_top.png", zoom=0.7)
