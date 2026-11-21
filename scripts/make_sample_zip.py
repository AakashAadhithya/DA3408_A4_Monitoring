#!/usr/bin/env python3
# python scripts/make_sample_zip.py -n 40 -o sample_images.zip
# Real photos from picsum.photos (synthetic fallback when offline) plus a few bad
# entries so the skip/error metrics also show up on the dashboard.
import argparse
import io
import random
import urllib.request
import zipfile

from PIL import Image, ImageDraw

p = argparse.ArgumentParser()
p.add_argument("-n", type=int, default=40)
p.add_argument("-o", default="sample_images.zip")
args = p.parse_args()


def photo(i):
    try:
        with urllib.request.urlopen(f"https://picsum.photos/seed/a4-{i}/640/480", timeout=10) as r:
            return r.read()
    except Exception:
        img = Image.new("RGB", (640, 480), tuple(random.choices(range(256), k=3)))
        d = ImageDraw.Draw(img)
        for _ in range(6):
            x, y = random.randint(0, 560), random.randint(0, 400)
            d.ellipse([x, y, x + 80, y + 80], fill=tuple(random.choices(range(256), k=3)))
        buf = io.BytesIO()
        img.save(buf, "JPEG")
        return buf.getvalue()


with zipfile.ZipFile(args.o, "w") as z:
    for i in range(args.n):
        z.writestr(f"images/img_{i:03d}.jpg", photo(i))
    z.writestr("images/notes.txt", "not an image")
    z.writestr("images/corrupt.jpg", b"definitely not a jpeg")
print(f"wrote {args.o}")
