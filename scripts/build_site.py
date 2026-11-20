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
body.lock{overflow:hidden}
header{position:sticky;top:0;z-index:5;background:var(--dark);color:#fff;padding:14px 16px 12px;box-shadow:0 2px 12px #0003}
.brand{display:flex;align-items:baseline;justify-content:space-between;gap:8px}
.brand h1{margin:0;font-size:22px;letter-spacing:.5px;text-transform:uppercase}
.brand h1 span{color:var(--accent)}
.brand small{opacity:.75;font-size:12px}
.find{display:flex;gap:8px;margin-top:10px}
.find input{flex:1;min-width:0;font-size:17px;padding:11px 14px;border-radius:12px;border:0;font-weight:600}
.find button{font-size:16px;font-weight:800;padding:0 18px;border:0;border-radius:12px;background:var(--accent);color:var(--on)}
.notice{font-size:12.5px;line-height:1.45;background:#fff;border-left:4px solid var(--accent);margin:12px;padding:10px 12px;border-radius:8px}
.bar{display:flex;gap:8px;align-items:center;padding:0 12px 4px}
.chips{display:flex;gap:8px;overflow-x:auto;flex:1;scrollbar-width:none;padding:2px 0}
.chips::-webkit-scrollbar{display:none}
.chips button{flex:none;border:1px solid #0002;background:#fff;color:var(--dark);border-radius:20px;padding:7px 14px;font-size:14px;font-weight:600}
.chips button.on{background:var(--dark);color:#fff}
.bar select{flex:none;border:1px solid #0002;background:#fff;color:var(--dark);border-radius:20px;padding:7px 10px;font-size:14px;font-weight:600}
.count{font-size:12.5px;color:#555;padding:4px 14px 0}
main{display:grid;grid-template-columns:repeat(auto-fill,minmax(165px,1fr));gap:12px;padding:12px}
.card{background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 2px 10px #0001;display:flex;flex-direction:column;position:relative;cursor:pointer}
.card img{width:100%%;height:auto;aspect-ratio:1;object-fit:contain;background:#fff}
.num{position:absolute;top:8px;left:8px;background:var(--accent);color:var(--on);font-weight:900;font-size:17px;padding:4px 11px;border-radius:14px}
.new{position:absolute;top:8px;right:8px;background:var(--dark);color:#fff;font-weight:800;font-size:11px;padding:4px 8px;border-radius:10px;letter-spacing:.5px}
.body{padding:10px 12px 12px;display:flex;flex-direction:column;gap:6px;flex:1}
.body h2{font-size:15px;line-height:1.25;margin:0}
.price{font-size:19px;font-weight:900}
.price small{font-size:12px;font-weight:600;color:#555}
.meta{font-size:12.5px;color:#555}
.buy{margin-top:auto;display:block;text-align:center;text-decoration:none;background:var(--dark);color:#fff;font-weight:800;padding:11px;border-radius:11px;font-size:15px}
.empty{grid-column:1/-1;text-align:center;padding:30px;color:#666}
footer{font-size:12px;color:#666;text-align:center;padding:20px 16px 40px;line-height:1.5}
.sheet{position:fixed;inset:0;z-index:20;background:#0008;display:none;align-items:flex-end;justify-content:center}
.sheet.open{display:flex}
.panel{background:#fff;width:100%%;max-width:560px;max-height:94vh;overflow-y:auto;border-radius:22px 22px 0 0;position:relative;padding-bottom:86px}
@media(min-width:700px){.sheet{align-items:center}.panel{border-radius:22px}}
.x{position:absolute;top:10px;right:10px;z-index:2;width:38px;height:38px;border-radius:50%%;border:0;background:#000a;color:#fff;font-size:20px;line-height:1}
.gal{display:flex;overflow-x:auto;scroll-snap-type:x mandatory;scrollbar-width:none;background:#fff}
.gal::-webkit-scrollbar{display:none}
.gal img{flex:none;width:100%%;aspect-ratio:1;object-fit:contain;scroll-snap-align:center}
.dots{display:flex;gap:6px;justify-content:center;padding:8px}
.dots i{width:7px;height:7px;border-radius:50%%;background:#0002}.dots i.on{background:var(--dark)}
.info{padding:4px 18px 0;display:flex;flex-direction:column;gap:8px}
.info .tag{align-self:flex-start;background:var(--accent);color:var(--on);font-weight:900;padding:4px 12px;border-radius:14px}
.info h2{margin:0;font-size:21px;line-height:1.25}
.info .price{font-size:26px}
.info ul{margin:0;padding-left:19px;font-size:15px;line-height:1.5}
.info .small{font-size:12.5px;color:#555;line-height:1.45}
.share{display:flex;gap:8px}
.share button{flex:1;border:1px solid #0002;background:#fff;color:var(--dark);border-radius:11px;padding:10px;font-size:14px;font-weight:700}
.cta{position:sticky;bottom:0;margin-top:14px;padding:12px 18px 16px;background:linear-gradient(#fff0,#fff 22%%)}
.cta a{display:block;text-align:center;text-decoration:none;background:var(--accent);color:var(--on);font-weight:900;padding:15px;border-radius:14px;font-size:18px}
.panel{padding-bottom:0}
"""

JS = """
const P=JSON.parse(document.getElementById('data').textContent),BY={};P.forEach(p=>BY[p.n]=p);
const $=id=>document.getElementById(id),cards=[...document.querySelectorAll('.card')],grid=document.querySelector('main');
let cat='all',max=0,q='';
function apply(){const words=q.toLowerCase().split(/\\s+/).filter(Boolean);let n=0;
  cards.forEach(c=>{const ok=(cat==='all'||c.dataset.c===cat)&&(!max||+c.dataset.p<=max)&&words.every(w=>c.dataset.t.includes(w));
    c.style.display=ok?'':'none';n+=ok});
  const e=$('empty');e.style.display=n?'none':'block';
  if(!n)e.textContent=q?'Nothing found for "'+q+'". Try another word, or type the number from the post.':'No products here yet.';
  $('count').textContent=n+(n===1?' product':' products')}
function sortBy(k){const f={new:c=>-c.dataset.n,low:c=>+c.dataset.p||1e9,high:c=>-(+c.dataset.p),top:c=>-(+c.dataset.r)}[k];
  cards.slice().sort((a,b)=>f(a)-f(b)||b.dataset.n-a.dataset.n).forEach(c=>grid.insertBefore(c,$('empty')))}
function open(n,push){const p=BY[n];if(!p)return false;
  $('gal').innerHTML='';$('dots').innerHTML='';
  for(let i=1;i<=p.i;i++){const im=new Image();im.src='img/'+n+(i>1?'-'+i:'')+'.webp';im.alt=p.t;$('gal').appendChild(im);
    if(p.i>1)$('dots').appendChild(document.createElement('i'))}
  $('gal').scrollLeft=0;dots();
  $('s-tag').textContent='No. '+n;$('s-title').textContent=p.t;
  $('s-price').innerHTML='';if(p.p){$('s-price').append('₹'+p.p+' ');const s=document.createElement('small');s.textContent='on '+p.s+(p.d?', '+p.d:'')+' (may change)';$('s-price').append(s)}
  $('s-rate').textContent=p.r||'';$('s-feat').innerHTML='';p.f.forEach(x=>{const li=document.createElement('li');li.textContent=x;$('s-feat').appendChild(li)});
  $('s-buy').href=p.l;$('s-buy').textContent='Buy on '+p.s+' →';
  $('sheet').classList.add('open');document.body.classList.add('lock');$('sheet').dataset.n=n;
  if(push)history.pushState({n},'','#'+n);return true}
function close(nav){$('sheet').classList.remove('open');document.body.classList.remove('lock');
  if(nav)history.pushState(null,'',location.pathname)}
function dots(){const g=$('gal'),k=Math.round(g.scrollLeft/g.clientWidth);[...$('dots').children].forEach((d,i)=>d.classList.toggle('on',i===k))}
function fromHash(){const n=location.hash.replace(/[^0-9]/g,'');if(n&&open(n,false))return;close(false)}
function url(n){return location.origin+'/p/'+n+'/'}
$('gal').addEventListener('scroll',dots,{passive:true});
$('f').addEventListener('submit',e=>{e.preventDefault();const v=$('q').value.trim();
  if(/^(no\\.?\\s*)?\\d+$/i.test(v)){const n=v.replace(/[^0-9]/g,'');
    if(!open(n,true)){q='';apply();$('empty').style.display='block';$('empty').textContent='No product No. '+n+' yet. Check the number in the post.'}
    else{$('q').value='';q='';apply()}}
  $('q').blur()});
$('q').addEventListener('input',e=>{const v=e.target.value.trim();q=/^(no\\.?\\s*)?\\d*$/i.test(v)?'':v;apply()});
document.querySelectorAll('.chips button').forEach(b=>b.addEventListener('click',()=>{
  if(b.dataset.max){max=max?0:+b.dataset.max;b.classList.toggle('on',!!max)}
  else{cat=b.dataset.c;document.querySelectorAll('.chips button[data-c]').forEach(x=>x.classList.toggle('on',x===b))}
  apply()}));
$('sort').addEventListener('change',e=>sortBy(e.target.value));
cards.forEach(c=>c.addEventListener('click',e=>{if(!e.target.closest('.buy'))open(c.id,true)}));
$('sheet').addEventListener('click',e=>{if(e.target===$('sheet')||e.target.closest('.x'))close(true)});
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&$('sheet').classList.contains('open'))close(true)});
$('wa').addEventListener('click',()=>{const n=$('sheet').dataset.n,p=BY[n];
  window.open('https://wa.me/?text='+encodeURIComponent(p.t+(p.p?' (₹'+p.p+')':'')+' '+url(n)),'_blank','noopener')});
$('cp').addEventListener('click',async()=>{const n=$('sheet').dataset.n;
  try{if(navigator.share){await navigator.share({title:BY[n].t,url:url(n)})}else{await navigator.clipboard.writeText(url(n));$('cp').textContent='Copied ✓';setTimeout(()=>$('cp').textContent='Share / copy link',1500)}}catch(e){}});
window.addEventListener('popstate',fromHash);window.addEventListener('hashchange',fromHash);
apply();fromHash();
"""

CATS = {"kitchen": "Kitchen", "cleaning": "Cleaning", "storage": "Storage", "bathroom": "Bathroom",
        "home": "Home", "gadgets": "Gadgets", "beauty": "Beauty", "other": "More"}
MAX_PHOTOS = 5
NEW_DAYS = 4


def _checked(p: dict) -> str:
    try:
        return date.fromisoformat(str(p.get("price_checked", ""))).strftime("%-d %b")
    except ValueError:
        return ""


def _rating(p: dict) -> str:
    if not p.get("rating"):
        return ""
    return f"{p['rating']}★" + (f" · {int(p['ratings']):,} ratings" if p.get("ratings") else "")


def _is_new(p: dict) -> bool:
    try:
        return (date.today() - date.fromisoformat(str(p.get("added", "")))).days <= NEW_DAYS
    except ValueError:
        return False


def _card(p: dict, img_rel: str, preview: bool) -> str:
    link = link_of(p) or (product_url(p) if preview else "#")
    store = STORE_NAMES.get(store_of(p), "the store")
    price = f'<div class="price">₹{p["price"]} <small>on {store}</small></div>' if p.get("price") else ""
    text = " ".join([str(p["short_title"]), str(p.get("title", "")), p.get("category", ""), store,
                     " ".join(map(str, p["features"]))]).lower()
    return (f'<article class="card" id="{p["number"]}" data-n="{p["number"]}" data-c="{html.escape(p.get("category", "other"))}" '
            f'data-p="{p.get("price") or 0}" data-r="{p.get("rating") or 0}" data-t="{html.escape(text)}">'
            f'<span class="num">No. {p["number"]}</span>{"<span class=new>NEW</span>" if _is_new(p) else ""}'
            f'<img src="{img_rel}" alt="{html.escape(p["short_title"])}" loading="lazy" width="512" height="512">'
            f'<div class="body"><h2>{html.escape(p["short_title"])}</h2>{price}'
            f'<div class="meta">{html.escape(_rating(p))}</div>'
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
        f'<button data-c="{k}">{CATS.get(k, k.title())}</button>' for k in cats) + '<button data-max="299">Under ₹299</button>'
    cards = "".join(_card(p, f"{img_prefix}img/{p["number"]}.webp", preview) for p in prods)
    data = json.dumps([{"n": p["number"], "t": p["short_title"], "f": [str(f) for f in list(p["features"])[:4]],
                        "p": p.get("price") or 0, "d": _checked(p), "r": _rating(p),
                        "s": STORE_NAMES.get(store_of(p), "the store"), "i": int(p.get("_photos", 1)),
                        "l": link_of(p) or (product_url(p) if preview else "#")} for p in prods],
                      ensure_ascii=False).replace("</", "<\\/")
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
<form class="find" id="f"><input id="q" type="search" enterkeyhint="search" autocomplete="off" placeholder="Post No. or a word (e.g. 12, rack)" aria-label="Product number or word">
<button>Find</button></form></header>
<div class="notice"><b>Ad:</b> the "Buy" links are affiliate links. If you buy, we may earn a small
commission at no extra cost to you. Prices and stock change on the store, so check there before you order.</div>
<div class="bar"><div class="chips">{chips}</div>
<select id="sort" aria-label="Sort"><option value="new">Newest</option><option value="low">Price: low to high</option>
<option value="high">Price: high to low</option><option value="top">Top rated</option></select></div>
<div class="count" id="count"></div>
<main>{cards}<div class="empty" id="empty" style="display:none"></div></main>
<footer>The product catalog for Jugaad House and Handy House on Instagram. It shows products listed on Shopsy, Myntra and other stores. We don't sell or ship anything
ourselves; orders, returns and delivery are handled by the store and its sellers.</footer>
<div class="sheet" id="sheet" role="dialog" aria-modal="true"><div class="panel"><button class="x" aria-label="Close">✕</button>
<div class="gal" id="gal"></div><div class="dots" id="dots"></div>
<div class="info"><span class="tag" id="s-tag"></span><h2 id="s-title"></h2><div class="price" id="s-price"></div>
<div class="small" id="s-rate"></div><ul id="s-feat"></ul>
<div class="share"><button id="wa">Send on WhatsApp</button><button id="cp">Share / copy link</button></div>
<div class="small"><b>Ad:</b> affiliate link. The price is what we saw on the date shown; the store's page has today's price.</div></div>
<div class="cta"><a id="s-buy" rel="sponsored nofollow noopener" target="_blank"></a></div></div></div>
<script type="application/json" id="data">{data}</script>
<script>{JS}</script></body></html>"""


def share_page(site: dict, p: dict) -> str:
    """/p/<No>/ : a tiny page with a preview card (photo, name, price) for WhatsApp etc.; it opens the product."""
    base = (site.get("base_url") or "https://gharfinds.github.io/").rstrip("/")
    t = html.escape(f"No. {p['number']}: {p['short_title']}" + (f" (₹{p['price']})" if p.get("price") else ""))
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{t}</title>
<meta name="robots" content="noindex"><meta property="og:title" content="{t}">
<meta property="og:description" content="{html.escape(str(p['hook']) if p.get('hook') else 'Useful home find')}">
<meta property="og:image" content="{base}/img/{p['number']}.jpg"><meta property="og:type" content="product">
<meta http-equiv="refresh" content="0;url={base}/#{p['number']}">
<script>location.replace("{base}/#{p['number']}")</script></head>
<body><a href="{base}/#{p['number']}">{t}</a></body></html>"""


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


def _fetch(p: dict, url: str):
    import io

    from PIL import Image
    for attempt in range(3):
        r = requests.get(url, headers={"User-Agent": UA, "Referer": REFERERS.get(store_of(p), "https://www.google.com/")},
                         timeout=30)
        if r.status_code == 200 and r.headers.get("content-type", "").startswith("image"):
            return Image.open(io.BytesIO(r.content)).convert("RGB")
        time.sleep(2 + 3 * attempt)
    return None


def thumbs(p: dict, img_dir: Path, base: str) -> int:
    """Download the product's photos: <No>.webp (card), <No>-2.webp … (gallery), <No>.jpg (share preview).
    Returns how many gallery photos exist. The first photo must work; later ones are optional."""
    n = p["number"]
    urls = [first_image(p, base)] + [str(u) for u in list(p["images"])[1:MAX_PHOTOS] if str(u).startswith("http")]
    count = 0
    for i, url in enumerate(urls, start=1):
        dest = img_dir / (f"{n}.webp" if i == 1 else f"{n}-{count + 1}.webp")
        if not dest.exists():
            im = _fetch(p, url)
            if im is None:
                if i == 1:
                    raise SystemExit(f"thumbnail failed for No. {n}: {url}")
                continue
            if i == 1:
                card = im.copy()
                card.thumbnail((800, 800))
                card.save(img_dir / f"{n}.jpg", "JPEG", quality=80)
            im.thumbnail((720, 720))
            im.save(dest, "WEBP", quality=80)
        count += 1
    return count


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
        p["_photos"] = thumbs(p, out / "img", site.get("image_base", "https://images.meesho.com/images/products"))
        (out / "p" / str(p["number"])).mkdir(parents=True, exist_ok=True)
        (out / "p" / str(p["number"]) / "index.html").write_text(share_page(site, p))
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
