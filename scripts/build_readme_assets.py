#!/usr/bin/env python3
"""Genera los SVG del README de perfil de GitHub de Gabriel Mayorga.

Una sola fuente de verdad: colores en THEMES, textos en CONTENT.
Cada pieza sale en dos versiones (dark/light) para el <picture> del README.

Uso:
  python3 scripts/build_readme_assets.py                     # fuentes del sistema
  uv run --with fonttools scripts/build_readme_assets.py --fonts ~/fonts
      # incrusta Poppins y JetBrains Mono (subconjunto) para que todos
      # vean la misma tipografía, tengan o no las fuentes instaladas.
"""
from __future__ import annotations

import argparse
import base64
import copy
import io
from pathlib import Path
from xml.sax.saxutils import escape

OUT = Path(__file__).resolve().parent.parent / "assets"

# ── Tokens ───────────────────────────────────────────────────────────
THEMES = {
    "dark": {
        "bg": "#0F172A", "surface": "#0F172A", "tile": "#16213D",
        "text": "#F8FAFC", "muted": "#9AA6B8",
        "accent": "#3B82F6", "accent_text": "#60A5FA", "button": "#2563EB",
        "line": "#F8FAFC", "line_op": 0.10, "glass_op": 0.05,
        "blob_a": "#3B82F6", "blob_b": "#1D4ED8", "blob_op": 0.38,
        "live": "#34D399",
    },
    "light": {
        "bg": "#F4F7FC", "surface": "#FFFFFF", "tile": "#EAF1FF",
        "text": "#0F172A", "muted": "#526079",
        "accent": "#3B82F6", "accent_text": "#2563EB", "button": "#2563EB",
        "line": "#0F172A", "line_op": 0.09, "glass_op": 0.70,
        "blob_a": "#93C5FD", "blob_b": "#BFDBFE", "blob_op": 0.65,
        "live": "#16A34A",
    },
}

CONTENT = {
    "eyebrow": "IA · AUTOMATIZACIÓN · DESARROLLO",
    "name": "Gabriel Mayorga",
    "rotating": [
        ("Construyo ", "software full-stack"),
        ("Automatizo procesos ", "con IA"),
        ("Documento todo ", "en público"),
    ],
    "pills": [("live", "Abierto a oportunidades"), ("plain", "Ingeniero de sistemas · Nicaragua")],
    "projects": [
        {"slug": "dental", "mono": "DC", "title": "Dental Cloud System",
         "desc": ["SaaS de gestión para clínicas dentales.", "Frontend y API en repos separados."],
         "status": ("build", "Construyendo · demo"), "tags": ["Web", "API", "SaaS"], "linked": True},
        {"slug": "portafolio", "mono": "GM", "title": "Portafolio",
         "desc": ["Sitio personal con modo claro y oscuro,", "desplegado en Vercel."],
         "status": ("live", "En producción"), "tags": ["Next.js 16", "TypeScript", "Tailwind v4"], "linked": True},
        {"slug": "lotify", "mono": "LT", "title": "Lotify",
         "desc": ["SaaS white-label para venta de lotes", "residenciales en LATAM."],
         "status": ("build", "Construyendo"), "tags": ["SaaS", "Multi-marca"]},
        {"slug": "pdf", "mono": "PDF", "title": "Conversor de PDF",
         "desc": ["Herramientas de PDF en un solo lugar:", "conversión hoy, OCR en camino."],
         "status": ("build", "Construyendo"), "tags": ["Herramientas", "OCR"]},
    ],
    "principles": [
        ("01", "Por fases", ["Un commit por pieza terminada.", "Cada fase se revisa por sí sola."]),
        ("02", "En público", ["Comparto decisiones, errores", "y lo que aprendo en cada proyecto."]),
        ("03", "Con IA", ["Mi flujo corre con Claude Code:", "skills, hooks y subagentes."]),
    ],
    "buttons": [
        ("portafolio", "Portafolio", True),
        ("linkedin", "LinkedIn", False),
        ("correo", "Correo", False),
        ("youtube", "YouTube", False),
    ],
}

# ── Tipografía ───────────────────────────────────────────────────────
FONT_FILES = {  # clave → (familia CSS, peso, nombre de archivo sin extensión)
    "sans400": ("Poppins", 400, "Poppins-Regular"),
    "sans500": ("Poppins", 500, "Poppins-Medium"),
    "sans700": ("Poppins", 700, "Poppins-Bold"),
    "mono500": ("JetBrains Mono", 500, "JetBrainsMono-Medium"),
    "mono700": ("JetBrains Mono", 700, "JetBrainsMono-Bold"),
}
SANS = "Poppins, -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"
MONO = "'JetBrains Mono', ui-monospace, Consolas, 'Courier New', monospace"
_fonts: dict[str, object] = {}  # clave → TTFont, solo si se pasó --fonts


