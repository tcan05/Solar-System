"""Build a self-contained index.html globe from Natural Earth + World Bank data.

Usage: python tools/build_globe.py
Inputs : data/ne_10m_countries.geojson, data/worldbank_pop_2023.json,
         data/capitals.json (optional), src/globe_template.html
Output : index.html (single file, works offline)
"""

import base64
import json
import math
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
SRC = os.path.join(ROOT, "src")
OUT = os.path.join(ROOT, "index.html")

SIMPLIFY_TOL = 0.06      # degrees, max Douglas-Peucker tolerance
MIN_RING_AREA = 2e-6     # square degrees, drops specks/dust rings
COORD_DECIMALS = 4       # ~11 m
SOURCE = os.environ.get("NE_SOURCE", "ne_10m_countries.geojson")

# Non-country Natural Earth features (bases, buffer zones, reefs, ice fields).
SKIP_ISO = {"CNM", "WSB", "ESB", "KAS", "USG", "IOA", "CSI", "PGA"}

NAME_FIXES = {
    "United States of America": "United States",
    "Dem. Rep. Congo": "DR Congo",
    "Central African Rep.": "Central African Republic",
    "S. Sudan": "South Sudan",
    "Bosnia and Herz.": "Bosnia and Herzegovina",
    "Dominican Rep.": "Dominican Republic",
    "Eq. Guinea": "Equatorial Guinea",
    "Solomon Is.": "Solomon Islands",
    "Falkland Is.": "Falkland Islands",
    "Fr. S. Antarctic Lands": "French Southern Territories",
    "W. Sahara": "Western Sahara",
    "eSwatini": "Eswatini",
    "N. Cyprus": "Northern Cyprus",
    "Lao PDR": "Laos",
    "Dem. Rep. Korea": "North Korea",
    "Republic of Korea": "South Korea",
    "Macedonia": "North Macedonia",
    "Czech Rep.": "Czechia",
    "St. Vin. and Gren.": "Saint Vincent and the Grenadines",
    "St. Kitts and Nevis": "Saint Kitts and Nevis",
    "São Tomé and Principe": "São Tomé and Príncipe",
    "Antigua and Barb.": "Antigua and Barbuda",
    "Trin. and Tobago": "Trinidad and Tobago",
    "Turks and Caicos Is.": "Turks and Caicos Islands",
    "St. Pierre and Miquelon": "Saint Pierre and Miquelon",
    "Wallis and Futuna Is.": "Wallis and Futuna",
    "Cook Is.": "Cook Islands",
    "N. Mariana Is.": "Northern Mariana Islands",
    "S. Geo. and the Is.": "South Georgia and the South Sandwich Islands",
    "Br. Indian Ocean Ter.": "British Indian Ocean Territory",
    "Pitcairn Is.": "Pitcairn Islands",
    "US Naval Base Guantanamo Bay": "Guantanamo Bay",
}

# NE's ADM0_A3 codes that the World Bank reports under a different ISO3.
WB_ALIAS = {
    "KOS": "XKX",  # Kosovo (World Bank uses XKX)
}

# Antarctica has no permanent population; NE's POP_EST counts wintering
# researchers. Keep it on the globe, but with zero population so it never
# pollutes the world total or the rankings.
ZERO_POP_ISO = {"ATA"}

TERRITORY_LABELS = {
    "ATA": "No permanent population",
}


def area(ring):
    a = 0.0
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % n]
        a += x1 * y2 - x2 * y1
    return abs(a) / 2.0


def simplify(ring, tol):
    """Douglas-Peucker on a closed ring (implicitly returns start point)."""
    if len(ring) < 5:
        return ring
    pts = list(ring) + [ring[0]]
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        lo, hi = stack.pop()
        if hi - lo < 2:
            continue
        x1, y1 = pts[lo]
        x2, y2 = pts[hi]
        dx, dy = x2 - x1, y2 - y1
        norm = math.hypot(dx, dy)
        best_i, best_d = -1, -1.0
        for i in range(lo + 1, hi):
            px, py = pts[i]
            if norm == 0.0:
                d = math.hypot(px - x1, py - y1)
            else:
                d = abs(dy * px - dx * py + x2 * y1 - y2 * x1) / norm
            if d > best_d:
                best_i, best_d = i, d
        if best_d > tol and best_i > 0:
            keep[best_i] = True
            stack.append((lo, best_i))
            stack.append((best_i, hi))
    return [p for p, k in zip(pts, keep) if k][:-1]


def clean_ring(ring):
    out = []
    for lon, lat in ring:
        p = (round(lon, COORD_DECIMALS), round(lat, COORD_DECIMALS))
        if p == (round(-180.0), round(-180.0)):
            continue
        if not out or out[-1] != p:
            out.append(p)
    # remove duplicate closing point: rings are treated as closed loops
    while len(out) > 1 and out[0] == out[-1]:
        out.pop()
    if len(out) < 3 or area(out) < MIN_RING_AREA:
        return None
    return out


def rings_from(geometry):
    gtype = geometry["type"]
    coords = geometry["coordinates"]
    if gtype == "Polygon":
        polys = [coords]
    elif gtype == "MultiPolygon":
        polys = coords
    else:
        return []
    out = []
    for poly in polys:
        if not poly:
            continue
        # keep small countries recognizable: tighten tolerance for small shapes
        xs = [p[0] for p in poly[0]]
        ys = [p[1] for p in poly[0]]
        diag = math.hypot(max(xs) - min(xs), max(ys) - min(ys))
        tol = min(SIMPLIFY_TOL, max(0.0008, diag * 0.12))
        outer = clean_ring(simplify(poly[0], tol))
        if not outer:
            continue  # outer ring too small: drop the whole polygon, holes included
        cleaned = [outer]
        for ring in poly[1:]:
            hole = clean_ring(simplify(ring, tol))
            if hole:
                cleaned.append(hole)
        out.append(cleaned)
    return out


