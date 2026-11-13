#!/usr/bin/env python3
"""Synthetic 3D plant data - presentation (English, technical, willow theme)."""
import os
import shutil
from PIL import Image
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

ROOT = '/home/angel/qsm_work'
FIGS = os.path.join(ROOT, 'paper/figs')
APPLE = os.path.join(ROOT, 'apple')
OT = '/home/angel/dev/orchard_twins'
OUT = os.path.join(ROOT, 'paper/Synthetic_Tree_G_presentation_EN.pptx')

INK = RGBColor(0x2B, 0x3A, 0x2F)
ACCENT = RGBColor(0x4A, 0x7C, 0x59)
MUTED = RGBColor(0x6A, 0x6A, 0x6A)
PAPER = RGBColor(0xFA, 0xF7, 0xF0)
PLACE = RGBColor(0xEF, 0xEA, 0xDC)

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
BLANK = prs.slide_layouts[6]
TOTAL = 10
_page = [0]


def slide():
    s = prs.slides.add_slide(BLANK)
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = PAPER
    _page[0] += 1
    return s


def title_bar(s, title, sub=None):
    box = s.shapes.add_textbox(Inches(0.55), Inches(0.32), Inches(12.25), Inches(0.85))
    p = box.text_frame.paragraphs[0]
    p.text = title; p.font.size = Pt(25); p.font.bold = True; p.font.color.rgb = INK
    bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.6), Inches(1.18), Inches(1.6), Pt(3))
    bar.fill.solid(); bar.fill.fore_color.rgb = ACCENT; bar.line.fill.background()
    if sub:
        sb = s.shapes.add_textbox(Inches(0.55), Inches(1.3), Inches(12.25), Inches(0.42))
        sp = sb.text_frame.paragraphs[0]
        sp.text = sub; sp.font.size = Pt(13); sp.font.italic = True; sp.font.color.rgb = MUTED


def footer(s):
    f = s.shapes.add_textbox(Inches(0.55), Inches(7.06), Inches(12.2), Inches(0.34))
    p = f.text_frame.paragraphs[0]
    p.text = f"LiuLiu Willow team - Synthetic 3D plant data  -  {_page[0]}/{TOTAL}"
    p.font.size = Pt(10); p.font.color.rgb = MUTED


def bullets(s, items, left, top, width, height, size=16):
    box = s.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    tf = box.text_frame; tf.word_wrap = True
    for i, (txt, lvl) in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = txt; p.level = lvl
        p.font.size = Pt(size if lvl == 0 else size - 2)
        p.font.color.rgb = INK if lvl == 0 else MUTED
        p.space_after = Pt(8)
    return box


def img(s, path, left, top, width=None, height=None, caption=None):
    w, h = Image.open(path).size
    ar = w / h
    if width and not height:
        height = width / ar
    elif height and not width:
        width = height * ar
    s.shapes.add_picture(path, Inches(left), Inches(top), Inches(width), Inches(height))
    if caption:
        cb = s.shapes.add_textbox(Inches(left), Inches(top + height + 0.04), Inches(width), Inches(0.34))
        cp = cb.text_frame.paragraphs[0]
        cp.text = caption; cp.font.size = Pt(10); cp.font.italic = True; cp.font.color.rgb = MUTED
        cp.alignment = PP_ALIGN.CENTER


def video(s, path, left, top, width, height):
    return s.shapes.add_movie(path, Inches(left), Inches(top), Inches(width), Inches(height), mime_type='video/mp4')


def chip(s, text, left, top, width, height, fill=ACCENT, fg=RGBColor(0xFF, 0xFF, 0xFF)):
    c = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(left), Inches(top), Inches(width), Inches(height))
    c.fill.solid(); c.fill.fore_color.rgb = fill; c.line.fill.background()
    tf = c.text_frame; tf.word_wrap = True; tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    p.text = text; p.font.size = Pt(13); p.font.bold = True; p.font.color.rgb = fg
    return c


def arrow(s, left, top):
    a = s.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Inches(left), Inches(top), Inches(0.4), Inches(0.35))
    a.fill.solid(); a.fill.fore_color.rgb = ACCENT; a.line.fill.background()
    return a


def placeholder(s, left, top, width, height, label):
    ph = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(left), Inches(top), Inches(width), Inches(height))
    ph.fill.solid(); ph.fill.fore_color.rgb = PLACE
    ph.line.color.rgb = ACCENT; ph.line.width = Pt(1.5)
    tf = ph.text_frame; tf.word_wrap = True; tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    p.text = label; p.font.size = Pt(13); p.font.italic = True; p.font.color.rgb = MUTED
    return ph


def source_note(s, text):
    sn = s.shapes.add_textbox(Inches(0.6), Inches(6.62), Inches(12.1), Inches(0.32))
    p = sn.text_frame.paragraphs[0]
    p.text = "Sources: " + text
    p.font.size = Pt(9); p.font.italic = True; p.font.color.rgb = MUTED
    return sn


