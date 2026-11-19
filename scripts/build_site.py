#!/usr/bin/env python3
"""Build the public catalog site (GitHub Pages) from data/products/*.yaml + site.yaml.

One page per Instagram account (same products, own colours), newest first, find-by-number.
Run: python scripts/build_site.py --out _site     (downloads each product's first photo as a thumbnail)
"""
from __future__ import annotations

import argparse
import html
import json
import sys
import time
from datetime import date
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131 Safari/537.36"


STORE_NAMES = {"shopsy": "Shopsy", "myntra": "Myntra", "meesho": "Meesho", "amazon": "Amazon",
               "flipkart": "Flipkart", "ajio": "AJIO"}
REFERERS = {"shopsy": "https://www.shopsy.in/", "myntra": "https://www.myntra.com/", "meesho": "https://www.meesho.com/",
            "amazon": "https://www.amazon.in/", "flipkart": "https://www.flipkart.com/", "ajio": "https://www.ajio.com/"}


def link_of(p: dict) -> str:
    return (p.get("aff_url") or "").strip()


def store_of(p: dict) -> str:
    return p.get("store") or ("meesho" if p.get("meesho_url") else "")


def product_url(p: dict) -> str:
    return p.get("product_url") or p.get("meesho_url") or ""


def first_image(p: dict, base: str) -> str:
    img = str(p["images"][0])
    return img if img.startswith("http") else f"{base}/{p['image_folder']}/{img}_512.webp"


CSS = """
:root{--dark:%(dark)s;--accent:%(accent)s;--light:%(light)s;--on:%(on)s}
*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:150px}
body{margin:0;font-family:Inter,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;background:var(--light);color:var(--dark)}
header{position:sticky;top:0;z-index:5;background:var(--dark);color:#fff;padding:14px 16px 12px;box-shadow:0 2px 12px #0003}
.brand{display:flex;align-items:baseline;justify-content:space-between;gap:8px}
.brand h1{margin:0;font-size:22px;letter-spacing:.5px;text-transform:uppercase}
.brand h1 span{color:var(--accent)}
.brand small{opacity:.75;font-size:12px}
.find{display:flex;gap:8px;margin-top:10px}
.find input{flex:1;min-width:0;font-size:18px;padding:11px 14px;border-radius:12px;border:0;font-weight:700}
.find button{font-size:16px;font-weight:800;padding:0 18px;border:0;border-radius:12px;background:var(--accent);color:var(--on)}
.notice{font-size:12.5px;line-height:1.45;background:#fff;border-left:4px solid var(--accent);margin:12px;padding:10px 12px;border-radius:8px}
.chips{display:flex;gap:8px;overflow-x:auto;padding:0 12px 4px}
.chips button{flex:none;border:1px solid #0002;background:#fff;color:var(--dark);border-radius:20px;padding:7px 14px;font-size:14px;font-weight:600}
.chips button.on{background:var(--dark);color:#fff}
main{display:grid;grid-template-columns:repeat(auto-fill,minmax(165px,1fr));gap:12px;padding:12px}
.card{background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 2px 10px #0001;display:flex;flex-direction:column;position:relative;transition:box-shadow .3s,transform .3s}
.card.hit{box-shadow:0 0 0 4px var(--accent),0 6px 24px #0003;transform:scale(1.02)}
.card img{width:100%%;height:auto;aspect-ratio:1;object-fit:contain;background:#fff}
.num{position:absolute;top:8px;left:8px;background:var(--accent);color:var(--on);font-weight:900;font-size:17px;padding:4px 11px;border-radius:14px}
.body{padding:10px 12px 12px;display:flex;flex-direction:column;gap:6px;flex:1}
.body h2{font-size:15px;line-height:1.25;margin:0}
.body ul{margin:0;padding-left:17px;font-size:13px;line-height:1.35;color:#333}
.meta{font-size:12.5px;color:#555}
.buy{margin-top:auto;display:block;text-align:center;text-decoration:none;background:var(--dark);color:#fff;font-weight:800;padding:11px;border-radius:11px;font-size:15px}
.empty{grid-column:1/-1;text-align:center;padding:30px;color:#666}
footer{font-size:12px;color:#666;text-align:center;padding:20px 16px 40px;line-height:1.5}
"""

