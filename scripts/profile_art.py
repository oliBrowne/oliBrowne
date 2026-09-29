"""Generate the portrait and info panel as self-contained animated SVGs.

Edit profile.json or replace its portrait_source, then run this file.
The daily contribution workflow does not need Pillow or this script.
"""
from html import escape
import json
from pathlib import Path
import textwrap

from PIL import Image, ImageOps, ImageEnhance

ROOT = Path(__file__).resolve().parents[1]
BG = "#0d1117"
BORDER = "#30363d"
MUTED = "#8b949e"
TEXT = "#e6edf3"
GREEN = "#7ee787"
FONT = "ui-monospace, SFMono-Regular, Consolas, Liberation Mono, monospace"


def frame(width, height, title, description):
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        f'<title id="title">{escape(title)}</title><desc id="desc">{escape(description)}</desc>',
        f'<rect x=".5" y=".5" width="{width-1}" height="{height-1}" rx="12" fill="{BG}" stroke="{BORDER}"/>',
        f'<path d="M1 40H{width-1}" stroke="{BORDER}"/>',
        '<circle cx="19" cy="21" r="4" fill="#ff7b72"/><circle cx="33" cy="21" r="4" fill="#e3b341"/><circle cx="47" cy="21" r="4" fill="#3fb950"/>',
        f'<g font-family="{FONT}">',
        f'<text x="{width-18}" y="25" text-anchor="end" font-size="10" fill="{MUTED}">{escape(title)}</text>',
    ]


def portrait(config):
    # Bright areas use dense, light-colored glyphs on the dark terminal.
    # Transparency leaves the area around the subject completely empty.
    source = ImageOps.fit(Image.open(ROOT / config["portrait_source"]).convert("RGBA"), (300, 282))
    alpha = source.getchannel("A")
    source = source.convert("L")
    source = ImageOps.autocontrast(source, cutoff=1)
    source = ImageEnhance.Contrast(source).enhance(1.12)
    cols, rows = 78, 43
    sample = source.resize((cols, rows), Image.Resampling.LANCZOS)
    coverage = alpha.resize((cols, rows), Image.Resampling.LANCZOS)
    ramp = " .,:;irsXA253hMHGS#9B&@"
    parts = frame(370, 360, "portrait.txt", "An animated ASCII portrait of " + config["name"] + ".")
    parts += [
        '<style>@keyframes type{from{clip-path:inset(0 100% 0 0)}to{clip-path:inset(0 0 0 0)}}',
        '.row{white-space:pre;animation:type .24s steps(18,end) both}',
        '@media(prefers-reduced-motion:reduce){.row{animation:none!important}}</style>',
        f'<g fill="{TEXT}" font-size="6.4" xml:space="preserve">',
    ]
    for y in range(rows):
        line = "".join(ramp[round((sample.getpixel((x, y)) / 255) ** .8 * coverage.getpixel((x, y)) / 255 * (len(ramp)-1))] for x in range(cols))
        line = line.replace(" ", "\u00a0")
        parts.append(f'<text class="row" x="35" y="{62 + y*6.35:.2f}" textLength="300" lengthAdjust="spacingAndGlyphs" style="animation-delay:{y*.032:.3f}s">{escape(line)}</text>')
    parts += ["</g>", f'<text x="19" y="342" font-size="10" fill="{MUTED}"><tspan fill="{GREEN}">●</tspan> {escape(config["username"])} / portrait loaded</text>', "</g></svg>"]
    return "\n".join(parts) + "\n"


def info_card(config):
    parts = frame(490, 360, "neofetch", "Profile details for " + config["name"])
    parts += [
        '<style>@keyframes reveal{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:translateY(0)}}',
        '.entry{animation:reveal .36s ease-out both}',
        '@media(prefers-reduced-motion:reduce){.entry{animation:none!important}}</style>',
        f'<text x="25" y="76" font-size="23" font-weight="700" fill="{TEXT}">{escape(config["name"])}</text>',
        f'<text x="25" y="99" font-size="12" fill="{GREEN}">{escape(config["username"])}@github</text>',
        f'<path d="M25 113H465" stroke="{BORDER}" stroke-dasharray="3 4"/>',
    ]
    fields = [("now", config["title"]), ("school", config["school"]),
              ("base", config["location"]), ("stack", config["stack"]),
              ("ask me", config["interests"]), ("offline", config["offline"]),
              ("built", config["project"])]
    y = 139
    for index, (key, value) in enumerate(fields):
        # Wrap config text instead of silently clipping long edits.
        lines = textwrap.wrap(value, width=39) or [""]
        if len(lines) > 1:
            raise ValueError(f"Profile field {key!r} must fit 39 characters; shorten it for this layout.")
        parts.append(f'<g class="entry" style="animation-delay:{.2 + index*.13:.2f}s" font-size="12.5"><text x="25" y="{y}" fill="#79c0ff">{escape(key)}</text><text x="111" y="{y}" fill="{TEXT}">{escape(value)}</text></g>')
        y += 26
    parts.append(f'<path d="M25 318H465" stroke="{BORDER}"/>')
    for index, color in enumerate(["#0e4429", "#006d32", "#26a641", "#39d353", "#7ee787", "#a5d6ff"]):
        parts.append(f'<rect x="{25+index*15}" y="331" width="12" height="10" rx="2" fill="{color}"/>')
    parts.append(f'<text x="465" y="340" text-anchor="end" font-size="10" fill="{MUTED}">build · learn · repeat</text>')
    parts.append("</g></svg>")
    return "\n".join(parts) + "\n"


def main():
    config = json.loads((ROOT / "profile.json").read_text(encoding="utf-8"))
    assets = ROOT / "assets"
    assets.mkdir(exist_ok=True)
    portrait_svg, info_svg = portrait(config), info_card(config)
    (assets / "portrait.svg").write_text(portrait_svg, encoding="utf-8")
    (assets / "info-card.svg").write_text(info_svg, encoding="utf-8")
    print("Generated assets/portrait.svg and assets/info-card.svg")


if __name__ == "__main__":
    main()
