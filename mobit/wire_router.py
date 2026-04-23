"""3D wire routing module.

Routes wires between pins on two PCBs using voxelized pathfinding.
Board-agnostic — works with any two boards that have pin position dicts.

Pipeline: board shapes → trimesh → voxelize → pathfind → smooth → render
"""

import math
import warnings

import cadquery as cq
import numpy as np
import trimesh
from scipy import ndimage
from scipy.interpolate import make_interp_spline
from pathfinding3d.core.grid import Grid
from pathfinding3d.core.diagonal_movement import DiagonalMovement
from pathfinding3d.finder.theta_star import ThetaStarFinder

from OCP.gp import gp_Pnt, gp_Dir, gp_Ax2
from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder


# --- Step 1: CadQuery to trimesh conversion ---

def cq_shape_to_trimesh(shape):
    """Convert a CadQuery Workplane or Shape to a trimesh.Trimesh."""
    if hasattr(shape, "val"):
        solid = shape.val()
    else:
        solid = shape

    vertices, faces = solid.tessellate(0.1)
    v_array = np.array([(v.x, v.y, v.z) for v in vertices])
    f_array = np.array(faces)
    return trimesh.Trimesh(vertices=v_array, faces=f_array)


# --- Step 2: Voxelization ---

def build_occupancy_grid(meshes, resolution=0.5, clearance=1.0, wire_radius=0.5, padding=3.0):
    """Voxelize board meshes into a 3D occupancy grid with clearance buffer.

    Returns (obstacle_grid, origin, resolution) where:
        obstacle_grid: 3D bool ndarray (True = blocked)
        origin: world-space coordinate of voxel [0,0,0]
        resolution: voxel size in mm
    """
    combined = trimesh.util.concatenate(meshes)

    # Compute padded bounding box
    bbox_min = combined.bounds[0] - padding
    bbox_max = combined.bounds[1] + padding

    # Create the voxel grid
    voxelized = combined.voxelized(pitch=resolution)
    grid = voxelized.matrix.copy()

    # The voxelized grid has its own origin/transform
    voxel_origin = voxelized.transform[:3, 3]

    # Inflate obstacles for wire clearance
    inflate_radius = math.ceil((wire_radius + clearance) / resolution)
    if inflate_radius > 0:
        struct = ndimage.generate_binary_structure(3, 3)  # 26-connected
        grid = ndimage.binary_dilation(grid, structure=struct, iterations=inflate_radius)

    # Pad the grid so wires can route around the outside
    pad_voxels = math.ceil(padding / resolution)
    grid = np.pad(grid, pad_voxels, mode="constant", constant_values=False)
    origin = voxel_origin - pad_voxels * resolution

    return grid, origin, resolution


# --- Step 3: Pathfinding ---

def world_to_grid(point, origin, resolution):
    """Convert world-space coordinate to grid indices."""
    ijk = np.round((np.array(point) - origin) / resolution).astype(int)
    return tuple(ijk)


def grid_to_world(ijk, origin, resolution):
    """Convert grid indices to world-space coordinate."""
    return origin + np.array(ijk, dtype=float) * resolution


def find_path(obstacle_grid, start_world, end_world, origin, resolution):
    """Find a collision-free path through the voxel grid using Theta*.

    Returns list of world-space 3D points.
    Falls back to straight line if no path found.
    """
    start_ijk = world_to_grid(start_world, origin, resolution)
    end_ijk = world_to_grid(end_world, origin, resolution)

    # Clamp to grid bounds
    shape = obstacle_grid.shape
    start_ijk = tuple(max(0, min(s - 1, v)) for v, s in zip(start_ijk, shape))
    end_ijk = tuple(max(0, min(s - 1, v)) for v, s in zip(end_ijk, shape))

    # Build pathfinding grid (1 = walkable, 0 = obstacle)
    walkable = (~obstacle_grid).astype(np.int32)

    # Ensure start and end plus their neighbors are walkable
    # (pins may be inside the inflated obstacle zone)
    for ijk in [start_ijk, end_ijk]:
        for dx in range(-3, 4):
            for dy in range(-3, 4):
                for dz in range(-3, 4):
                    ni, nj, nk = ijk[0] + dx, ijk[1] + dy, ijk[2] + dz
                    if 0 <= ni < shape[0] and 0 <= nj < shape[1] and 0 <= nk < shape[2]:
                        walkable[ni, nj, nk] = 1

    grid = Grid(matrix=walkable)
    start_node = grid.node(*start_ijk)
    end_node = grid.node(*end_ijk)

    finder = ThetaStarFinder(diagonal_movement=DiagonalMovement.always)
    path, _ = finder.find_path(start_node, end_node, grid)

    if not path:
        warnings.warn(f"No path found from {start_world} to {end_world}, using straight line")
        return [np.array(start_world), np.array(end_world)]

    # Convert grid path to world coordinates
    # pathfinding3d returns GridNode objects with x, y, z attributes
    world_path = [grid_to_world((node.x, node.y, node.z), origin, resolution) for node in path]
    return world_path