JS = """
const cards=[...document.querySelectorAll('.card')];
function show(n){n=String(n).replace(/[^0-9]/g,'');if(!n)return;
  const c=document.getElementById(n);document.querySelectorAll('.card.hit').forEach(x=>x.classList.remove('hit'));
  const e=document.getElementById('empty');
  if(!c){e.style.display='block';e.textContent='No product No. '+n+' yet. Check the number in the post.';return}
  e.style.display='none';filter('all');c.classList.add('hit');c.scrollIntoView({block:'center'});
  history.replaceState(null,'','#'+n)}
function filter(cat){document.querySelectorAll('.chips button').forEach(b=>b.classList.toggle('on',b.dataset.c===cat));
  cards.forEach(c=>c.style.display=(cat==='all'||c.dataset.c===cat)?'':'none')}
document.getElementById('f').addEventListener('submit',e=>{e.preventDefault();show(document.getElementById('q').value)});
document.querySelectorAll('.chips button').forEach(b=>b.addEventListener('click',()=>filter(b.dataset.c)));
window.addEventListener('load',()=>{if(location.hash)show(location.hash.slice(1))});
window.addEventListener('hashchange',()=>show(location.hash.slice(1)));
"""

CATS = {"kitchen": "Kitchen", "cleaning": "Cleaning", "storage": "Storage", "bathroom": "Bathroom",
        "home": "Home", "gadgets": "Gadgets", "beauty": "Beauty", "other": "More"}


def _card(p: dict, img_rel: str, preview: bool) -> str:
    feats = "".join(f"<li>{html.escape(str(f))}</li>" for f in list(p["features"])[:3])
    link = link_of(p) or (product_url(p) if preview else "#")
    store = STORE_NAMES.get(store_of(p), "the store")
    rating = ""
    if p.get("rating"):
        rating = f"{p['rating']}★"
        if p.get("ratings"):
            rating += f" · {int(p['ratings']):,} ratings"
    price = ""
    if p.get("price"):
        checked = p.get("price_checked", "")
        try:
            checked = date.fromisoformat(str(checked)).strftime("%-d %b")
        except ValueError:
            pass
        price = f"₹{p['price']} on {store}, {checked} (may change)"
    meta = " · ".join(x for x in (rating, price) if x)
    return (f'<article class="card" id="{p["number"]}" data-c="{html.escape(p.get("category", "other"))}">'
            f'<span class="num">No. {p["number"]}</span>'
            f'<img src="{img_rel}" alt="{html.escape(p["short_title"])}" loading="lazy" width="512" height="512">'
            f'<div class="body"><h2>{html.escape(p["short_title"])}</h2><ul>{feats}</ul>'
            f'<div class="meta">{html.escape(meta)}</div>'
            f'<a class="buy" href="{html.escape(link)}" rel="sponsored nofollow noopener" target="_blank">'
            f'Buy on {store}</a></div></article>')


