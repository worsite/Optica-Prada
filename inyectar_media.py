"""
inyectar_media.py — Ópticas Prada
Inyecta imágenes de la carpeta media/ en index.html.

Reglas de nombres de archivo:
  Montura4.png                        → monturas,    "Montura 4"
  Montura19-97823.png                 → monturas,    "Ref. 97823"
  Sol3.png                            → sol,         "Sol 3"
  Sol5-RayBan.png                     → sol,         "Ref. RayBan"
  Lentes de contacto-Soflens 59.png   → lentes,      "Soflens 59"
  Lentes de contacto Purevision 2.png → lentes,      "Purevision 2"
  Soluciones - Multisolution Oxi.png  → soluciones,  "Multisolution Oxi"
  Gotas - Refresh Plus.png            → gotas,       "Refresh Plus"
  Lentes cosmetico - FreshLook.png    → cosmeticos,  "FreshLook"
  Lentes esfericos - Air Optix.png    → esfericos,   "Air Optix"
  Lentes multifocales - Bifocal.png   → multifocales,"Bifocal"
  Lentes toricos - Toric XR.png       → toricos,     "Toric XR"
  Montura4-foto2.png                  → segunda foto del modal de Montura 4

Uso:
  pip install Pillow
  python inyectar_media.py
"""

import base64
import io
import json
import os
import re
import sys

MEDIA_DIR   = "media"
INPUT_HTML  = "index.html"
OUTPUT_HTML = "index.html"   # sobreescribe; cámbialo a "index-nuevo.html" si prefieres
MAX_PX      = 900
QUALITY     = 82

START_MARKER = "/* PRODUCTS_START */"
END_MARKER   = "/* PRODUCTS_END */"

# ── intentar importar Pillow ──────────────────────────────────────────────────
try:
    from PIL import Image, ImageOps
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False
    print("⚠  Pillow no instalado — las imágenes se inyectarán sin comprimir.")
    print("   Instálalo con: pip install Pillow\n")

# ── helpers ───────────────────────────────────────────────────────────────────
def compress(path: str) -> bytes:
    """Redimensiona, corrige rotación EXIF y convierte a JPEG/PNG optimizado."""
    if not HAS_PILLOW:
        with open(path, "rb") as f:
            return f.read()

    img = Image.open(path)
    img = ImageOps.exif_transpose(img)          # corrige rotación EXIF

    # convertir a RGB si es necesario (ej. RGBA PNG)
    if img.mode in ("RGBA", "P"):
        bg = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode == "P":
            img = img.convert("RGBA")
        bg.paste(img, mask=img.split()[3] if img.mode == "RGBA" else None)
        img = bg
    elif img.mode != "RGB":
        img = img.convert("RGB")

    # redimensionar si supera MAX_PX en cualquier dimensión
    w, h = img.size
    if max(w, h) > MAX_PX:
        ratio = MAX_PX / max(w, h)
        img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=QUALITY, optimize=True)
    return buf.getvalue()


def to_b64(data: bytes, is_jpeg: bool = True) -> str:
    mime = "image/jpeg" if is_jpeg else "image/png"
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


# ── parseo de nombre de archivo → metadatos de producto ──────────────────────
def parse_filename(stem: str):
    """
    Devuelve (key, meta) donde:
      key  = identificador canónico del producto (usado para agrupar foto2)
      meta = dict con n, m, c  (None si es foto2)
    """
    # Foto secundaria — sufijo -foto2 (o -foto1 si quieres tratarlo igual)
    m = re.match(r"^(.+?)-(foto\d+)$", stem, re.IGNORECASE)
    if m:
        return m.group(1).strip().lower(), None   # key sin sufijo, sin meta

    # Nueva convención: "Categoría - Nombre producto" (con espacios alrededor del guion)
    # Ej: "Soluciones - Multisolution Oxi", "Gotas - Refresh Plus"
    CAT_MAP = {
        "lentes cosmetico":   ("cosmeticos",   "Lentes Cosméticos"),
        "lentes cosméticos":  ("cosmeticos",   "Lentes Cosméticos"),
        "gotas":              ("gotas",         "Gotas"),
        "lentes esfericos":   ("esfericos",     "Lentes Esféricos"),
        "lentes esféricos":   ("esfericos",     "Lentes Esféricos"),
        "lentes multifocales":("multifocales",  "Lentes Multifocales"),
        "lentes toricos":     ("toricos",       "Lentes Tóricos"),
        "lentes tóricos":     ("toricos",       "Lentes Tóricos"),
        "soluciones":         ("soluciones",    "Soluciones"),
    }
    m = re.match(r"^(.+?)\s+-\s+(.+)$", stem)
    if m:
        cat_raw = m.group(1).strip().lower()
        display  = m.group(2).strip()
        if cat_raw in CAT_MAP:
            cat_code, mat = CAT_MAP[cat_raw]
            key = f"{cat_code}-{display.lower()}"
            return key, {"n": display, "m": mat, "c": cat_code}

    # Lentes de contacto (con o sin guion: "Lentes de contacto-Soflens 59" o "Lentes de contacto Purevision 2")
    m = re.match(r"^Lentes de contacto[-\s]+(.+)$", stem, re.IGNORECASE)
    if m:
        display = m.group(1).strip()
        key = stem.lower()
        return key, {"n": display, "m": "Lentes de Contacto", "c": "lentes"}

    # Montura con referencia
    m = re.match(r"^Montura(\d+)-(.+)$", stem)
    if m:
        display = f"Ref. {m.group(2).strip()}"
        key = f"montura{m.group(1)}"
        return key, {"n": display, "m": "Montura", "c": "monturas"}

    # Montura simple
    m = re.match(r"^Montura(\d+)$", stem)
    if m:
        display = f"Montura {m.group(1)}"
        key = f"montura{m.group(1)}"
        return key, {"n": display, "m": "Montura", "c": "monturas"}

    # Sol con referencia
    m = re.match(r"^Sol(\d+)-(.+)$", stem)
    if m:
        display = f"Ref. {m.group(2).strip()}"
        key = f"sol{m.group(1)}"
        return key, {"n": display, "m": "Gafas de Sol", "c": "sol"}

    # Sol simple
    m = re.match(r"^Sol(\d+)$", stem)
    if m:
        display = f"Sol {m.group(1)}"
        key = f"sol{m.group(1)}"
        return key, {"n": display, "m": "Gafas de Sol", "c": "sol"}

    # Fallback
    key = stem.lower()
    return key, {"n": stem, "m": "Montura", "c": "monturas"}