def bbox_diag(geometry):
    if not geometry:
        return 0.0
    gtype = geometry["type"]
    coords = geometry["coordinates"]
    polys = [coords] if gtype == "Polygon" else coords
    xs, ys = [], []
    for poly in polys:
        for ring in poly:
            for lon, lat in ring:
                xs.append(lon)
                ys.append(lat)
    if not xs:
        return 0.0
    return math.hypot(max(xs) - min(xs), max(ys) - min(ys))


def main():
    with open(os.path.join(DATA, SOURCE), encoding="utf-8") as f:
        ne = json.load(f)
    with open(os.path.join(DATA, "worldbank_pop_2023.json"), encoding="utf-8") as f:
        wb_raw = json.load(f)
    wb = {}
    for row in wb_raw[1]:
        if row["value"]:
            wb[row["countryiso3code"]] = int(row["value"])

    countries = []
    skipped = []
    for feat in ne["features"]:
        p = feat["properties"]
        iso = p.get("ADM0_A3") or p.get("ISO_A3") or ""
        name = NAME_FIXES.get(p.get("NAME"), p.get("NAME") or p.get("ADMIN") or "Unknown")
        pop = wb.get(WB_ALIAS.get(iso, iso)) or wb.get(p.get("ISO_A3", "")) or int(p.get("POP_EST") or 0)
        continent = p.get("CONTINENT") or ""
        if iso in ZERO_POP_ISO:
            # Antarctica: keep it, but report no permanent residents.
            pop = 0
        if (pop <= 0 and iso not in ZERO_POP_ISO) or iso in SKIP_ISO:
            skipped.append(name)
            continue
        geometry = feat.get("geometry")
        rings = rings_from(geometry) if geometry else []
        label = None
        if p.get("LABEL_X") is not None and p.get("LABEL_Y") is not None:
            label = (float(p["LABEL_X"]), float(p["LABEL_Y"]))
        elif rings:
            outer = max((poly[0] for poly in rings), key=len)
            label = (
                sum(pt[0] for pt in outer) / len(outer),
                sum(pt[1] for pt in outer) / len(outer),
            )
        if not rings and label is None:
            skipped.append(name)
            continue
        geometry_out = []
        for poly in rings:
            geometry_out.append([[c for pt in ring for c in pt] for ring in poly])
        countries.append([
            name,
            iso,
            int(pop),
            continent,
            geometry_out,
            round(label[0], 3) if label else 0,
            round(label[1], 3) if label else 0,
            round(bbox_diag(geometry), 4),
        ])

    countries.sort(key=lambda c: (-c[2], c[0]))
    total_pop = sum(c[2] for c in countries)

    payload = {
        "year": 2023,
        "world": total_pop,
        "countries": countries,
    }
    blob = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    # Capital cities ([name, lon, lat, population] keyed by ISO code) for the
    # digital-mode dots and the pinned-country card. Population is the city
    # proper figure from Wikidata (optional 4th field). Filtered to the
    # countries actually present in the output.
    caps_path = os.path.join(DATA, "capitals.json")
    caps = None
    if os.path.exists(caps_path):
        with open(caps_path, encoding="utf-8") as f:
            caps_raw = json.load(f)
        isos = {c[1] for c in countries}
        caps = {iso: v for iso, v in caps_raw.items() if iso in isos}

    with open(os.path.join(SRC, "globe_template.html"), encoding="utf-8") as f:
        template = f.read()
    html = template.replace("/*__GLOBE_DATA__*/", blob)
    html = html.replace("/*__CAPITALS__*/",
                        json.dumps(caps, ensure_ascii=False, separators=(",", ":"))
                        if caps else "null")

    # Optionally inline the equirectangular topography+bathymetry texture used
    # by the physical mode. Missing file -> empty URL -> painted fallback.
    tex_path = os.path.join(DATA, "earth_topo.jpg")
    earth_url = ""
    if os.path.exists(tex_path):
        with open(tex_path, "rb") as f:
            earth_url = "data:image/jpeg;base64," + base64.b64encode(f.read()).decode("ascii")
    html = html.replace("__EARTH_IMG_URL__", earth_url)

    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)

    points = sum(len(ring) // 2 for c in countries for poly in c[4] for ring in poly)
    print(f"countries : {len(countries)}")
    print(f"points    : {points}")
    print(f"data size : {len(blob) / 1024:.1f} KB")
    print(f"capitals  : {len(caps) if caps else 0} ({sum(1 for v in (caps or {}).values() if len(v) == 4)} with population)")
    print(f"html size : {os.path.getsize(OUT) / 1024:.1f} KB")
    print(f"texture   : {os.path.getsize(tex_path) / 1024:.1f} KB" if earth_url else "texture   : none (painted physical fallback)")
    print(f"world pop : {total_pop:,}")
    if skipped:
        print("skipped   :", ", ".join(skipped))
    print("\ntop 10:")
    for c in countries[:10]:
        print(f"  {c[0]:<28} {c[2]:>15,}")


if __name__ == "__main__":
    main()