def load_fonts(folder: Path) -> None:
    from fontTools.ttLib import TTFont
    for key, (_, _, stem) in FONT_FILES.items():
        hits = [p for ext in ("ttf", "otf", "woff", "woff2") for p in folder.rglob(f"{stem}.{ext}")]
        if hits:
            _fonts[key] = TTFont(hits[0])
        else:
            print(f"  aviso: no encontré {stem}.* en {folder}; uso la fuente del sistema")


def measure(text: str, key: str, size: float, tracking: float = 0) -> float:
    """Ancho real del texto en px. Sin fuentes, una aproximación conservadora."""
    font = _fonts.get(key)
    if font is None:
        per = 0.62 if key.startswith("mono") else 0.58
        return len(text) * size * per + tracking * len(text)
    cmap, hmtx = font.getBestCmap(), font["hmtx"]
    upm = font["head"].unitsPerEm
    units = sum(hmtx[cmap.get(ord(c), cmap.get(32))][0] for c in text)
    return units / upm * size + tracking * len(text)


def font_faces(used_text: str) -> str:
    """@font-face con subconjuntos en base64 de solo los caracteres usados."""
    if not _fonts:
        return ""
    from fontTools import subset
    rules = []
    for key, font in _fonts.items():
        family, weight, _ = FONT_FILES[key]
        opts = subset.Options()
        opts.flavor, opts.layout_features, opts.name_IDs = "woff", ["kern", "liga"], []
        sub = subset.Subsetter(opts)
        sub.populate(text=used_text + " ")
        f = copy.deepcopy(font)
        sub.subset(f)
        buf = io.BytesIO()
        f.flavor = "woff"
        f.save(buf)
        data = base64.b64encode(buf.getvalue()).decode()
        rules.append(
            f"@font-face{{font-family:'{family}';font-weight:{weight};"
            f"src:url(data:font/woff;base64,{data}) format('woff');}}"
        )
    return "".join(rules)


# ── Piezas compartidas ───────────────────────────────────────────────
REDUCED = "@media (prefers-reduced-motion: reduce){*{animation:none!important}.in{opacity:1!important;transform:none!important}.w{opacity:0!important}.w1{opacity:1!important;transform:none!important}}"
EASE = "cubic-bezier(.22,1,.36,1)"  # salida suave tipo spring críticamente amortiguado


def svg(w: int, h: int, title: str, css: str, body: str, used: str, sized: bool = False) -> str:
    size = f' width="{w}" height="{h}"' if sized else ""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}"{size} role="img" aria-label="{escape(title)}">'
        f"<title>{escape(title)}</title><style>{font_faces(used)}{css}</style>{body}</svg>\n"
    )


def blur_defs(uid: str, w: int, h: int, r: int, dev: int = 50, extra: str = "") -> str:
    """Recorte al borde redondeado + desenfoque para los halos de color."""
    return (
        f'<defs><clipPath id="c{uid}"><rect width="{w}" height="{h}" rx="{r}"/></clipPath>'
        f'<filter id="b{uid}" x="-50%" y="-50%" width="200%" height="200%">'
        f'<feGaussianBlur stdDeviation="{dev}"/></filter>{extra}</defs>'
    )


def hairline(t: dict, w: int, h: int, r: int) -> str:
    """Borde fino + brillo superior: la luz que "toca" el material."""
    return (
        f'<rect x=".5" y=".5" width="{w-1}" height="{h-1}" rx="{r}" fill="none" '
        f'stroke="{t["line"]}" stroke-opacity="{t["line_op"]}"/>'
        + (f'<path d="M{r} 1.5H{w-r}" stroke="#FFFFFF" stroke-opacity=".16"/>' if t is THEMES["dark"] else "")
    )


