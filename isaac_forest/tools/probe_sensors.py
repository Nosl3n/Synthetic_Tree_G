"""Prueba mínima: abre el bosque, crea LiDAR + cámara, imprime qué devuelven."""
import os, sys, traceback
from isaacsim.simulation_app import SimulationApp
app = SimulationApp({"headless": True})
import numpy as np
import isaacsim.core.experimental.utils.stage as stage_utils
import isaacsim.core.experimental.utils.app as app_utils
from isaacsim.sensors.experimental.rtx import (Lidar, LidarSensor, RtxCamera, CameraSensor,
    parse_generic_model_output_data, parse_stable_id_map_data, parse_object_ids)
try:
    stage_utils.open_stage(os.path.abspath(sys.argv[1]))
    lidar = Lidar.create(path="/World/Rig/lidar", config="OS1", variant="OS1_REV6_128ch10hz1024res",
                         aux_output_level="FULL", tick_rate=10.0, accumulate_outputs=True,
                         translations=[[0.0, 0.0, 1.8]])
    ls = LidarSensor(lidar, annotators=["generic-model-output", "stable-id-map"])
    cam = RtxCamera("/World/Rig/cam", tick_rate=30.0, translations=[[0.0, 0.0, 1.2]],
                    orientations=[[0.5, 0.5, -0.5, -0.5]])
    cs = CameraSensor(cam, resolution=(480, 848), annotators=["rgb", "distance_to_image_plane", "semantic_segmentation"])
    app_utils.play(commit=True)
    seen = set()
    for i in range(40):
        app.update()
        d, info = ls.get_data("generic-model-output")
        if d is not None and len(d):
            g = parse_generic_model_output_data(d)
            key = (g.frameEnd.timestampNs if hasattr(g.frameEnd, 'timestampNs') else i)
            if g.numElements and key not in seen:
                seen.add(key)
                x, y, z = np.asarray(g.x), np.asarray(g.y), np.asarray(g.z)
                print(f"[{i}] GMO n={g.numElements} coords={g.elementsCoordsType} x[{x.min():.1f},{x.max():.1f}] "
                      f"y[{y.min():.1f},{y.max():.1f}] z[{z.min():.1f},{z.max():.1f}] scalar={np.asarray(g.scalar)[:3]}")
                print("   attrs:", [a for a in dir(g) if not a.startswith('_')])
                print("   frameEnd:", [a for a in dir(g.frameEnd) if not a.startswith('_')])
                s, _ = ls.get_data("stable-id-map")
                if s is not None and len(s):
                    m = parse_stable_id_map_data(s)
                    ids = parse_object_ids(np.asarray(g.objId))
                    paths = [m.get(o, '?') for o in ids[:2000]]
                    from collections import Counter
                    print("   paths:", Counter(p.split('/')[-1] for p in paths).most_common(6))
        if i in (20, 39):
            for a in ["rgb", "distance_to_image_plane", "semantic_segmentation"]:
                v, inf = cs.get_data(a)
                if v is not None:
                    v = v.numpy() if hasattr(v, 'numpy') else np.asarray(v)
                    print(f"[{i}] cam {a} {v.shape} {v.dtype} min={np.nanmin(v[np.isfinite(v)]) if v.size else None} max={np.nanmax(v[np.isfinite(v)]) if v.size else None} info={ {k: (str(w)[:200]) for k, w in inf.items()} }")
except Exception:
    traceback.print_exc()
app.close()
