#!/usr/bin/env python3
"""Generate PostPilot's original 1024x1024 app icon (icon.png).

No TikTok logo, no social-media company logo, no third-party
artwork: a plain dark-blue rounded square, a white paper-plane
mark, and the word "PostPilot". Run: python3 make_icon.py
"""
from PIL import Image, ImageDraw, ImageFont

SIZE = 1024
BG = (11, 42, 74, 255)          # deep blue
ACCENT = (45, 183, 160, 255)    # teal
WHITE = (255, 255, 255, 255)

img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)
draw.rounded_rectangle([8, 8, SIZE - 8, SIZE - 8], radius=220, fill=BG)
# Paper-plane mark (simple original polygon + fold line).
draw.polygon([(300, 620), (724, 300), (560, 700), (470, 540)], fill=WHITE)
draw.polygon([(470, 540), (560, 700), (430, 660)], fill=ACCENT)
draw.line([(300, 620), (470, 540)], fill=ACCENT, width=14)

try:
    font = ImageFont.truetype(
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 104)
except OSError:
    font = ImageFont.load_default()
text = "PostPilot"
bbox = draw.textbbox((0, 0), text, font=font)
w = bbox[2] - bbox[0]
draw.text(((SIZE - w) // 2, 770), text, font=font, fill=WHITE)

img.convert("RGB").save("icon.png", "PNG")
print("Wrote icon.png")