def status_pill(t: dict, kind: str, label: str, x_right: float, y: float) -> tuple[str, float]:
    size, h, pad, dot = 14, 30, 14, 8
    w = pad + dot + 8 + measure(label, "sans500", size) + pad
    x = x_right - w
    color = t["live"] if kind == "live" else t["accent"]
    ring = f'<circle class="pulse" cx="{x+pad+dot/2}" cy="{y+h/2}" r="{dot/2}" fill="{color}"/>'
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{h/2}" fill="{color}" fill-opacity=".12"/>'
        f"{ring}"
        f'<circle cx="{x+pad+dot/2}" cy="{y+h/2}" r="{dot/2}" fill="{color}"/>'
        f'<text x="{x+pad+dot+8}" y="{y+h/2+5}" class="pill" fill="{t["text"]}">{escape(label)}</text>'
    ), w


PULSE_CSS = (
    ".pulse{transform-box:fill-box;transform-origin:center;animation:pulse 2.4s ease-out infinite}"
    "@keyframes pulse{0%{opacity:.6;transform:scale(1)}80%,100%{opacity:0;transform:scale(2.6)}}"
)


# ── Hero ─────────────────────────────────────────────────────────────
def hero(t: dict) -> str:
    W, H, R = 1280, 480, 28
    cx = W / 2
    c = CONTENT
    used = c["eyebrow"] + c["name"] + "".join(a + b for a, b in c["rotating"]) + "".join(p for _, p in c["pills"]) + "{GM}"
    css = (
        f".display{{font:700 78px {SANS};letter-spacing:-2.4px;fill:{t['text']}}}"
        f".eyebrow{{font:500 15px {MONO};letter-spacing:4px;fill:{t['accent_text']}}}"
        f".rot{{font:400 30px {SANS};letter-spacing:-.3px;fill:{t['muted']}}}"
        f".rot tspan{{fill:{t['text']};font-weight:500}}"
        f".pill{{font:500 15px {SANS}}}"
        f".mono{{font:700 40px {MONO}}}"
        f".in{{opacity:0;animation:rise .9s {EASE} both}}"
        "@keyframes rise{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:none}}"
        ".blob{transform-box:fill-box;transform-origin:center;animation:drift 28s ease-in-out infinite alternate}"
        "@keyframes drift{to{transform:translate(60px,-30px) scale(1.12)}}"
        ".blob2{animation-duration:34s;animation-direction:alternate-reverse}"
        ".w{opacity:0;animation:word 12s infinite both}"
        "@keyframes word{0%{opacity:0;transform:translateY(10px)}4%,29%{opacity:1;transform:none}33%,100%{opacity:0;transform:translateY(-10px)}}"
        f"{PULSE_CSS}{REDUCED}"
    )
    words = "".join(
        f'<text class="rot w w{i+1}" x="{cx}" y="356" text-anchor="middle" style="animation-delay:{0.7+i*4}s">'
        f"{escape(a)}<tspan>{escape(b)}</tspan></text>"
        for i, (a, b) in enumerate(c["rotating"])
    )
    # Pastillas inferiores centradas, con ancho medido
    pills, widths = [], []
    for kind, label in c["pills"]:
        dot = 22 if kind == "live" else 0
        widths.append(20 + dot + measure(label, "sans500", 15) + 20)
    x = cx - (sum(widths) + 14 * (len(widths) - 1)) / 2
    for (kind, label), w in zip(c["pills"], widths):
        y, h = 396, 40
        pills.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{h/2}" fill="{t["surface"]}" fill-opacity="{t["glass_op"]}" '
            f'stroke="{t["line"]}" stroke-opacity="{t["line_op"]+.04}"/>'
        )
        tx = x + 20
        if kind == "live":
            pills.append(f'<circle class="pulse" cx="{tx+4}" cy="{y+h/2}" r="4" fill="{t["live"]}"/>'
                         f'<circle cx="{tx+4}" cy="{y+h/2}" r="4" fill="{t["live"]}"/>')
            tx += 22
        pills.append(f'<text class="pill" x="{tx}" y="{y+h/2+5}" fill="{t["text"]}">{escape(label)}</text>')
        x += w + 14
    tile = 112
    body = (
        blur_defs("h", W, H, R, 70, extra=(
            '<linearGradient id="tg" x1="0" y1="0" x2="0" y2="1">'
            '<stop offset="0" stop-color="#FFFFFF" stop-opacity=".10"/>'
            '<stop offset="1" stop-color="#FFFFFF" stop-opacity="0"/></linearGradient>'))
        + f'<rect width="{W}" height="{H}" rx="{R}" fill="{t["bg"]}"/>'
        f'<g clip-path="url(#ch)"><g filter="url(#bh)" opacity="{t["blob_op"]}">'
        f'<circle class="blob" cx="250" cy="90" r="230" fill="{t["blob_a"]}"/>'
        f'<circle class="blob blob2" cx="1060" cy="420" r="270" fill="{t["blob_b"]}"/>'
        f'<circle class="blob" cx="1010" cy="40" r="120" fill="{t["accent"]}" opacity=".5"/>'
        f"</g></g>"
        + hairline(t, W, H, R)
        + f'<g class="in" style="animation-delay:.05s">'
        f'<rect x="{cx-tile/2}" y="52" width="{tile}" height="{tile}" rx="30" fill="{t["tile"]}" stroke="{t["accent"]}" stroke-opacity=".45" stroke-width="1.5"/>'
        f'<rect x="{cx-tile/2}" y="52" width="{tile}" height="{tile/2}" rx="30" fill="url(#tg)"/>'
        f'<text class="mono" x="{cx}" y="122" text-anchor="middle"><tspan fill="{t["accent"]}">{{</tspan><tspan fill="{t["text"]}">GM</tspan><tspan fill="{t["accent"]}">}}</tspan></text></g>'
        f'<text class="eyebrow in" x="{cx}" y="214" text-anchor="middle" style="animation-delay:.15s">{escape(c["eyebrow"])}</text>'
        f'<text class="display in" x="{cx}" y="298" text-anchor="middle" style="animation-delay:.25s">{escape(c["name"])}</text>'
        f"{words}"
        f'<g class="in" style="animation-delay:.45s">{"".join(pills)}</g>'
    )
    return svg(W, H, "Gabriel Mayorga — IA, automatización y desarrollo", css, body, used)


