#!/usr/bin/env python3
import json, argparse, math
from pathlib import Path
from PIL import Image, ImageDraw

def rect(l,t,w,h):
    return (float(l), float(t), float(w), float(h))

def rect_to_ltrb(r):
    l,t,w,h = r
    return (l, t, l+w, t+h)

def intersect(a,b):
    al,at,ar,ab = (*rect_to_ltrb(a),)
    bl,bt,br,bb = (*rect_to_ltrb(b),)
    l = max(al, bl)
    t = max(at, bt)
    r = min(ar, br)
    btm = min(ab, bb)
    if r <= l or btm <= t:
        return (0,0,0,0), 0.0
    return (l, t, r-l, btm-t), (r-l)*(btm-t)

def contains(outer, inner, tol=0.0):
    ol,ot,ow,oh = outer
    il,it,iw,ih = inner
    return (il >= ol - tol and it >= ot - tol and
            il+iw <= ol+ow + tol and it+ih <= ot+oh + tol)

def clamp_rect_to_img(r, W, H):
    l,t,w,h = r
    l = max(0, int(math.floor(l)))
    t = max(0, int(math.floor(t)))
    r = int(min(W, math.ceil(l + w)))
    b = int(min(H, math.ceil(t + h)))
    return (l, t, r, b)

def compute_chunks(canvas, grid, chunks):
    W, H = canvas["width"], canvas["height"]
    m = grid["margin"]
    g = grid["gutter"]
    rows, cols = grid["rows"], grid["cols"]
    cell_w = (W - m["left"] - m["right"] - (cols-1) * g["col"]) / cols
    cell_h = (H - m["top"] - m["bottom"] - (rows-1) * g["row"]) / rows
    out = {}
    for ch in chunks:
        ga = ch["grid_area"]
        row = ga["row"]
        col = ga["col"]
        colspan = ga.get("colspan", 1)
        left = m["left"] + col * (cell_w + g["col"])
        top = m["top"] + row * (cell_h + g["row"])
        width = cell_w * colspan + g["col"] * (colspan - 1)
        height = cell_h
        out[ch["chunk_id"]] = rect(left, top, width, height)
    return out, (cell_w, cell_h)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", required=True)
    ap.add_argument("--image", required=True)
    ap.add_argument("--outdir", default="iconagent/dfa-paperX/tests/validation_out")
    ap.add_argument("--tol", type=float, default=2.0)
    args = ap.parse_args()

    D = json.loads(Path(args.json).read_text())
    W, H = D["canvas"]["width"], D["canvas"]["height"]
    chunks, cell = compute_chunks(D["canvas"], D["grid"], D["chunks"])
    print(f"Canvas {W}x{H}, cell={tuple(round(x,2) for x in cell)}")

    outdir = Path(args.outdir)
    (outdir/"groups").mkdir(parents=True, exist_ok=True)

    base_img = Image.open(args.image).convert("RGB")
    overlay = base_img.copy()
    draw = ImageDraw.Draw(overlay)

    colors = {"chunk": (43,108,176), "group_ok": (56,161,105), "group_bad": (229,62,62)}

    # draw chunk boxes
    for cid, rc in chunks.items():
        draw.rectangle(rect_to_ltrb(rc), outline=colors["chunk"], width=3)
        draw.text((rc[0]+4, rc[1]+4), cid, fill=colors["chunk"])

    ok_all = True
    for g in D["positions"]["groups"]:
        gid = g["group_id"]
        b = g["bbox"]
        bbox = rect(b["left"], b["top"], b["width"], b["height"])
        cid = g["chunk_id"]
        rc_chunk = chunks[cid]
        in_canvas = contains(rect(0,0,W,H), bbox, tol=args.tol)
        in_chunk = contains(rc_chunk, bbox, tol=args.tol)
        _, iarea = intersect(rc_chunk, bbox)
        iou = iarea / max(1.0, bbox[2]*bbox[3])
        color = colors["group_ok"] if (in_canvas and in_chunk) else colors["group_bad"]
        draw.rectangle(rect_to_ltrb(bbox), outline=color, width=3)
        draw.text((bbox[0]+4, bbox[1]+4), f"{gid} in {cid}", fill=color)
        print(f"- {gid} in {cid}: inside_chunk={in_chunk}, in_canvas={in_canvas}, IoU_with_chunk={iou:.3f}")
        if not (in_canvas and in_chunk):
            ok_all = False
        # save crop
        l,t,r,b = clamp_rect_to_img(bbox, W, H)
        base_img.crop((l,t,r,b)).save(outdir/"groups"/f"{gid}.png")

    print("All groups valid:", ok_all)
    overlay.save(outdir/"annotated.png")
    print(f"Saved overlay to {outdir/'annotated.png'} and crops to {outdir/'groups'}")

if __name__ == "__main__":
    main()