# ===== 1. Title =====
s = slide()
img(s, os.path.join(FIGS, 'willow.jpg'), 8.0, 0.85, height=5.6)
tb = s.shapes.add_textbox(Inches(0.7), Inches(1.5), Inches(7.0), Inches(2.7))
tf = tb.text_frame; tf.word_wrap = True
p = tf.paragraphs[0]
p.text = "Synthetic 3D Plant Data: Augmenting Geometry & Topology"
p.font.size = Pt(33); p.font.bold = True; p.font.color.rgb = INK
p2 = tf.add_paragraph()
p2.text = "柳柳 (Liǔ Liǔ) — the Willow team · 柳 liǔ “willow” ≈ 留 liú “stay” · 我们会想你, “we’ll miss you”"
p2.font.size = Pt(14); p2.font.italic = True; p2.font.color.rgb = MUTED; p2.space_before = Pt(14)
ab = s.shapes.add_textbox(Inches(0.7), Inches(5.3), Inches(7.0), Inches(1.2))
ap = ab.text_frame.paragraphs[0]
ap.text = "Nelson Broyer-Paco · Angel Marquez-Aguilar · Li Shi · Josine · Pacifique"
ap.font.size = Pt(15); ap.font.color.rgb = INK
ap2 = ab.text_frame.add_paragraph()
ap2.text = "github.com/Nosl3n/Synthetic_Tree_G"
ap2.font.size = Pt(12); ap2.font.color.rgb = MUTED; ap2.space_before = Pt(4)
footer(s)

# ===== 2. Problem & goal =====
s = slide()
title_bar(s, "The problem & the goal")
bullets(s, [
    ("Models that work with 3D plant data need large amounts of labelled examples — point clouds, meshes, structure.", 0),
    ("Labelling is the bottleneck: scanning is hard, but manual annotation is the slowest and most expensive step.", 0),
    ("Goal: a method to AUGMENT 3D plant data — generate more, diverse, labelled examples of plant geometry & topology.", 0),
    ("The tropical forest below is just our test bed; the method applies to any tree.", 0),
], 0.6, 1.7, 12.1, 4.6, size=18)
footer(s)

# ===== 3. Starting point =====
s = slide()
title_bar(s, "Starting point: real scanned trees as QSMs")
bullets(s, [
    ("A Quantitative Structure Model (QSM) is a cylinder table: start point, axis, length, radius, and parent/child topology — the geometry and topology of a tree.", 0),
    ("Test bed: 201 tropical trees, 53 species, scanned with terrestrial laser scanning on Barro Colorado Island (Panama).", 0),
    ("Split by tree: 152 train / 49 test (stratified, fixed seed).", 0),
    ("Feasible to download and work with — but any tree fits the same representation.", 0),
], 0.7, 1.9, 12.0, 4.2, size=18)
source_note(s, "Data: Krishna Moorthy et al. 2022, Zenodo 6981485 (CC BY 4.0)")
footer(s)

# ===== 4. The method =====
s = slide()
title_bar(s, "The method: eight generators, three families")
chip(s, "Real QSMs\ncylinder models", 0.8, 1.75, 2.4, 0.95)
arrow(s, 3.3, 2.05)
chip(s, "8 generators\n3 families", 3.8, 1.75, 2.4, 0.95)
arrow(s, 6.3, 2.05)
chip(s, "Evaluate\nfidelity & novelty", 6.8, 1.75, 2.4, 0.95)
arrow(s, 9.3, 2.05)
chip(s, "Augmented\n3D plant data", 9.8, 1.75, 2.4, 0.95)
img(s, os.path.join(FIGS, 'generadores.png'), 0.7, 3.2, width=11.9,
    caption="A real tree (left) and one synthetic tree from each generator.")
bullets(s, [
    ("G2 (recombination) is the most faithful · G4 (procedural) the most novel · their mix G2+G4 is the best trade-off.", 0),
], 0.7, 5.6, 12.0, 0.5, size=15)
source_note(s, "QSM: TreeQSM (Raumonen et al. 2013) · space colonization: Runions et al. 2007")
footer(s)

# ===== 5. Proof =====
s = slide()
title_bar(s, "Proof: are they realistic?")
img(s, os.path.join(FIGS, 'fidelidad_novedad-1.png'), 0.7, 1.7, height=3.8,
    caption="1-NNA fidelity vs novelty per generator.")
img(s, os.path.join(FIGS, 'w1_rasgos-1.png'), 6.7, 1.7, height=3.8,
    caption="Wasserstein W1 per trait.")
bullets(s, [
    ("Over 22 tree + 10 branch traits: 1-NNA 56 % for G2 vs 46 % real–real; novelty 0.73 → 1.19 with G2+G4.", 0),
], 0.7, 6.1, 12.0, 0.6, size=15)
source_note(s, "Metrics: normalized Wasserstein W1, 1-NNA two-sample test, novelty, botanical validity")
footer(s)