# --- Step 4: Path smoothing ---

def smooth_path(waypoints, spacing=0.5):
    """Smooth raw waypoints into a dense B-spline curve.

    Returns list of uniformly-spaced 3D points.
    """
    pts = np.array(waypoints)
    if len(pts) < 3:
        return [pts[0], pts[-1]]

    # Chord-length parameterization
    diffs = np.diff(pts, axis=0)
    seg_lengths = np.linalg.norm(diffs, axis=1)
    t = np.concatenate([[0], np.cumsum(seg_lengths)])
    total_length = t[-1]

    if total_length < 0.01:
        return [pts[0]]

    # Cubic B-spline (or lower degree if too few points)
    k = min(3, len(pts) - 1)
    spline = make_interp_spline(t, pts, k=k)

    # Resample at uniform spacing
    num_samples = max(int(total_length / spacing), 2)
    t_new = np.linspace(0, total_length, num_samples)
    smooth_pts = spline(t_new)

    return [smooth_pts[i] for i in range(len(smooth_pts))]


# --- Step 5: Wire rendering ---

def render_wire(points, radius, color, signal_name):
    """Render a wire path as a single continuous pipe solid.

    Uses BRepOffsetAPI_MakePipe to sweep a circle along a spline —
    one solid per wire, no seams.

    Returns list of (name, cq_shape, color_tuple).
    """
    from OCP.BRepOffsetAPI import BRepOffsetAPI_MakePipe
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire, BRepBuilderAPI_MakeFace
    from OCP.gp import gp_Circ
    from cadquery import Vector

    # Build spline through all points
    vectors = [Vector(*pt) for pt in points]
    try:
        spline_edge = cq.Edge.makeSpline(vectors)
        spine_wire = cq.Wire.assembleEdges([spline_edge])

        # Circle profile at start, oriented along initial tangent
        start = np.array(points[0])
        next_pt = np.array(points[1])
        tangent = next_pt - start
        tangent = tangent / np.linalg.norm(tangent)

        ax = gp_Ax2(gp_Pnt(*start), gp_Dir(*tangent))
        circle = gp_Circ(ax, radius)
        circle_edge = BRepBuilderAPI_MakeEdge(circle).Edge()
        circle_wire = BRepBuilderAPI_MakeWire(circle_edge).Wire()
        profile_face = BRepBuilderAPI_MakeFace(circle_wire).Face()

        # Single pipe sweep — one solid, no seams
        pipe = BRepOffsetAPI_MakePipe(spine_wire.wrapped, profile_face)
        pipe.Build()
        pipe_shape = pipe.Shape()

        wire_solid = cq.Workplane().add(cq.Shape(pipe_shape))
        return [(f"wire_{signal_name}", wire_solid, color)]

    except Exception as e:
        # Fallback: cylinders if pipe fails
        print(f"    MakePipe failed for {signal_name}: {e}, using cylinder fallback")
        results = []
        for i in range(len(points) - 1):
            a = np.array(points[i])
            b = np.array(points[i + 1])
            seg_vec = b - a
            seg_len = float(np.linalg.norm(seg_vec))
            if seg_len < 0.01:
                continue
            seg_dir = seg_vec / seg_len
            ax = gp_Ax2(gp_Pnt(*a), gp_Dir(*seg_dir))
            cyl = BRepPrimAPI_MakeCylinder(ax, radius, seg_len).Shape()
            results.append((f"wire_{signal_name}_s{i}", cq.Workplane().add(cq.Shape(cyl)), color))
        return results


