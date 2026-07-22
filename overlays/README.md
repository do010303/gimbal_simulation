# overlays/

Files that belong to packages living **outside** this repository, kept here so
that a fresh clone can reproduce the full drone-in-a-box simulation.

Same idea as the `px4/` directory (which mirrors `~/PX4/Tools/simulation/gz`
and is applied with `rsync`), but for the `box_simulation` package.

## box_simulation

`box_simulation` is the articulated box model (lid + clamps, driven by
ros2_control). It is developed in its own workspace, so M3.5's addition to it
is carried here instead of being committed there.

| File | What it is |
|---|---|
| `launch/box_spawn_only.launch.py` | Spawns the box into an **already running** Gazebo server — PX4 SITL's — instead of starting a private world like the package's own `box.launch.py` does. Also spawns `dib_box_marker` onto the box's landing surface and loads the four ros2_control controllers. |

Apply it with:

```bash
cp overlays/box_simulation/launch/box_spawn_only.launch.py \
   <path-to>/box_simulation/launch/
colcon build --packages-select box_simulation
```

`box.launch.py` is deliberately **not** overridden: it still starts its own
standalone world, so the older standalone box test stays reproducible.

## What must NOT be added to box_simulation

Do not put the fractal marker into `box.xacro` as a `<visual>` inside
`<gazebo reference="base_link">`. It looks correct and fails silently:
sdformat's URDF parser strips the `<visual>` wrapper and merges the children
into the link's existing `base_link_visual`, which then holds two `<pose>` and
two `<geometry>` elements. The first of each wins, so the marker plane is
discarded with no error and no warning — the box renders normally and the
landing surface is simply blank.

Verified by diffing the xacro output against `gz sdf -p`: the URDF contains
the marker visual once, the converted SDF contains it zero times. URDF also has
no `<plane>` geometry and no PBR `albedo_map`.

That is why the marker is a separate SDF model (`dib_box_marker`, shipped in
`px4/Tools/simulation/gz/models/`) spawned at a pose derived from the box's
own spawn pose.