# ===== 6. It transfers to any tree =====
s = slide()
title_bar(s, "It transfers to any tree — orchard and forest")
img(s, os.path.join(APPLE, 'apple_vs_tropical_deck.png'), 0.7, 1.7, height=3.5,
    caption="Real apple tree (Bibaum, left) vs tropical tree (right).")
img(s, os.path.join(OT, 'results/viewer_qsm_check/03_qsm_over_cloud.png'), 7.3, 1.7, height=3.5,
    caption="The apple-tree QSM over its own point cloud (digital-twin repo).")
bullets(s, [
    ("Orchard trees differ in scale and form — short trunk, spreading pruned crown — not in representation.", 0),
], 0.7, 5.9, 12.0, 0.8, size=15)
footer(s)

# ===== 7. Applications =====
s = slide()
title_bar(s, "Applications")
bullets(s, [
    ("Instance segmentation — individual trees and organs (trunk, branches, leaves).", 0),
    ("Phenotyping — biomass, DBH, volume, crown size.", 0),
    ("Robotics — orchard robots: pruning, navigation, harvesting.", 0),
    ("Agronomy — light interception and yield estimation.", 0),
    ("FSPM — feed the structure into growth models (GroIMP / L-Py).", 0),
    ("Two of these, demonstrated next.", 1),
], 0.7, 1.8, 11.9, 5.0, size=18)
footer(s)

# ===== 8. Demo 1: labelled sensor data =====
s = slide()
title_bar(s, "Demo 1: automatically-labelled sensor data",
          "24 synthetic trees · 128-channel Ouster OS1 LiDAR + RGB-D (D455) @ 10 Hz · per-class labels in real time")
video(s, os.path.join(ROOT, 'media/forest_route.mp4'), 0.7, 1.9, 7.3, 3.56)
vc = s.shapes.add_textbox(Inches(0.7), Inches(5.5), Inches(7.3), Inches(0.34))
vp = vc.text_frame.paragraphs[0]
vp.text = "Isaac Sim forest route (84 s) — LiDAR + RGB-D in real time."
vp.font.size = Pt(10); vp.font.italic = True; vp.font.color.rgb = MUTED
img(s, os.path.join(FIGS, 'sensores_v1_v2.png'), 8.3, 1.9, width=4.2,
    caption="RGB-D: RGB, depth, segmentation.")
img(s, os.path.join(FIGS, 'lidar_v1_v2-1.png'), 8.3, 3.9, width=4.2,
    caption="LiDAR: understory 21.7 % of points in v2.")
footer(s)

# ===== 9. Demo 2: robotic pruning =====
s = slide()
title_bar(s, "Demo 2: robotic pruning (orchard-robot repo)",
          "The same tree models drive a real pruning robot in the orchard.")
video(s, os.path.join(ROOT, 'media/pruning_agent.mp4'), 0.7, 1.9, 7.3, 4.11)
vc = s.shapes.add_textbox(Inches(0.7), Inches(6.05), Inches(7.3), Inches(0.34))
vp = vc.text_frame.paragraphs[0]
vp.text = "Robotic pruning plan (Nemotron 550B) on the apple tree."
vp.font.size = Pt(10); vp.font.italic = True; vp.font.color.rgb = MUTED
img(s, os.path.join(OT, 'results/segmentation/four_trees.png'), 8.3, 1.9, width=4.2,
    caption="Segmentation of four orchard trees.")
img(s, os.path.join(OT, 'results/pruning_ground_truth/bibaum_2020_added.png'), 8.3, 4.0, height=2.5,
    caption="Pruning: wood added/removed on the apple tree.")
footer(s)

# ===== 10. Takeaway & close =====
s = slide()
title_bar(s, "Takeaway")
img(s, os.path.join(FIGS, 'willow.jpg'), 8.3, 1.7, height=4.6)
bullets(s, [
    ("Synthetic 3D plant data = more, diverse, labelled examples of geometry & topology.", 0),
    ("One representation serves forest and orchard trees alike.", 0),
    ("Evaluated by fidelity and novelty — not just by eye.", 0),
    ("Downstream: segmentation, phenotyping, robotics, agronomy, FSPM.", 0),
], 0.7, 1.9, 7.2, 3.6, size=16)
cb = s.shapes.add_textbox(Inches(0.7), Inches(5.9), Inches(7.4), Inches(1.0))
cp = cb.text_frame.paragraphs[0]
cp.text = "柳柳，我们会想你 (Liǔ liǔ, wǒmen huì xiǎng nǐ) — “Liu Liu, we’ll miss you.”"
cp.font.size = Pt(16); cp.font.bold = True; cp.font.color.rgb = ACCENT
footer(s)

prs.save(OUT)
try:
    shutil.copy(OUT, '/mnt/c/Users/angel/Downloads/Synthetic_Tree_G_presentation_EN.pptx')
except PermissionError:
    print('note: Downloads copy skipped (file open in PowerPoint)')
print('wrote', OUT, os.path.getsize(OUT), 'bytes')