# --- Step 6: Top-level API ---

DEFAULT_WIRE_COLORS = {
    "3V3": (1.0, 0.0, 0.0),
    "GND": (0.15, 0.15, 0.15),
    "SDA": (0.0, 0.3, 1.0),
    "SCL": (1.0, 0.85, 0.0),
}


def route_wires(
    board_shapes,
    pin_positions_a,
    pin_positions_b,
    connections,
    wire_radius=0.5,
    grid_resolution=0.5,
    clearance=1.0,
    wire_colors=None,
    exit_dir_a=None,
    entry_dir_b=None,
    exit_distance=2.0,
):
    """Route wires between two boards using 3D pathfinding.

    Args:
        board_shapes: list of CadQuery Workplane objects (positioned in assembly space)
        pin_positions_a: dict of pin_name → np.ndarray (3D position in assembly space)
        pin_positions_b: dict of pin_name → np.ndarray (3D position in assembly space)
        connections: list of connection dicts from connections.json
        wire_radius: wire radius in mm
        grid_resolution: voxel size in mm
        clearance: min distance from wire to board geometry in mm
        wire_colors: dict of signal_name → (r, g, b) tuple

    Returns:
        list of (name, cq_shape, color_tuple) ready to add to assembly
    """
    if wire_colors is None:
        wire_colors = DEFAULT_WIRE_COLORS

    # Convert board shapes to trimesh
    print("  Converting board geometry to mesh...")
    meshes = [cq_shape_to_trimesh(s) for s in board_shapes]

    # Build occupancy grid
    print("  Voxelizing...")
    obstacle_grid, origin, res = build_occupancy_grid(
        meshes, resolution=grid_resolution, clearance=clearance, wire_radius=wire_radius
    )
    print(f"  Grid size: {obstacle_grid.shape}, {obstacle_grid.sum()} blocked voxels")

    all_shapes = []

    for conn in connections:
        signal = conn["signal"]
        pin_a_name = conn["from"]["pin"]
        pin_b_name = conn["to"]["pin"]
        color = wire_colors.get(signal, (0.5, 0.5, 0.5))

        start = pin_positions_a[pin_a_name]
        end = pin_positions_b[pin_b_name]

        # Compute exit/entry forced waypoints
        if exit_dir_a is not None:
            start_forced = start + np.array(exit_dir_a) * exit_distance
        else:
            start_forced = start

        if entry_dir_b is not None:
            end_forced = end - np.array(entry_dir_b) * exit_distance
        else:
            end_forced = end

        # Pathfind between the forced intermediate points
        print(f"  Routing {signal}: {pin_a_name} → {pin_b_name}...", end="")
        raw_path = find_path(obstacle_grid, start_forced, end_forced, origin, res)

        # Prepend start and append end to get the full path
        raw_path = [start] + raw_path + [end]
        print(f" {len(raw_path)} waypoints", end="")

        # Smooth
        smooth = smooth_path(raw_path, spacing=0.3)
        print(f" → {len(smooth)} smooth points")

        # Mark the SMOOTHED path as obstacle so subsequent wires avoid it
        wire_inflate = max(1, math.ceil(wire_radius * 2 / res))
        for pt in smooth:
            ijk = world_to_grid(pt, origin, res)
            for dx in range(-wire_inflate, wire_inflate + 1):
                for dy in range(-wire_inflate, wire_inflate + 1):
                    for dz in range(-wire_inflate, wire_inflate + 1):
                        ni = ijk[0] + dx
                        nj = ijk[1] + dy
                        nk = ijk[2] + dz
                        if (0 <= ni < obstacle_grid.shape[0] and
                            0 <= nj < obstacle_grid.shape[1] and
                            0 <= nk < obstacle_grid.shape[2]):
                            obstacle_grid[ni, nj, nk] = True

        # Render
        shapes = render_wire(smooth, wire_radius, color, signal)
        all_shapes.extend(shapes)

    return all_shapes
