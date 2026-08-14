#!/usr/bin/env python3
"""LNG Orifice Meter uygulama ikonunu üretir.

Tasarim: boru ucundan gorunum - orifis plakasi + flans + boru deligi (bore),
merkezden akan gaz ok isareti ve ust kisimda DeltaP rozeti. LNG'nin kriyojenik
mavi-tonu arka plan olarak kullanilir.

Ciktilar (assets/):
  icon.png   1024x1024 master PNG (Linux dahil tum platformlar)
  icon.ico   cok boyutlu Windows ikonu
  icon.icns  macOS ikonu (Pillow ICNS)

Gereksinim: pip install Pillow
"""

import os

from PIL import Image, ImageDraw

S = 4096  # 4x supersampling -> 1024'e dusurulur
FINAL = 1024
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)))

C = S // 2  # merkez

# Palet
NAVY = (8, 26, 52)
CYAN = (14, 128, 168)
STEEL_HI = (184, 194, 208)
STEEL_MID = (126, 138, 154)
STEEL_DK = (80, 90, 106)
PLATE = (48, 58, 74)
BORE = (7, 16, 30)
GLOW = (34, 211, 238)
GLOW_SOFT = (148, 233, 247)
WHITE = (255, 255, 255)


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def rounded_bg(draw):
    """Dikey gradyanli, kose yaricapli zemin."""
    r = int(S * 0.185)
    steps = 48
    for i in range(steps):
        t = i / (steps - 1)
        col = lerp(NAVY, CYAN, t)
        y0 = int(S * (i / steps))
        y1 = int(S * ((i + 1) / steps)) + 1
        draw.rounded_rectangle(
            [0, y0, S, y1], radius=r, fill=col
        )
    # merkeze dogru yumusak isik
    glow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([int(S * 0.18), int(S * 0.05), int(S * 0.82), int(S * 0.85)],
               fill=(120, 210, 240, 70))
    draw._image.alpha_composite(glow)


def disc(draw, cx, cy, r, fill, outline=None, width=0):
    b = [cx - r, cy - r, cx + r, cy + r]
    draw.ellipse(b, fill=fill, outline=outline, width=width)


def steel_ring(draw, cx, cy, r_outer, r_inner, color):
    """Metalik flans halkasi: hafif radyal gibi gorunen dairesel cizim."""
    n = 24
    for i in range(n):
        t = i / (n - 1)
        r = r_inner + (r_outer - r_inner) * t
        col = lerp(color[0], color[1], t)
        w = int((r_outer - r_inner) / n) + 2
        disc(draw, cx, cy, r, None, outline=col, width=w)


def bolt_circle(draw, cx, cy, angle, R, r, color):
    import math

    x = cx + R * math.cos(angle)
    y = cy + R * math.sin(angle)
    disc(draw, x, y, r, color)
    disc(draw, x, y, r * 0.55, lerp(color, WHITE, 0.35))


def chevron(draw, cx, cy, size, color, n, gap):
    """Saga isaret eden gaz akis oklari (chevron)."""
    import math

    hw = size * 0.9
    for i in range(n):
        x = cx + (i - (n - 1) / 2) * (size + gap)
        pts = [
            (x - hw, cy - size),
            (x, cy),
            (x - hw, cy + size),
            (x + hw * 0.45, cy + size),
            (x + hw * 0.45 + size * 0.55, cy),
            (x + hw * 0.45, cy - size),
        ]
        draw.polygon(pts, fill=color)


def delta_badge(draw, cx, cy, s):
    """Ustte kucuk 'DeltaP' rozeti: ucgen + P."""
    tri = [
        (cx, cy - s * 1.1),
        (cx - s, cy + s * 0.5),
        (cx + s, cy + s * 0.5),
    ]
    draw.polygon(tri, fill=WHITE)
    # P harfi (iki dikdortgen + yari daire)
    pw = s * 0.34
    ph = s * 0.95
    x0, y0 = cx - pw, cy + s * 0.05
    draw.rounded_rectangle([x0, y0, x0 + pw, y0 + ph], radius=pw / 2, fill=NAVY)
    pr = pw * 0.62
    disc(draw, x0 + pw, y0 + pr * 0.62, pr, NAVY)
    draw.rectangle([x0 + pw - pr * 0.1, y0, x0 + pw + pr * 1.25, y0 + pr * 1.35],
                   fill=NAVY)


def main():
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    rounded_bg(draw)

    # Flans halkasi (dis -> ic)
    steel_ring(draw, C, C, int(S * 0.45), int(S * 0.375), (STEEL_MID, STEEL_HI))
    # flansin dis kenarina koyu taslak
    disc(draw, C, C, int(S * 0.45), None, outline=STEEL_DK, width=int(S * 0.012))
    disc(draw, C, C, int(S * 0.375), None, outline=STEEL_DK, width=int(S * 0.008))

    # Civalar (8 adet)
    import math

    for i in range(8):
        a = math.pi / 2 + i * math.tau / 8
        bolt_circle(draw, C, C, a, int(S * 0.412), int(S * 0.02), STEEL_DK)

    # Orifis plakasi
    disc(draw, C, C, int(S * 0.36), PLATE)
    # plaka ust isigi
    disc(draw, C, C, int(S * 0.36), None, outline=lerp(PLATE, WHITE, 0.22),
         width=int(S * 0.006))
    # plaka ic kademe
    disc(draw, C, C, int(S * 0.26), lerp(PLATE, BORE, 0.45))

    # Boru deligi (bore) + parlaklik halkasi
    r_glow = int(S * 0.155)
    glow_img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow_img)
    gd.ellipse([C - r_glow, C - r_glow, C + r_glow, C + r_glow],
               outline=(GLOW[0], GLOW[1], GLOW[2], 90), width=int(S * 0.03))
    img.alpha_composite(glow_img)
    disc(draw, C, C, int(S * 0.13), BORE)
    # delik ic derinligi
    disc(draw, C, C, int(S * 0.065), lerp(BORE, GLOW_SOFT, 0.18))

    # Gaz akis oklari (delikten saga)
    chevron(draw, C, C, int(S * 0.055), GLOW_SOFT, 3, int(S * 0.03))

    # Ust DeltaP rozeti
    delta_badge(draw, C, int(S * 0.30), int(S * 0.075))

    # Dis vurgu (glass efekti)
    glass = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glass)
    gd.pieslice([int(S * 0.03), int(S * 0.03), int(S * 0.97), int(S * 0.97)],
                210, 330, fill=(255, 255, 255, 42))
    img.alpha_composite(glass)

    img = img.resize((FINAL, FINAL), Image.LANCZOS)

    img.save(os.path.join(OUT, "icon.png"))
    img.save(
        os.path.join(OUT, "icon.ico"),
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64),
               (128, 128), (256, 256)],
    )
    img.save(os.path.join(OUT, "icon.icns"), format="ICNS")

    print("ikonlar uretildi: icon.png / icon.ico / icon.icns")


if __name__ == "__main__":
    main()