# ── Tarjetas de proyecto ─────────────────────────────────────────────
def card(t: dict, p: dict) -> str:
    W, H, R = 600, 300, 24
    used = p["mono"] + p["title"] + "".join(p["desc"]) + p["status"][1] + "".join(p["tags"])
    css = (
        f".title{{font:700 30px {SANS};letter-spacing:-.7px;fill:{t['text']}}}"
        f".desc{{font:400 17px {SANS};fill:{t['muted']}}}"
        f".pill{{font:500 14px {SANS}}}"
        f".tag{{font:500 13px {MONO};fill:{t['text']};fill-opacity:.85}}"
        f".mono{{font:700 {20 if len(p['mono']) < 3 else 16}px {MONO}}}"
        f"{PULSE_CSS}{REDUCED}"
    )
    pill, _ = status_pill(t, *p["status"], x_right=W - 28, y=32)
    for line in p["desc"]:
        if measure(line, "sans400", 17) > W - 64:
            print(f"  aviso: línea larga en {p['slug']}: {line!r}")
    desc = "".join(f'<text class="desc" x="32" y="{184 + i*26}">{escape(l)}</text>' for i, l in enumerate(p["desc"]))
    tags, x = [], 32
    for tag in p["tags"]:
        w = measure(tag, "mono500", 13) + 24
        tags.append(
            f'<rect x="{x}" y="240" width="{w}" height="30" rx="15" fill="{t["line"]}" fill-opacity=".06" stroke="{t["line"]}" stroke-opacity="{t["line_op"]}"/>'
            f'<text class="tag" x="{x+12}" y="260">{escape(tag)}</text>'
        )
        x += w + 8
    # La flecha promete un enlace: solo aparece si la tarjeta lo tiene en el README
    ax, ay = W - 50, 255
    arrow = "" if not p.get("linked") else (
        f'<circle cx="{ax}" cy="{ay}" r="18" fill="{t["line"]}" fill-opacity=".06" stroke="{t["line"]}" stroke-opacity="{t["line_op"]}"/>'
        f'<path d="M{ax-5} {ay+5}L{ax+5} {ay-5}M{ax-3} {ay-5}H{ax+5}V{ay+3}" fill="none" stroke="{t["text"]}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>'
    )
    body = (
        blur_defs(p["slug"], W, H, R)
        + f'<rect width="{W}" height="{H}" rx="{R}" fill="{t["surface"]}"/>'
        f'<g clip-path="url(#c{p["slug"]})"><circle cx="{W-40}" cy="-10" r="150" fill="{t["blob_a"]}" '
        f'opacity="{t["blob_op"]*0.45}" filter="url(#b{p["slug"]})"/></g>'
        + hairline(t, W, H, R)
        + f'<rect x="32" y="32" width="56" height="56" rx="16" fill="{t["tile"]}" stroke="{t["accent"]}" stroke-opacity=".35"/>'
        f'<text class="mono" x="60" y="{67 if len(p["mono"]) < 3 else 66}" text-anchor="middle" fill="{t["text"]}">{escape(p["mono"])}</text>'
        f"{pill}"
        f'<text class="title" x="32" y="146">{escape(p["title"])}</text>'
        f"{desc}{''.join(tags)}{arrow}"
    )
    return svg(W, H, f'{p["title"]}: {" ".join(p["desc"])}', css, body, used)


