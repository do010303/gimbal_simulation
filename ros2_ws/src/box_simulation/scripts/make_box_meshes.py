#!/usr/bin/env python3
"""Split the CAD export of the box into one STL per URDF link.

The CAD export (THAN = body, CANHTRAI / CANHPHAI = left / right lid) has NO
assembly placement: all three parts sit on the floor next to each other, in
millimetres, Z up. The lids lie on their back (big plate down, walls up). This
script places them, cuts the four clamp bars out of THAN, and writes every link
mesh in its own link frame, in metres, so box.xacro uses scale 1 (meshes/stl/*.stl) and the joint
origins below.

Model frame (box.xacro): Z up, origin on the ground under the centre of the
body. Every number box.xacro needs is printed at the end; keep the two in sync.

Assembly assumptions (NOT in the CAD export, chosen by comparison with the old
box -- re-run with new values if the real box differs):
  * Lid = outer side panel (the big plate) + half roof (the 520 mm wall at the
    far end of the plate) + two end walls covering only the upper ~480 mm.
    Closed, the panel hangs vertical outside the body wall; the hinge axis runs
    along Y at the bottom (motor) end of the panel, on the small brackets on
    the body side walls (THAN parts at x = +-0.5 m, z = 0.253 m).
  * The clamp bars in THAN are drawn CLOSED. Open = 0.2 m further out, which
    keeps the 0..0.2 m joint travel box_hardware_adapter and box_manager use.

Usage:
    python3 make_box_meshes.py <dir with THAN/CANHTRAI/CANHPHAI .STL.stl> [out_dir]
"""
import os
import sys

import numpy as np
import trimesh

SRC = sys.argv[1]
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', 'meshes', 'stl')

# CAD (mm) -> model frame: centre of the body's top plate, feet on the ground.
BODY_CENTRE_MM = np.array([2118.0, -655.0, 619.0])

HINGE_X = 0.53      # |x| of the lid panel's outer face (body wall is at 0.50)
HINGE_Z = 0.253     # height of the hinge brackets on the body side walls
CLAMP_TRAVEL = 0.2  # m, open -> closed, matches box_hardware_adapter.yaml

# THAN connected components that are clamp bars, found by their bounds (mm).
# (bounds min corner, axis the bar CLOSES along in the model frame, link name)
CLAMPS = [
    ((1793.0, -1005.0, 1340.0), (1, 0, 0), 'clamp_v_1'),   # -x bar, closes +x
    ((2356.0, -1005.0, 1340.0), (-1, 0, 0), 'clamp_v_2'),  # +x bar, closes -x
    ((1977.0, -953.0, 1340.0), (0, 1, 0), 'clamp_h_1'),    # -y bar, closes +y
    ((1977.0, -431.0, 1340.0), (0, -1, 0), 'clamp_h_2'),   # +y bar, closes -y
]

# Lid: the hinge (motor) end of the plate's outer face in CAD mm, the rotation
# that stands the plate up with the roof wall pointing at the body, and side.
LIDS = [
    ('CANHTRAI.STL.stl', 'lid_left', (1251.0, 556.0, 625.0), np.pi / 2, -1),
    ('CANHPHAI.STL.stl', 'lid_right', (2760.0, 451.0, 628.0), -np.pi / 2, 1),
]


def to_model(mesh):
    mesh.apply_translation(-BODY_CENTRE_MM)
    mesh.apply_scale(0.001)
    return mesh


# Triangle budget per link. The raw CAD is ~1.5 M triangles and STL repeats
# every vertex per triangle; in PX4's world the gz SERVER renders the gimbal
# camera, so it loads every visual too, and the full-detail box drove it to
# 7.8 GB RSS and the OOM killer (2026-10-29). (That OOM turned out to be the GStreamer camera leak, not the mesh,
# but a lighter mesh still loads faster.)
FACE_BUDGET = {'base': 80000, 'lid_left': 30000, 'lid_right': 30000}
FACE_BUDGET_DEFAULT = 4000


def save(mesh, name):
    """Merge duplicate vertices, decimate to the budget, write <name>.stl."""
    import open3d as o3d
    g = o3d.geometry.TriangleMesh(o3d.utility.Vector3dVector(mesh.vertices),
                                  o3d.utility.Vector3iVector(mesh.faces))
    g.remove_duplicated_vertices()
    target = FACE_BUDGET.get(name, FACE_BUDGET_DEFAULT)
    if len(g.triangles) > target:
        g = g.simplify_quadric_decimation(target)
    g.remove_degenerate_triangles()
    g.remove_unreferenced_vertices()
    out = trimesh.Trimesh(np.asarray(g.vertices), np.asarray(g.triangles))
    # Binary STL: carries per-face normals (an OBJ without vn lines renders
    # as one flat washed-out colour in gz) and is ~10x smaller than OBJ.
    out.export(os.path.join(OUT, f'{name}.stl'))
    print(f'{name}: {len(mesh.faces)} -> {len(out.faces)} triangles')


def fmt(v):
    return ' '.join(f'{x:.5f}' for x in v)


def main():
    os.makedirs(OUT, exist_ok=True)
    than = trimesh.load(os.path.join(SRC, 'THAN.STL.stl'))
    parts = than.split(only_watertight=False)

    def find(min_corner):
        hits = [p for p in parts if np.allclose(p.bounds[0], min_corner, atol=2.0)]
        if len(hits) != 1:
            sys.exit(f'clamp part at {min_corner}: {len(hits)} matches, CAD changed?')
        return hits[0]

    joints = {}
    clamp_parts = []
    for corner, axis, name in CLAMPS:
        p = find(corner)
        clamp_parts.append(id(p))
        m = to_model(p.copy())
        closed_ref = m.bounds.mean(axis=0)
        # joint origin = where the link frame sits at q = 0 (OPEN)
        origin = closed_ref - CLAMP_TRAVEL * np.array(axis, float)
        # link frame = bar centre, so q = CLAMP_TRAVEL puts it back at closed_ref
        m.apply_translation(-closed_ref)
        save(m, name)
        bb = m.bounds
        joints[name] = (origin, axis, (bb[0] + bb[1]) / 2, bb[1] - bb[0])

    body = trimesh.util.concatenate([p for p in parts if id(p) not in clamp_parts])
    body = to_model(body)
    save(body, 'base')

    for fname, name, hinge_mm, stand_up, side in LIDS:
        m = trimesh.load(os.path.join(SRC, fname))
        m.apply_translation(-np.array(hinge_mm))
        m.apply_scale(0.001)
        m.apply_transform(trimesh.transformations.rotation_matrix(stand_up, (0, 1, 0)))
        save(m, name)
        # opening outward = rotating the top of the panel away from the body
        # (+q about +y swings +z towards +x, so the -x lid needs -y)
        joints[name] = (np.array([side * HINGE_X, 0.0, HINGE_Z]), (0, side, 0), None, None)

    print('base bounds (m):', np.round(body.bounds, 4).tolist())
    for name, (origin, axis, cc, size) in joints.items():
        print(f'{name}_joint origin xyz="{fmt(origin)}" axis xyz="{fmt(axis)}"')
        if cc is not None:
            print(f'    collision (link frame) xyz="{fmt(cc)}" size="{fmt(size)}"')


if __name__ == '__main__':
    main()