def page(site: dict, account: str, prods: list[dict], img_prefix: str, preview: bool = False) -> str:
    acc = site["accounts"][account]
    c = acc["colors"]
    css = CSS % {"dark": c["dark"], "accent": c["accent"], "light": c["light"], "on": c.get("text_on_accent", c["dark"])}
    name = acc["name"]
    first, _, rest = name.partition(" ")
    cats = sorted({p.get("category", "other") for p in prods})
    chips = '<button data-c="all" class="on">All</button>' + "".join(
        f'<button data-c="{k}">{CATS.get(k, k.title())}</button>' for k in cats)
    cards = "".join(_card(p, f"{img_prefix}img/{p["number"]}.webp", preview) for p in prods)
    handle = acc.get("handle") or ""
    suffix = site.get("title_suffix") or ""
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(name)}{(" " + suffix) if suffix else ""} · find your product number</title>
<meta name="description" content="Useful home and kitchen finds. Type the number from the Instagram post.">
<meta name="robots" content="noindex">
<style>{css}</style></head><body>
<header><div class="brand"><h1>{html.escape(first)} <span>{html.escape(rest)}</span></h1>
<small>{'@' + html.escape(handle) if handle else ''}</small></div>
<form class="find" id="f"><input id="q" inputmode="numeric" pattern="[0-9]*" placeholder="Type product No. (e.g. 12)" aria-label="Product number">
<button>Find</button></form></header>
<div class="notice"><b>Ad:</b> the "Buy" links are affiliate links. If you buy, we may earn a small
commission at no extra cost to you. Prices and stock change on the store, so check there before you order.</div>
<div class="chips">{chips}</div>
<main>{cards}<div class="empty" id="empty" style="display:none"></div></main>
<footer>The product catalog for Jugaad House and Handy House on Instagram. It shows products listed on Shopsy, Myntra and other stores. We don't sell or ship anything
ourselves; orders, returns and delivery are handled by the store and its sellers.</footer>
<script>{JS}</script></body></html>"""


def load_products(preview: bool) -> list[dict]:
    out = []
    for f in sorted((ROOT / "data" / "products").glob("*.yaml")):
        p = yaml.safe_load(f.read_text()) or {}
        if p.get("status", "active") != "active":
            continue
        if not link_of(p) and not preview:
            continue
        out.append(p)
    return sorted(out, key=lambda p: p["number"], reverse=True)


def thumb(p: dict, dest: Path, base: str) -> None:
    if dest.exists():
        return
    import io

    from PIL import Image
    url = first_image(p, base)
    for attempt in range(3):
        r = requests.get(url, headers={"User-Agent": UA, "Referer": REFERERS.get(store_of(p), "https://www.google.com/")},
                         timeout=30)
        if r.status_code == 200 and r.headers.get("content-type", "").startswith("image"):
            im = Image.open(io.BytesIO(r.content)).convert("RGB")
            im.thumbnail((512, 512))
            im.save(dest, "WEBP", quality=82)
            return
        time.sleep(2 + 3 * attempt)
    raise SystemExit(f"thumbnail failed for No. {p['number']}: {url} (HTTP {r.status_code})")


def check(prods: list[dict]) -> list[str]:
    errs, seen = [], set()
    for p in prods:
        n = p.get("number")
        if n in seen:
            errs.append(f"duplicate number {n}")
        seen.add(n)
        for k in ("number", "short_title", "images", "features"):
            if not p.get(k):
                errs.append(f"No. {n}: missing {k}")
        if not product_url(p):
            errs.append(f"No. {n}: missing product_url")
    return errs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="_site")
    a = ap.parse_args()
    site = yaml.safe_load((ROOT / "site.yaml").read_text())
    preview = bool(site.get("preview"))
    prods = load_products(preview)
    errs = check(prods)
    if errs:
        sys.exit("\n".join(errs))
    out = ROOT / a.out
    (out / "img").mkdir(parents=True, exist_ok=True)
    for p in prods:
        thumb(p, out / "img" / f"{p['number']}.webp", site.get("image_base", "https://images.meesho.com/images/products"))
    for acc, cfg in site["accounts"].items():
        sub = (cfg.get("path") or "").strip("/")
        target = out / sub if sub else out
        target.mkdir(parents=True, exist_ok=True)
        prefix = "../" * (len(sub.split("/")) if sub else 0)
        (target / "index.html").write_text(page(site, acc, prods, prefix, preview))
    (out / "products.json").write_text(json.dumps(
        [{"number": p["number"], "title": p["short_title"], "link": link_of(p) or None} for p in prods], indent=1))
    (out / ".nojekyll").write_text("")
    print(f"built {len(prods)} products for {len(site['accounts'])} account page(s)")


if __name__ == "__main__":
    main()
