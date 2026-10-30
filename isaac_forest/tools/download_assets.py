"""Descarga los recursos CC0 de Poly Haven (https://polyhaven.com) que usan las escenas en assets/.

    python3 tools/download_assets.py            # 2k, ~450 MB
Cada archivo se verifica con el MD5 publicado por la API de Poly Haven.
Basado en ~/NELSON/ISAAC_AGRO/scripts/download_assets.py.
"""
import argparse
import glob
import hashlib
import json
import os
import urllib.request

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'assets')
API = 'https://api.polyhaven.com/files/'
UA = {'User-Agent': 'shagai-forest'}

HDRIS = ['rainforest_trail', 'farmland_overcast']        # v2 (selva) y v1 (campo nublado)
TEXTURES = ['forest_leaves_02',                          # suelo de v2 (hojarasca)
            'forrest_ground_01',                         # suelo de v1
            'bark_brown_01', 'bark_brown_02', 'chinese_hackberry_bark', 'japanese_zelkova_bark']   # cortezas
MODELS = {   # carpeta -> modelos (solo v2)
    'understory': ['fern_02', 'calathea_orbifolia_01', 'anthurium_botany_01', 'shrub_02', 'shrub_03'],
    'deadwood': ['tree_stump_01', 'tree_stump_02', 'dead_tree_trunk', 'dead_tree_trunk_02', 'root_cluster_01',
                 'bark_debris_01', 'dry_branches_medium_01'],
    'rocks': ['rock_moss_set_01', 'rock_moss_set_02', 'boulder_01'],
}
TEX_MAPS = {'Diffuse': 'diff', 'nor_gl': 'nor_gl', 'Rough': 'rough', 'AO': 'ao'}


def get_json(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return json.load(r)


def fetch(url, md5, dest):
    if os.path.exists(dest) and hashlib.md5(open(dest, 'rb').read()).hexdigest() == md5:
        return False
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=300) as r:
        data = r.read()
    if hashlib.md5(data).hexdigest() != md5:
        raise RuntimeError(f'MD5 distinto en {url}')
    with open(dest, 'wb') as f:
        f.write(data)
    return True


def to_8bit_masks(model_dir):
    """Las máscaras alfa de Poly Haven son PNG de 16 bits y RTX las lee mal: copia de 8 bits."""
    import numpy as np
    from PIL import Image
    for f in glob.glob(os.path.join(model_dir, 'textures', '*_alpha_*.png')):
        out = f.replace('_alpha_', '_alpha8_')
        if '_alpha8' in f or os.path.exists(out):
            continue
        a = np.asarray(Image.open(f)).astype(np.float32)
        a = a / 257.0 if a.max() > 255 else a
        Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), mode='L').save(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--res', default='2k', choices=['1k', '2k', '4k'])
    args = ap.parse_args()
    for name in HDRIS:
        info = get_json(API + name)['hdri'][args.res]['hdr']
        fetch(info['url'], info['md5'], os.path.join(ROOT, 'hdri', f'{name}_{args.res}.hdr'))
        print('ok hdri/' + name)
    for name in TEXTURES:
        files = get_json(API + name)
        for key, short in TEX_MAPS.items():
            if key in files:
                info = files[key][args.res]['jpg']
                fetch(info['url'], info['md5'], os.path.join(ROOT, 'textures', name, f'{name}_{short}_{args.res}.jpg'))
        print('ok textures/' + name)
    for group, names in MODELS.items():
        for name in names:
            usd = get_json(API + name)['usd'][args.res]['usd']
            base = os.path.join(ROOT, 'props', group, name)
            fetch(usd['url'], usd['md5'], os.path.join(base, os.path.basename(usd['url'])))
            for rel, inc in usd.get('include', {}).items():
                fetch(inc['url'], inc['md5'], os.path.join(base, rel))
            to_8bit_masks(base)
            print(f'ok props/{group}/{name}')


if __name__ == '__main__':
    main()