# ── leer imágenes ─────────────────────────────────────────────────────────────
def load_products(media_dir: str):
    """Devuelve lista de dicts {n, m, c, img, img2} ordenados por categoría."""
    exts = {".png", ".jpg", ".jpeg", ".webp"}
    files = sorted(
        [f for f in os.listdir(media_dir) if os.path.splitext(f)[1].lower() in exts]
    )

    primary   = {}   # key → {meta, img_b64}
    secondary = {}   # key → img_b64

    for fname in files:
        stem = os.path.splitext(fname)[0]
        path = os.path.join(media_dir, fname)
        key, meta = parse_filename(stem)

        data    = compress(path)
        is_jpeg = HAS_PILLOW  # compress() siempre devuelve JPEG si Pillow disponible
        b64     = to_b64(data, is_jpeg=is_jpeg)

        if meta is None:
            # es foto2
            secondary[key] = b64
        else:
            primary[key] = {"meta": meta, "img": b64}

    # combinar
    products = []
    order = {"monturas": 0, "sol": 1, "lentes": 2}
    for key, val in primary.items():
        p = dict(val["meta"])
        p["img"]  = val["img"]
        p["img2"] = secondary.get(key, "")
        products.append(p)

    products.sort(key=lambda x: (order.get(x["c"], 9), x["n"]))
    return products


# ── construir bloque JS ───────────────────────────────────────────────────────
def build_js_block(products):
    items = []
    for p in products:
        n   = p["n"].replace("'", "\\'")
        m   = p["m"].replace("'", "\\'")
        img2 = p.get("img2", "")
        items.append(f"{{n:'{n}',m:'{m}',c:'{p['c']}',img:'{p['img']}',img2:'{img2}'}}")
    joined = ",".join(items)
    return f"{START_MARKER}\nconst prods=[{joined}]\n{END_MARKER}"


# ── inyectar en HTML ──────────────────────────────────────────────────────────
def inject(input_path, output_path, js_block):
    with open(input_path, "r", encoding="utf-8") as f:
        html = f.read()

    pattern = re.compile(
        re.escape(START_MARKER) + r"[\s\S]*?" + re.escape(END_MARKER)
    )
    if not pattern.search(html):
        print("✗  No se encontraron los marcadores PRODUCTS_START / PRODUCTS_END en el HTML.")
        sys.exit(1)

    html = pattern.sub(js_block, html)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)


# ── main ──────────────────────────────────────────────────────────────────────
def main():
    if not os.path.isdir(MEDIA_DIR):
        print(f"✗  Carpeta '{MEDIA_DIR}' no encontrada.")
        sys.exit(1)
    if not os.path.isfile(INPUT_HTML):
        print(f"✗  Archivo '{INPUT_HTML}' no encontrado.")
        sys.exit(1)

    print(f"Leyendo imágenes de '{MEDIA_DIR}'…")
    products = load_products(MEDIA_DIR)

    cats = {}
    for p in products:
        cats[p["c"]] = cats.get(p["c"], 0) + 1

    labels = {
        "monturas":"Monturas","sol":"Gafas de Sol","lentes":"Lentes de Contacto",
        "cosmeticos":"Lentes Cosméticos","esfericos":"Lentes Esféricos",
        "multifocales":"Lentes Multifocales","toricos":"Lentes Tóricos",
        "gotas":"Gotas","soluciones":"Soluciones",
    }
    for code, label in labels.items():
        if cats.get(code, 0):
            print(f"  {label+':':<26}{cats[code]}")
    print(f"  {'Total:':<26}{len(products)}")

    js_block = build_js_block(products)
    inject(INPUT_HTML, OUTPUT_HTML, js_block)

    print(f"\n✓  Listo — {len(products)} productos inyectados en '{OUTPUT_HTML}'")


if __name__ == "__main__":
    main()
