"""Video de muestra de una grabación: RGB | profundidad | segmentación, y LiDAR (planta y alzado).

    python3 tools/make_video.py recordings/v2_bosque --out videos/v2_bosque.mp4
Necesita ffmpeg en el PATH. 10 fotogramas por segundo = tiempo real de la simulación.
"""
import argparse
import glob
import json
import os
import subprocess

import numpy as np
from matplotlib import colormaps
from PIL import Image, ImageDraw, ImageFont

CLASS_RGB = np.array([[140, 190, 240], [158, 133, 92], [115, 56, 13], [230, 153, 51], [38, 178, 64],
                      [64, 209, 89], [171, 89, 199], [120, 128, 150], [128, 128, 128]], np.uint8)
NAMES = ['cielo', 'suelo', 'tronco', 'rama', 'hoja', 'sotobosque', 'madera muerta', 'roca', 'otro']
W_PANEL, H_PANEL = 640, 362                    # cada imagen de la cámara (848x480 reducida)
W_LID, H_LID = 960, 540                        # cada vista del LiDAR


def font(size):
    for f in ('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', '/usr/share/fonts/TTF/DejaVuSans-Bold.ttf'):
        if os.path.exists(f):
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def raster(P, C, u, v, extent_u, extent_v, W, H, order):
    """Proyección ortográfica de puntos coloreados por clase (los de `order` mayor se dibujan encima)."""
    img = np.full((H, W, 3), 18, np.uint8)
    x = ((P[:, u] - extent_u[0]) / (extent_u[1] - extent_u[0]) * (W - 1)).astype(int)
    y = ((1 - (P[:, v] - extent_v[0]) / (extent_v[1] - extent_v[0])) * (H - 1)).astype(int)
    ok = (x >= 0) & (x < W) & (y >= 0) & (y < H)
    o = np.argsort(order[ok])
    img[y[ok][o], x[ok][o]] = CLASS_RGB[C[ok][o]]
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('rec')
    ap.add_argument('--out', required=True)
    ap.add_argument('--fps', type=int, default=10)
    ap.add_argument('--range', type=float, default=30.0, help='radio de la vista del LiDAR (m)')
    args = ap.parse_args()
    meta = json.load(open(os.path.join(args.rec, 'meta.json')))
    fs = sorted(glob.glob(os.path.join(args.rec, 'frames', '*.npz')))
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    W, H = 3 * W_PANEL, H_PANEL + H_LID + 40
    ff = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
                           '-s', f'{W}x{H}', '-r', str(args.fps), '-i', '-', '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
                           '-crf', '20', args.out], stdin=subprocess.PIPE)
    turbo = (colormaps['turbo'](np.linspace(0, 1, 256))[:, :3] * 255).astype(np.uint8)
    f_big, f_small = font(22), font(16)
    title = os.path.basename(os.path.normpath(args.rec))
    present = set()
    for f in fs:
        z = np.load(f)
        present |= set(np.unique(z['lidar_label']).tolist()) | set(np.unique(z['sem']).tolist())
    for k, f in enumerate(fs):
        z = np.load(f)
        rgb = np.asarray(Image.fromarray(z['rgb']).resize((W_PANEL, H_PANEL)))
        d = np.clip(z['depth'].astype(float) / 40.0, 0, 1)
        dep = turbo[(d * 255).astype(int)]
        dep[z['depth'] == 0] = 20
        dep = np.asarray(Image.fromarray(dep).resize((W_PANEL, H_PANEL)))
        sem = np.asarray(Image.fromarray(CLASS_RGB[z['sem']]).resize((W_PANEL, H_PANEL), Image.NEAREST))
        P, C = z['lidar_xyz'].astype(float), z['lidar_label']
        c = z['lidar_pose'][:3, 3]
        R = args.range
        top = raster(P, C, 0, 1, (c[0] - R * 16 / 9, c[0] + R * 16 / 9), (c[1] - R, c[1] + R), W_LID, H_LID, P[:, 2])
        side = raster(P, C, 0, 2, (c[0] - R * 16 / 9, c[0] + R * 16 / 9), (c[2] - 3, c[2] - 3 + 2 * R * 9 / 16 * 1.8),
                      W_LID, H_LID, -P[:, 1])
        frame = Image.new('RGB', (W, H), (12, 12, 16))
        for i, im in enumerate((rgb, dep, sem)):
            frame.paste(Image.fromarray(im), (i * W_PANEL, 0))
        frame.paste(Image.fromarray(top), (0, H_PANEL))
        frame.paste(Image.fromarray(side), (W_LID, H_PANEL))
        dr = ImageDraw.Draw(frame)
        for i, t in enumerate(('RGB', 'Profundidad (0-40 m)', 'Segmentación')):
            dr.text((i * W_PANEL + 10, 8), t, fill='white', font=f_big, stroke_width=2, stroke_fill='black')
        dr.text((10, H_PANEL + 8), 'LiDAR: planta', fill='white', font=f_big)
        dr.text((W_LID + 10, H_PANEL + 8), 'LiDAR: alzado', fill='white', font=f_big)
        # cruz en la posición del sensor en la planta
        cx, cy = W_LID // 2, H_PANEL + H_LID // 2
        dr.line([(cx - 8, cy), (cx + 8, cy)], fill='white', width=2)
        dr.line([(cx, cy - 8), (cx, cy + 8)], fill='white', width=2)
        x = 10
        for c_ in sorted(present):
            if c_ == 0:
                continue
            dr.rectangle([x, H - 30, x + 18, H - 12], fill=tuple(int(v) for v in CLASS_RGB[c_]))
            dr.text((x + 24, H - 32), NAMES[c_], fill='white', font=f_small)
            x += 40 + 10 * len(NAMES[c_])
        dr.text((W - 420, H - 32), f'{title}   t = {float(z["t"]):5.1f} s   {len(P)} puntos', fill='white',
                font=f_small)
        ff.stdin.write(np.asarray(frame).tobytes())
    ff.stdin.close()
    ff.wait()
    print(f'{len(fs)} fotogramas -> {args.out}')


if __name__ == '__main__':
    main()