# ── Cómo trabajo ─────────────────────────────────────────────────────
def principles(t: dict) -> str:
    W, H, R = 1280, 250, 24
    items = CONTENT["principles"]
    used = "".join(n + ti + "".join(ls) for n, ti, ls in items)
    css = (
        f".n{{font:500 14px {MONO};letter-spacing:2px;fill:{t['accent_text']}}}"
        f".h{{font:700 26px {SANS};letter-spacing:-.5px;fill:{t['text']}}}"
        f".p{{font:400 17px {SANS};fill:{t['muted']}}}"
    )
    col = W / len(items)
    parts = []
    for i, (n, title, lines) in enumerate(items):
        x = i * col + 48
        if i:
            parts.append(f'<path d="M{i*col} 44V{H-44}" stroke="{t["line"]}" stroke-opacity="{t["line_op"]}"/>')
        parts.append(f'<text class="n" x="{x}" y="76">{n}</text><text class="h" x="{x}" y="120">{escape(title)}</text>')
        for j, line in enumerate(lines):
            if measure(line, "sans400", 17) > col - 80:
                print(f"  aviso: línea larga en principios: {line!r}")
            parts.append(f'<text class="p" x="{x}" y="{162 + j*26}">{escape(line)}</text>')
    body = (
        blur_defs("p", W, H, R)
        + f'<rect width="{W}" height="{H}" rx="{R}" fill="{t["surface"]}"/>'
        f'<g clip-path="url(#cp)"><circle cx="{W/2}" cy="{H+60}" r="220" fill="{t["blob_a"]}" opacity="{t["blob_op"]*0.35}" filter="url(#bp)"/></g>'
        + hairline(t, W, H, R) + "".join(parts)
    )
    return svg(W, H, "Cómo trabajo: " + "; ".join(f"{ti}. {' '.join(ls)}" for _, ti, ls in items), css, body, used)


# ── Botones de enlace ────────────────────────────────────────────────
def button(t: dict, label: str, primary: bool) -> str:
    size, pad, h = 16, 24, 48
    w = round(pad + measure(label, "sans500", size) + 10 + 12 + pad)
    fill = t["button"] if primary else t["surface"]
    color = "#FFFFFF" if primary else t["text"]
    stroke = "" if primary else f' stroke="{t["line"]}" stroke-opacity="{t["line_op"]+.05}"'
    css = f".l{{font:500 {size}px {SANS};fill:{color}}}"
    ax, ay = w - pad - 6, h / 2
    body = (
        f'<rect x=".5" y=".5" width="{w-1}" height="{h-1}" rx="{(h-1)/2}" fill="{fill}"{stroke}/>'
        f'<text class="l" x="{pad}" y="{h/2+6}">{escape(label)}</text>'
        f'<path d="M{ax-4} {ay+4}L{ax+4} {ay-4}M{ax-2} {ay-4}H{ax+4}V{ay+2}" fill="none" stroke="{color}" '
        f'stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/>'
    )
    return svg(w, h, label, css, body, label, sized=True)


# ── Build ────────────────────────────────────────────────────────────
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fonts", type=Path, help="carpeta con Poppins-*.ttf y JetBrainsMono-*.ttf")
    args = ap.parse_args()
    if args.fonts:
        load_fonts(args.fonts.expanduser())
    OUT.mkdir(exist_ok=True)
    files = {}
    for mode, t in THEMES.items():
        files[f"hero-{mode}.svg"] = hero(t)
        files[f"principios-{mode}.svg"] = principles(t)
        for p in CONTENT["projects"]:
            files[f"proyecto-{p['slug']}-{mode}.svg"] = card(t, p)
        for slug, label, primary in CONTENT["buttons"]:
            files[f"btn-{slug}-{mode}.svg"] = button(t, label, primary)
    for name, data in files.items():
        (OUT / name).write_text(data, encoding="utf-8")
    kb = sum(len(d.encode()) for d in files.values()) / 1024
    print(f"listo: {len(files)} archivos en {OUT} ({kb:.0f} KB)")


if __name__ == "__main__":
    main()
