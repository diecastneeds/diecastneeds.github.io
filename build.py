"""
Build script for DiecastNeeds.com Catalog
- Reads the product export (products.zip preferred, products.xml fallback)
- Applies 30% markup, rounds up to nearest .99
- Embeds logo.png, outputs index.html + descs.json
Daily update: push a new products.zip to GitHub — auto-rebuilds in ~60s.
"""
import xml.etree.ElementTree as ET
import json, math, html, re, os, base64, zipfile

SCALE_RE = re.compile(r'1/(\d+)')

def markup_price(cost_str):
    try:
        cost = float(cost_str)
        if cost <= 0: return ""
        marked = cost * 1.30
        rounded = math.ceil(marked) - 0.01
        if rounded < marked: rounded += 1
        return f"{rounded:.2f}"
    except: return ""

def clean_desc(raw):
    if not raw: return ""
    decoded = html.unescape(raw)
    decoded = re.sub(r"\r\n|\r|\n", "", decoded)
    decoded = re.sub(r"\s+", " ", decoded).strip()
    return decoded

logo_src = ""
if os.path.exists("logo.png"):
    with open("logo.png", "rb") as f:
        logo_src = "data:image/png;base64," + base64.b64encode(f.read()).decode()
    print("  Logo embedded")

def open_products_xml():
    """Return a file-like handle to the products XML.

    Prefers products.zip (small enough for GitHub's 25MB upload limit).
    Falls back to a plain products.xml if no zip is present.
    """
    if os.path.exists("products.zip"):
        z = zipfile.ZipFile("products.zip")
        xml_name = next(
            (n for n in z.namelist() if n.lower().endswith(".xml")), None
        )
        if not xml_name:
            raise SystemExit("ERROR: products.zip contains no .xml file")
        print(f"Reading {xml_name} from products.zip...")
        return z.open(xml_name)  # streamed, not loaded into memory
    if os.path.exists("products.xml"):
        print("Reading products.xml...")
        return open("products.xml", "rb")
    raise SystemExit("ERROR: neither products.zip nor products.xml found")

products = []
descs = []
seen = 0

def process_product(p):
    """Return (product_dict, description) or None if the product is skipped."""
    cost = p.findtext("price","0") or p.findtext("calculated_price","0") or "0"
    sale_price = markup_price(cost)
    if not sale_price: return None
    if float(sale_price) > 699.99: return None
    imgs = []
    for key in ["image","image_1","image_2","image_3","image_4","image_5"]:
        v = (p.findtext(key,"") or "").strip()
        if v: imgs.append(v)
    if not imgs: return None
    name = (p.findtext("name","") or p.findtext("n","")).strip()
    sm = SCALE_RE.search(name)
    scale = ("1/" + sm.group(1)) if sm else ""
    return {
        "c": p.findtext("code","").strip(),
        "n": name,
        "b": p.findtext("brand","").strip(),
        "p": sale_price,
        "imgs": imgs,
        "sz": scale,
    }, clean_desc(p.findtext("description",""))

src = open_products_xml()
# Stream product-by-product so we never hold the whole 25MB tree in memory.
for event, p in ET.iterparse(src, events=("end",)):
    if p.tag != "product":
        continue
    seen += 1
    result = process_product(p)
    if result:
        prod, desc = result
        products.append(prod)
        descs.append(desc)
    p.clear()  # free the parsed element so memory stays flat

print(f"  Found {seen} products, processed {len(products)}")

CHUNK = 400

# Tag each product with its global index. The description for product i lives
# at descs/<i // CHUNK>.json position <i % CHUNK>. Storing the index also lets
# the modal open without an O(n) PRODUCTS.indexOf() scan.
for i, prod in enumerate(products):
    prod["i"] = i

chunks = [products[i:i+CHUNK] for i in range(0, len(products), CHUNK)]
p_scripts = "\n".join([f"W.push({json.dumps(c, separators=(',',':'))});" for c in chunks])

# Write descriptions as small per-chunk files instead of one ~7.7MB JSON, so
# opening a product only downloads ~1 chunk (a few hundred KB) on demand.
os.makedirs("descs", exist_ok=True)
for fn in os.listdir("descs"):           # clear stale chunks from prior builds
    if fn.endswith(".json"):
        os.remove(os.path.join("descs", fn))
desc_chunks = [descs[i:i+CHUNK] for i in range(0, len(descs), CHUNK)]
for n, dc in enumerate(desc_chunks):
    with open(f"descs/{n}.json", "w", encoding="utf-8") as f:
        json.dump(dc, f, separators=(",",":"), ensure_ascii=False)
print(f"  {len(desc_chunks)} description chunks written to descs/")
if os.path.exists("descs.json"):         # remove superseded monolithic file
    os.remove("descs.json")

# Authoritative price list for server-side checkout validation. Retail prices
# only (already public in the catalog) — never wholesale. The checkout Worker
# fetches this to compute each order's true total so the amount can't be
# tampered with in the browser.
price_map = {}
for _p in products:
    if _p["c"]:
        price_map[_p["c"]] = _p["p"]
with open("prices.json", "w", encoding="utf-8") as f:
    json.dump(price_map, f, separators=(",", ":"))
print(f"  prices.json written ({len(price_map)} SKUs)")

brands = sorted(set(p["b"] for p in products if p["b"]))
brands_json = json.dumps(brands)

# Sort scales numerically by denominator
all_scales = sorted(set(p["sz"] for p in products if p["sz"]), key=lambda s: int(s.split("/")[1]))
scales_json = json.dumps(all_scales)
total = len(products)

# Deployed Cloudflare Worker that mints a Square payment link for each
# order's exact total (validated server-side against prices.json).
CHECKOUT_ENDPOINT = "https://diecastneeds-checkout.twilight-brook-50f5.workers.dev"

# ── Order-notification email (sent from thankyou.html AFTER payment) ──
# Get a free access key at https://web3forms.com (sign up with the address
# below). Paste it here, then rebuild. Free tier = 250 orders/month.
WEB3FORMS_ACCESS_KEY = "dbb6dffa-2621-43ba-8861-b45769091809"
ORDER_EMAIL = "sales@ultimategarageeventstx.com"
# Where Square sends the customer after a successful payment. This URL must be
# entered in your Square Dashboard under the payment link's "Redirect to a
# website after checkout" setting.
THANKYOU_URL = "https://diecastneeds.com/thankyou.html"

# ── Business / contact info (shown in footer + on the info pages) ──
# Confirm the phone number — pulled from the Ultimate Garage Events listing.
BUSINESS_NAME = "Ultimate Garage Events TX LLC"
BUSINESS_LOCATION = "Dallas, Texas"
CONTACT_EMAIL = "sales@ultimategarageeventstx.com"
CONTACT_PHONE = "(888) 505-3125"
SUPPORT_HOURS = "Monday–Friday, 9:00 AM – 5:00 PM CT"

# ── Sales tax ──
# Texas requires collecting on orders shipped TO Texas. Dallas combined rate is
# 8.25%. Orders shipped outside TX are not taxed (no nexus elsewhere). Confirm
# with the Texas Comptroller / your accountant as you grow.
TAX_RATE = 0.0825   # 8.25%
TAX_STATE = "TX"


# ── Events brand + social links ──
EVENTS_URL = "https://ultimategarageeventstx.com"
SOCIAL = {
    "Instagram": "https://www.instagram.com/ultimategarageeventstx/",
    "Facebook":  "https://www.facebook.com/p/Ultimate-Garage-Events-TX-100075534986358/",
    "TikTok":    "",   # paste your TikTok profile URL here
    "YouTube":   "",   # paste your YouTube channel URL here
}

# Shared footer used on the catalog and every info page.
_tel = CONTACT_PHONE.replace(' ','').replace('(','').replace(')','').replace('-','')
social_links_html = "".join(
    f'<a href="{u}" target="_blank" rel="noopener">{name}</a>'
    for name, u in SOCIAL.items() if u
)
_social_row = f'\n    <div class="footer-links footer-social">{social_links_html}</div>' if social_links_html else ""
footer_html = f"""<footer class="site-footer">
  <div class="footer-inner">
    <div class="footer-links">
      <a href="/">Catalog</a>
      <a href="about.html">About</a>
      <a href="events.html">Events</a>
      <a href="contact.html">Contact</a>
      <a href="shipping.html">Shipping</a>
      <a href="returns.html">Returns &amp; Exchanges</a>
      <a href="privacy.html">Privacy</a>
    </div>{_social_row}
    <div class="footer-contact">
      <a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a>
      <span>&middot;</span>
      <a href="tel:{_tel}">{CONTACT_PHONE}</a>
    </div>
    <div class="footer-legal">Free shipping on every order to U.S. addresses &nbsp;&middot;&nbsp; &copy; 2026 {BUSINESS_NAME}. All rights reserved.</div>
  </div>
</footer>"""

html_out = f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
<meta charset=\"UTF-8\">
<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0, viewport-fit=cover\">
<meta name=\"apple-mobile-web-app-capable\" content=\"yes\">
<meta name=\"apple-mobile-web-app-status-bar-style\" content=\"black-translucent\">
<title>DiecastNeeds.com Catalog</title>
<meta name=\"description\" content=\"Shop {total:,}+ diecast model cars, trucks and motorcycles at DiecastNeeds.com. Free shipping on every order. Maisto, Greenlight, Auto World, Hot Wheels and more.\">
<meta name=\"theme-color\" content=\"#0d0f1a\">
<link rel=\"icon\" href=\"logo.png\">
<link rel=\"apple-touch-icon\" href=\"logo.png\">
<link rel=\"canonical\" href=\"https://diecastneeds.com/\">
<meta property=\"og:type\" content=\"website\">
<meta property=\"og:site_name\" content=\"DiecastNeeds.com\">
<meta property=\"og:title\" content=\"DiecastNeeds.com Catalog\">
<meta property=\"og:description\" content=\"Shop {total:,}+ diecast models with free shipping on every order.\">
<meta property=\"og:url\" content=\"https://diecastneeds.com/\">
<meta property=\"og:image\" content=\"https://diecastneeds.com/logo.png\">
<meta name=\"twitter:card\" content=\"summary\">
<meta name=\"twitter:title\" content=\"DiecastNeeds.com Catalog\">
<meta name=\"twitter:description\" content=\"Shop {total:,}+ diecast models with free shipping on every order.\">
<meta name=\"twitter:image\" content=\"https://diecastneeds.com/logo.png\">
<link href=\"https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Sans:wght@300;400;500&display=swap\" rel=\"stylesheet\">
<style>
:root{{--bg:#0d0f1a;--surface:#13151f;--card:#1a1c2a;--border:#252836;--border2:#2e3148;--pink:#ff2d6b;--pink-dim:#cc1f55;--pink-glow:rgba(255,45,107,0.15);--white:#f5f5f5;--muted:#6b6f85;--text:#e8eaf2;--green:#22c55e;--green-dim:#16a34a;--green-glow:rgba(34,197,94,0.12);}}
*{{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent;}}
html{{font-size:16px;}}
body{{background:var(--bg);color:var(--text);font-family:\"DM Sans\",sans-serif;min-height:100vh;overflow-x:hidden;}}
header{{background:var(--surface);border-bottom:2px solid var(--pink);padding:10px 20px;padding-top:max(10px,env(safe-area-inset-top));display:flex;align-items:center;gap:14px;position:sticky;top:0;z-index:200;}}
.logo-img{{height:72px;width:72px;object-fit:contain;border-radius:10px;flex-shrink:0;}}
.logo-text{{display:flex;flex-direction:column;flex:1;min-width:0;}}
.site-name{{font-family:\"Bebas Neue\",sans-serif;font-size:1.5rem;letter-spacing:3px;color:var(--white);line-height:1;white-space:nowrap;}}
.site-name span{{color:var(--pink);}}
.site-sub{{font-size:0.6rem;color:var(--muted);letter-spacing:2.5px;text-transform:uppercase;margin-top:1px;}}
.header-right{{display:flex;align-items:center;gap:8px;flex-shrink:0;}}
.header-count{{background:var(--pink-glow);border:1px solid rgba(255,45,107,0.3);color:var(--pink);font-size:0.65rem;letter-spacing:1.5px;text-transform:uppercase;padding:5px 10px;border-radius:99px;white-space:nowrap;}}
.free-ship-badge{{background:rgba(34,197,94,0.12);border:1px solid rgba(34,197,94,0.35);color:var(--green);font-size:0.65rem;letter-spacing:1.2px;text-transform:uppercase;padding:5px 10px;border-radius:99px;white-space:nowrap;font-weight:600;}}
.ship-tag{{font-size:0.62rem;color:var(--green);letter-spacing:.8px;margin-top:4px;font-weight:500;}}
.cart-btn{{position:relative;background:var(--pink);border:none;color:#fff;padding:8px 16px;border-radius:8px;cursor:pointer;font-family:\"DM Sans\",sans-serif;font-size:0.85rem;font-weight:500;display:flex;align-items:center;gap:6px;white-space:nowrap;transition:background .15s;}}
.cart-btn:hover{{background:var(--pink-dim);}}
.cart-badge{{background:#fff;color:var(--pink);font-size:0.65rem;font-weight:700;width:18px;height:18px;border-radius:50%;display:none;align-items:center;justify-content:center;}}
.cart-badge.show{{display:flex;}}
@media(max-width:420px){{.site-name{{font-size:1.2rem;}}.header-count{{display:none;}}.free-ship-badge{{display:none;}}}}
.controls{{padding:12px 16px;display:flex;flex-direction:column;gap:10px;border-bottom:1px solid var(--border);background:var(--surface);position:sticky;top:92px;z-index:100;}}
.row{{display:flex;gap:8px;}}
.sw{{flex:1;position:relative;}}
.sw::before{{content:\"⌕\";position:absolute;left:12px;top:50%;transform:translateY(-54%);color:var(--muted);font-size:1.1rem;pointer-events:none;}}
input[type=text]{{width:100%;background:var(--card);border:1px solid var(--border2);color:var(--text);padding:11px 12px 11px 36px;border-radius:8px;font-family:\"DM Sans\",sans-serif;font-size:16px;outline:none;-webkit-appearance:none;transition:border-color .2s;}}
input[type=text]:focus{{border-color:var(--pink);}}
input[type=text]::placeholder{{color:var(--muted);}}
select{{flex:1;background:var(--card);border:1px solid var(--border2);color:var(--text);padding:11px 28px 11px 10px;border-radius:8px;font-family:\"DM Sans\",sans-serif;font-size:0.82rem;outline:none;-webkit-appearance:none;appearance:none;background-image:url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='8'%3E%3Cpath d='M1 1l5 5 5-5' stroke='%236b6f85' stroke-width='1.5' fill='none' stroke-linecap='round'/%3E%3C/svg%3E\");background-repeat:no-repeat;background-position:right 10px center;}}
select:focus{{border-color:var(--pink);outline:none;}}
.info{{font-size:0.72rem;color:var(--muted);text-align:right;letter-spacing:.5px;}}
.grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:1px;background:var(--border);}}
@media(min-width:480px){{.grid{{grid-template-columns:repeat(3,1fr);}}}}
@media(min-width:700px){{.grid{{grid-template-columns:repeat(4,1fr);}}}}
@media(min-width:960px){{.grid{{grid-template-columns:repeat(5,1fr);}}}}
@media(min-width:1240px){{.grid{{grid-template-columns:repeat(6,1fr);}}}}
.card{{background:var(--card);display:flex;flex-direction:column;overflow:hidden;cursor:pointer;transition:background .15s;}}
.card:active{{background:#1f2133;}}
@media(hover:hover){{.card:hover{{background:#1f2133;}}.card:hover .iw img{{transform:scale(1.06);}}}}
.iw{{aspect-ratio:4/3;overflow:hidden;background:#0a0c15;position:relative;flex-shrink:0;}}
.iw img{{width:100%;height:100%;object-fit:cover;transition:transform .35s ease;display:block;}}
.ni{{width:100%;height:100%;display:flex;align-items:center;justify-content:center;color:#252836;font-size:2rem;}}
.bt{{position:absolute;top:7px;left:7px;background:rgba(13,15,26,.82);border:1px solid rgba(255,45,107,.4);color:var(--pink);font-size:0.52rem;font-weight:500;letter-spacing:1.2px;text-transform:uppercase;padding:3px 8px;border-radius:99px;-webkit-backdrop-filter:blur(6px);backdrop-filter:blur(6px);max-width:calc(100% - 14px);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}}
.ic{{position:absolute;bottom:7px;right:7px;background:rgba(13,15,26,.78);border:1px solid var(--border2);color:var(--muted);font-size:0.55rem;padding:2px 7px;border-radius:99px;}}
.in-cart-flag{{position:absolute;top:7px;right:7px;background:var(--green);color:#fff;font-size:0.52rem;font-weight:700;padding:3px 7px;border-radius:99px;display:none;}}
.in-cart-flag.show{{display:block;}}
.cb{{padding:10px 11px 13px;flex:1;display:flex;flex-direction:column;gap:5px;}}
.ct{{font-size:0.74rem;font-weight:400;line-height:1.4;color:var(--text);display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;flex:1;}}
.sku-row{{display:flex;align-items:center;gap:5px;margin-top:3px;}}
.sku-label{{font-size:0.6rem;font-weight:700;color:var(--white);letter-spacing:.5px;text-transform:uppercase;}}
.sku-val{{font-size:0.6rem;font-weight:700;color:var(--white);font-family:\"Courier New\",monospace;letter-spacing:.5px;}}
.price-row{{margin-top:2px;}}
.pr{{font-family:\"Bebas Neue\",sans-serif;font-size:1.3rem;letter-spacing:2px;color:var(--pink);}}
.add-btn{{margin-top:6px;width:100%;background:transparent;border:1px solid var(--border2);color:var(--muted);padding:7px;border-radius:6px;font-family:\"DM Sans\",sans-serif;font-size:0.72rem;cursor:pointer;transition:all .15s;text-align:center;}}
.add-btn:hover{{border-color:var(--green);color:var(--green);}}
.add-btn.added{{background:var(--green-glow);border-color:var(--green);color:var(--green);}}
.pagination{{display:flex;justify-content:center;align-items:center;gap:6px;padding:24px 16px;padding-bottom:max(24px,env(safe-area-inset-bottom));border-top:1px solid var(--border);flex-wrap:wrap;}}
.pb{{background:var(--card);border:1px solid var(--border2);color:var(--text);min-width:44px;min-height:44px;padding:0 12px;border-radius:8px;cursor:pointer;font-family:\"DM Sans\",sans-serif;font-size:0.85rem;display:flex;align-items:center;justify-content:center;transition:all .14s;}}
.pb:active,.pb.on{{background:var(--pink);border-color:var(--pink);color:#fff;font-weight:600;}}
.pb:disabled{{opacity:.22;pointer-events:none;}}
.pi{{color:var(--muted);font-size:0.72rem;width:100%;text-align:center;margin-top:4px;}}
.empty{{grid-column:1/-1;padding:60px 20px;text-align:center;color:var(--muted);font-size:.9rem;}}
.mbg{{display:none;position:fixed;inset:0;background:rgba(5,6,15,.95);z-index:500;overflow-y:auto;-webkit-overflow-scrolling:touch;}}
.mbg.open{{display:flex;align-items:flex-start;justify-content:center;}}
.mdl{{background:var(--surface);width:100%;max-width:700px;margin:0 auto;min-height:100%;}}
@media(min-width:720px){{.mdl{{margin:40px auto;min-height:auto;border-radius:14px;overflow:hidden;border:1px solid var(--border2);}}}}
.mhd{{position:sticky;top:0;z-index:10;background:var(--surface);border-bottom:1px solid var(--border);padding:14px 18px;display:flex;align-items:center;justify-content:space-between;}}
.mhd button{{background:var(--card);border:1px solid var(--border2);color:var(--muted);width:38px;height:38px;border-radius:50%;font-size:1.1rem;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:border-color .15s,color .15s;}}
.mhd button:hover{{border-color:var(--pink);color:var(--pink);}}
.mhd-left{{display:flex;flex-direction:column;gap:3px;}}
.mhd-sku{{font-family:\"Courier New\",monospace;font-size:0.72rem;color:var(--white);font-weight:700;}}
.mhd-brand{{font-size:0.6rem;color:var(--pink);letter-spacing:1.5px;text-transform:uppercase;}}
.gal{{background:#07080f;}}.gmain{{width:100%;aspect-ratio:4/3;object-fit:contain;display:block;}}
.gthumbs{{display:flex;gap:6px;padding:10px 14px;overflow-x:auto;-webkit-overflow-scrolling:touch;scrollbar-width:none;background:#0a0c15;}}
.gthumbs::-webkit-scrollbar{{display:none;}}
.gthumb{{width:64px;height:48px;object-fit:cover;border-radius:4px;cursor:pointer;border:2px solid transparent;flex-shrink:0;opacity:.5;transition:opacity .2s,border-color .2s;}}
.gthumb.on{{border-color:var(--pink);opacity:1;}}
.mbody{{padding:20px;}}
.m-title{{font-size:1rem;font-weight:400;line-height:1.5;color:var(--text);margin-bottom:8px;}}
.m-price{{font-family:\"Bebas Neue\",sans-serif;font-size:2.4rem;letter-spacing:2px;color:var(--pink);margin-bottom:16px;display:block;}}
.m-add-btn{{width:100%;padding:14px;margin-bottom:20px;background:var(--green);border:none;color:#fff;border-radius:10px;font-family:\"DM Sans\",sans-serif;font-size:1rem;font-weight:500;cursor:pointer;transition:background .15s;}}
.m-add-btn:hover{{background:var(--green-dim);}}
.m-add-btn.added{{background:var(--green-glow);border:1px solid var(--green);color:var(--green);}}
.mdesc{{font-size:0.82rem;line-height:1.65;color:#9196ad;border-top:1px solid var(--border);padding-top:16px;}}
.mdesc ul{{padding-left:18px;}}.mdesc li{{margin-bottom:5px;}}
.dload{{color:var(--muted);font-size:0.8rem;font-style:italic;}}
.drawer-bg{{display:none;position:fixed;inset:0;background:rgba(5,6,15,.7);z-index:600;}}
.drawer-bg.open{{display:block;}}
.drawer{{position:fixed;top:0;right:0;bottom:0;width:min(500px,100vw);background:var(--surface);border-left:1px solid var(--border2);z-index:700;display:flex;flex-direction:column;transform:translateX(100%);transition:transform .3s cubic-bezier(.4,0,.2,1);}}
.drawer.open{{transform:translateX(0);}}
.drawer-hd{{padding:16px 20px;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between;flex-shrink:0;}}
.drawer-hd h2{{font-family:\"Bebas Neue\",sans-serif;font-size:1.4rem;letter-spacing:3px;color:var(--white);}}
.drawer-hd h2 span{{color:var(--pink);}}
.drawer-close{{background:var(--card);border:1px solid var(--border2);color:var(--muted);width:36px;height:36px;border-radius:50%;cursor:pointer;font-size:1rem;display:flex;align-items:center;justify-content:center;transition:all .15s;}}
.drawer-close:hover{{border-color:var(--pink);color:var(--pink);}}
.drawer-tabs{{display:flex;border-bottom:1px solid var(--border);flex-shrink:0;}}
.dtab{{flex:1;padding:13px;background:none;border:none;color:var(--muted);font-family:\"DM Sans\",sans-serif;font-size:0.82rem;cursor:pointer;border-bottom:2px solid transparent;transition:all .15s;text-align:center;}}
.dtab.on{{color:var(--white);border-bottom-color:var(--pink);}}
.dpanel{{display:none;flex:1;overflow-y:auto;flex-direction:column;}}
.dpanel.on{{display:flex;}}
.drawer-items{{padding:14px 20px;display:flex;flex-direction:column;gap:10px;flex:1;}}
.drawer-empty{{display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;gap:14px;color:var(--muted);}}
.de-icon{{font-size:3rem;opacity:.25;}}
.drawer-empty p{{font-size:0.85rem;}}
.ci{{display:flex;gap:12px;align-items:flex-start;background:var(--card);border:1px solid var(--border);border-radius:10px;padding:10px 12px;}}
.ci-img{{width:64px;height:48px;object-fit:cover;border-radius:6px;flex-shrink:0;background:#0a0c15;}}
.ci-info{{flex:1;min-width:0;}}
.ci-name{{font-size:0.76rem;line-height:1.35;color:var(--text);display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;}}
.ci-meta{{display:flex;align-items:center;justify-content:space-between;margin-top:5px;}}
.ci-sku{{font-size:0.62rem;color:var(--muted);font-family:\"Courier New\",monospace;}}
.ci-price{{font-family:\"Bebas Neue\",sans-serif;font-size:1rem;letter-spacing:1px;color:var(--pink);}}
.ci-qty{{display:flex;align-items:center;gap:8px;margin-top:7px;}}
.qty-btn{{background:var(--border2);border:none;color:var(--text);width:26px;height:26px;border-radius:5px;cursor:pointer;font-size:1rem;display:flex;align-items:center;justify-content:center;transition:background .15s;line-height:1;}}
.qty-btn:hover{{background:var(--pink);color:#fff;}}
.qty-num{{font-size:0.85rem;font-weight:500;min-width:22px;text-align:center;color:var(--white);}}
.ci-remove{{background:none;border:none;color:var(--muted);cursor:pointer;font-size:1rem;padding:4px;flex-shrink:0;transition:color .15s;align-self:flex-start;}}
.ci-remove:hover{{color:var(--pink);}}
.cart-footer{{padding:16px 20px;border-top:1px solid var(--border);flex-shrink:0;background:var(--surface);}}
.cart-total{{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:14px;}}
.cart-total-label{{font-size:0.78rem;color:var(--muted);text-transform:uppercase;letter-spacing:1px;}}
.cart-total-val{{font-family:\"Bebas Neue\",sans-serif;font-size:1.8rem;letter-spacing:2px;color:var(--white);}}
.checkout-btn{{width:100%;padding:15px;background:var(--green);border:none;color:#fff;border-radius:10px;font-family:\"DM Sans\",sans-serif;font-size:1rem;font-weight:600;cursor:pointer;transition:background .15s;letter-spacing:.5px;}}
.checkout-btn:hover{{background:var(--green-dim);}}
.co-wrap{{padding:18px 20px 30px;flex:1;overflow-y:auto;}}
.co-section{{margin-bottom:22px;}}
.co-section h3{{font-size:0.7rem;letter-spacing:1.5px;text-transform:uppercase;color:var(--muted);margin-bottom:12px;padding-bottom:8px;border-bottom:1px solid var(--border);}}
.fg{{display:grid;grid-template-columns:1fr 1fr;gap:8px;}}
.fg.full{{grid-template-columns:1fr;}}
.fi{{display:flex;flex-direction:column;gap:4px;margin-bottom:8px;}}
.fi label{{font-size:0.62rem;letter-spacing:1px;text-transform:uppercase;color:var(--muted);}}
.fi input,.fi-sel{{background:var(--card);border:1px solid var(--border2);color:var(--text);padding:10px 12px;border-radius:7px;font-family:\"DM Sans\",sans-serif;font-size:15px;outline:none;-webkit-appearance:none;width:100%;transition:border-color .2s;}}
.fi input:focus,.fi-sel:focus{{border-color:var(--green);}}
.fi input::placeholder{{color:var(--muted);}}
.fi-sel{{appearance:none;background-image:url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='8'%3E%3Cpath d='M1 1l5 5 5-5' stroke='%236b6f85' stroke-width='1.5' fill='none' stroke-linecap='round'/%3E%3C/svg%3E\");background-repeat:no-repeat;background-position:right 12px center;padding-right:32px;}}
.order-summary{{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:14px 16px;margin-bottom:16px;}}
.os-row{{display:flex;justify-content:space-between;align-items:baseline;font-size:0.78rem;padding:5px 0;color:var(--muted);gap:8px;}}
.os-name{{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}}
.os-row.total{{border-top:1px solid var(--border);margin-top:8px;padding-top:12px;color:var(--white);font-weight:500;font-size:0.92rem;}}
.place-btn{{width:100%;padding:16px;background:var(--green);border:none;color:#fff;border-radius:10px;font-family:\"DM Sans\",sans-serif;font-size:1.05rem;font-weight:600;cursor:pointer;transition:background .15s;letter-spacing:.5px;}}
.place-btn:hover{{background:var(--green-dim);}}
.sq-note{{font-size:0.68rem;color:var(--muted);text-align:center;margin-top:10px;line-height:1.6;}}
.err-msg{{color:var(--pink);font-size:0.78rem;margin-bottom:10px;display:none;}}
.err-msg.show{{display:block;}}
.success-overlay{{display:none;position:fixed;inset:0;background:var(--bg);z-index:900;flex-direction:column;align-items:center;justify-content:center;gap:18px;padding:40px 28px;text-align:center;}}
.success-overlay.show{{display:flex;}}
.success-icon{{font-size:4.5rem;}}
.success-overlay h2{{font-family:\"Bebas Neue\",sans-serif;font-size:2.2rem;letter-spacing:4px;color:var(--green);}}
.success-overlay p{{color:var(--muted);font-size:0.88rem;line-height:1.7;max-width:340px;}}
.success-back{{margin-top:10px;padding:13px 32px;background:var(--pink);border:none;color:#fff;border-radius:10px;font-family:\"DM Sans\",sans-serif;font-size:0.95rem;font-weight:500;cursor:pointer;}}
.success-back:hover{{background:var(--pink-dim);}}
#loader{{position:fixed;inset:0;background:var(--bg);display:flex;flex-direction:column;align-items:center;justify-content:center;gap:20px;z-index:999;font-family:\"Bebas Neue\",sans-serif;font-size:1.4rem;letter-spacing:4px;color:var(--pink);}}
.spin{{width:40px;height:40px;border:3px solid var(--border2);border-top-color:var(--pink);border-radius:50%;animation:spin .7s linear infinite;}}
@keyframes spin{{to{{transform:rotate(360deg);}}}}
.site-footer{{margin-top:0;background:var(--surface);border-top:2px solid var(--pink);padding:28px 20px;padding-bottom:max(28px,env(safe-area-inset-bottom));}}.footer-inner{{max-width:1000px;margin:0 auto;display:flex;flex-direction:column;align-items:center;gap:14px;text-align:center;}}.footer-links{{display:flex;flex-wrap:wrap;justify-content:center;gap:8px 22px;}}.footer-links a{{color:var(--text);text-decoration:none;font-size:0.85rem;letter-spacing:.3px;transition:color .15s;}}.footer-links a:hover{{color:var(--pink);}}.footer-contact{{display:flex;flex-wrap:wrap;justify-content:center;align-items:center;gap:8px;font-size:0.85rem;}}.footer-contact a{{color:var(--pink);text-decoration:none;}}.footer-contact a:hover{{text-decoration:underline;}}.footer-contact span{{color:var(--muted);}}.footer-legal{{color:var(--muted);font-size:0.72rem;line-height:1.6;}}</style>
</head>
<body>
<div id=\"loader\"><div class=\"spin\"></div>LOADING CATALOG</div>
<header>
  <img class=\"logo-img\" src=\"{logo_src}\" alt=\"DiecastNeeds\">
  <div class=\"logo-text\">
    <span class=\"site-name\">DiecastNeeds<span>.com</span></span>
  </div>
  <div class=\"header-right\">
    <span class=\"free-ship-badge\">🚚 Free Shipping!</span>
    <span class=\"header-count\" id=\"tb\">— Models</span>
    <button class=\"cart-btn\" onclick=\"openDrawer()\">🛒 Cart<span class=\"cart-badge\" id=\"cart-badge\">0</span></button>
  </div>
</header>
<div class=\"controls\">
  <div class=\"sw\"><input type=\"text\" id=\"q\" placeholder=\"Search name, brand, SKU…\" oninput=\"onF()\" autocomplete=\"off\" autocorrect=\"off\" autocapitalize=\"off\" spellcheck=\"false\"></div>
  <div class=\"row\">
    <select id=\"bs\" onchange=\"onF()\"><option value=\"\">All Brands</option></select>
    <select id=\"szs\" onchange=\"onF()\"><option value=\"\">All Sizes</option></select>
    <select id=\"ss\" onchange=\"onF()\"><option value=\"name\">Name A–Z</option><option value=\"pa\">Price ↑</option><option value=\"pd\">Price ↓</option><option value=\"sku\">SKU</option></select>
  </div>
  <div class=\"info\" id=\"inf\"></div>
</div>
<div class=\"grid\" id=\"grid\"></div>
<div class=\"pagination\" id=\"pg\"></div>
<div class=\"mbg\" id=\"mbg\" onclick=\"bgClick(event)\">
  <div class=\"mdl\">
    <div class=\"mhd\"><div class=\"mhd-left\"><span class=\"mhd-sku\" id=\"msk\"></span><span class=\"mhd-brand\" id=\"mbrand\"></span></div><button onclick=\"closeM()\">✕</button></div>
    <div class=\"gal\"><img class=\"gmain\" id=\"gmain\" src=\"\" alt=\"\"><div class=\"gthumbs\" id=\"gthumbs\"></div></div>
    <div class=\"mbody\">
      <div class=\"m-title\" id=\"mtitle\"></div>
      <span class=\"m-price\" id=\"mprice\"></span>
      <button class=\"m-add-btn\" id=\"m-add-btn\" onclick=\"addFromModal()\">+ Add to Cart</button>
      <div class=\"mdesc\" id=\"mdesc\"><span class=\"dload\">Loading description…</span></div>
    </div>
  </div>
</div>
<div class=\"drawer-bg\" id=\"drawer-bg\" onclick=\"closeDrawer()\"></div>
<div class=\"drawer\" id=\"drawer\">
  <div class=\"drawer-hd\"><h2>Your <span>Cart</span></h2><button class=\"drawer-close\" onclick=\"closeDrawer()\">✕</button></div>
  <div class=\"drawer-tabs\">
    <button class=\"dtab on\" id=\"tab-cart\" onclick=\"switchTab('cart')\">🛒 Cart</button>
    <button class=\"dtab\" id=\"tab-checkout\" onclick=\"switchTab('checkout')\">💳 Checkout</button>
  </div>
  <div class=\"dpanel on\" id=\"panel-cart\">
    <div class=\"drawer-items\" id=\"drawer-items\"><div class=\"drawer-empty\"><div class=\"de-icon\">🛒</div><p>Your cart is empty</p></div></div>
    <div class=\"cart-footer\" id=\"cart-footer\" style=\"display:none;\">
      <div class=\"cart-total\"><span class=\"cart-total-label\">Subtotal</span><span class=\"cart-total-val\" id=\"cart-total\">$0.00</span></div><div style=\"font-size:0.72rem;color:var(--muted);margin:-6px 0 12px;\">Tax &amp; final total shown at checkout</div>
      <button class=\"checkout-btn\" onclick=\"switchTab('checkout')\">Proceed to Checkout →</button>
    </div>
  </div>
  <div class=\"dpanel\" id=\"panel-checkout\">
    <div class=\"co-wrap\">
      <div class=\"co-section\"><h3>Contact Info</h3>
        <div class=\"fg\"><div class=\"fi\"><label>First Name *</label><input type=\"text\" id=\"co-fname\" placeholder=\"John\"></div><div class=\"fi\"><label>Last Name *</label><input type=\"text\" id=\"co-lname\" placeholder=\"Smith\"></div></div>
        <div class=\"fi\"><label>Email *</label><input type=\"email\" id=\"co-email\" placeholder=\"you@email.com\"></div>
        <div class=\"fi\"><label>Phone *</label><input type=\"tel\" id=\"co-phone\" placeholder=\"(555) 000-0000\"></div>
      </div>
      <div class=\"co-section\"><h3>Shipping Address</h3>
        <div class=\"fi\"><label>Street Address *</label><input type=\"text\" id=\"co-addr1\" placeholder=\"123 Main St\"></div>
        <div class=\"fi\"><label>Apt / Suite</label><input type=\"text\" id=\"co-addr2\" placeholder=\"Optional\"></div>
        <div class=\"fg\"><div class=\"fi\"><label>City *</label><input type=\"text\" id=\"co-city\" placeholder=\"Houston\"></div>
          <div class=\"fi\"><label>State *</label><select class=\"fi-sel\" id=\"co-state\" onchange=\"renderOrderSummary()\"><option value=\"\">State</option><option>AL</option><option>AK</option><option>AZ</option><option>AR</option><option>CA</option><option>CO</option><option>CT</option><option>DE</option><option>FL</option><option>GA</option><option>HI</option><option>ID</option><option>IL</option><option>IN</option><option>IA</option><option>KS</option><option>KY</option><option>LA</option><option>ME</option><option>MD</option><option>MA</option><option>MI</option><option>MN</option><option>MS</option><option>MO</option><option>MT</option><option>NE</option><option>NV</option><option>NH</option><option>NJ</option><option>NM</option><option>NY</option><option>NC</option><option>ND</option><option>OH</option><option>OK</option><option>OR</option><option>PA</option><option>RI</option><option>SC</option><option>SD</option><option>TN</option><option selected>TX</option><option>UT</option><option>VT</option><option>VA</option><option>WA</option><option>WV</option><option>WI</option><option>WY</option></select></div>
        </div>
        <div class=\"fi\"><label>ZIP Code *</label><input type=\"text\" id=\"co-zip\" placeholder=\"77001\" maxlength=\"10\"></div>
      </div>
      <div class=\"co-section\"><h3>Order Summary</h3><div class=\"order-summary\" id=\"co-summary\"></div></div>
      <div class=\"err-msg\" id=\"co-err\">Please fill in all required fields.</div>
      <button class=\"place-btn\" onclick=\"placeOrder()\">Pay with Square →</button>
      <p class=\"sq-note\">You'll be redirected to Square's secure checkout. Your card info is never stored here. 🔒</p>
    </div>
  </div>
</div>
<div class=\"success-overlay\" id=\"success-overlay\">
  <div class=\"success-icon\">✅</div>
  <h2>Redirecting to Payment!</h2>
  <p>Square is opening in a new tab. Complete payment there and you'll receive a receipt by email.</p>
  <button class=\"success-back\" onclick=\"document.getElementById('success-overlay').classList.remove('show')\">← Back to Catalog</button>
</div>
{footer_html}
<script>
const CHECKOUT_ENDPOINT=\"{CHECKOUT_ENDPOINT}\";
const W=[];
{p_scripts}
const PRODUCTS=W.flat();
const PS=40;
const TAX_RATE={TAX_RATE};const TAX_STATE="{TAX_STATE}";const TAX_LABEL="Texas Tax ({TAX_RATE*100:g}%)";
const DC={CHUNK};
const DESC_CACHE={{}};
const CART_KEY="dcn_cart_v1";
function loadCart(){{try{{const r=localStorage.getItem(CART_KEY);return r?JSON.parse(r):[];}}catch(_){{return[];}}}}
function saveCart(){{try{{localStorage.setItem(CART_KEY,JSON.stringify(CART));}}catch(_){{}}}}
let fil=[],pg=1,descLoading=false,pendingIdx=null,openProduct=null,CART=loadCart();
function e(s){{return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");}}
function fmt(n){{return"$"+parseFloat(n).toFixed(2);}}
function onF(){{pg=1;aF();}}
function aF(){{
  const q=document.getElementById("q").value.toLowerCase();
  const br=document.getElementById("bs").value;
  const sz=document.getElementById("szs").value;
  const so=document.getElementById("ss").value;
  fil=PRODUCTS.filter(p=>(!q||p.n.toLowerCase().includes(q)||p.b.toLowerCase().includes(q)||p.c.toLowerCase().includes(q))&&(!br||p.b===br)&&(!sz||p.sz===sz));
  fil.sort((a,b)=>so==="pa"?+a.p-+b.p:so==="pd"?+b.p-+a.p:so==="sku"?a.c.localeCompare(b.c):a.n.localeCompare(b.n));
  document.getElementById("inf").textContent=fil.length.toLocaleString()+" products found";
  rG();rP();
}}
function isInCart(code){{return CART.some(i=>i.c===code);}}
function rG(){{
  const g=document.getElementById("grid");
  const sl=fil.slice((pg-1)*PS,pg*PS);
  if(!sl.length){{g.innerHTML="<div class='empty'>No products found.</div>";return;}}
  g.innerHTML=sl.map((p,i)=>{{
    const idx=(pg-1)*PS+i;
    const img=p.imgs&&p.imgs.length?p.imgs[0]:"";
    const ih=img?`<img src="${{e(img)}}" alt="" loading="lazy" onerror="this.style.display='none';this.parentElement.insertAdjacentHTML('afterbegin','<div class=ni>🚗</div>')">`:"<div class='ni'>🚗</div>";
    const ic=p.imgs&&p.imgs.length>1?`<span class="ic">📷 ${{p.imgs.length}}</span>`:"";
    const inCart=isInCart(p.c);
    return `<div class="card" onclick="openM(${{idx}})"><div class="iw">${{ih}}<span class="bt">${{e(p.b)}}</span>${{ic}}<span class="in-cart-flag${{inCart?" show":""}}" id="flag-${{e(p.c)}}">✓ In Cart</span></div><div class="cb"><div class="ct">${{e(p.n)}}</div><div class="sku-row"><span class="sku-label">SKU#</span><span class="sku-val">${{e(p.c)}}</span></div><div class="price-row"><span class="pr">${{p.p?"$"+p.p:"—"}}</span></div><div class="ship-tag">🚚 Free Shipping</div><button class="add-btn${{inCart?" added":""}}" id="addbtn-${{e(p.c)}}" onclick="event.stopPropagation();toggleCart(${{idx}})">${{inCart?"✓ In Cart":"+ Add to Cart"}}</button></div></div>`;
  }}).join("");
}}
function rP(){{
  const tot=Math.ceil(fil.length/PS);const el=document.getElementById("pg");
  if(tot<=1){{el.innerHTML="";return;}}
  const rng=new Set([1,tot]);
  for(let i=Math.max(2,pg-2);i<=Math.min(tot-1,pg+2);i++)rng.add(i);
  const arr=[...rng].sort((a,b)=>a-b);
  let h=`<button class="pb" onclick="gP(${{pg-1}})" ${{pg===1?"disabled":""}}>←</button>`;
  let last=0;
  for(const n of arr){{if(n-last>1)h+=`<span style="color:var(--muted)">…</span>`;h+=`<button class="pb ${{n===pg?"on":""}}" onclick="gP(${{n}})">${{n}}</button>`;last=n;}}
  h+=`<button class="pb" onclick="gP(${{pg+1}})" ${{pg===tot?"disabled":""}}>→</button><div class="pi">Page ${{pg}} of ${{tot}}</div>`;
  el.innerHTML=h;
}}
function gP(n){{const tot=Math.ceil(fil.length/PS);if(n<1||n>tot)return;pg=n;rG();rP();window.scrollTo({{top:0,behavior:"smooth"}});}}
function toggleCart(idx){{const p=fil[idx];if(!p)return;isInCart(p.c)?removeFromCart(p.c):addToCart(p);}}
function addToCart(p){{
  if(isInCart(p.c)){{CART.find(i=>i.c===p.c).qty++;updateCartUI();return;}}
  CART.push({{...p,qty:1}});updateCartUI();
  const btn=document.getElementById("addbtn-"+p.c);if(btn){{btn.textContent="✓ In Cart";btn.classList.add("added");}}
  const flag=document.getElementById("flag-"+p.c);if(flag)flag.classList.add("show");
  if(openProduct&&openProduct.c===p.c)syncModalBtn();
}}
function removeFromCart(code){{
  CART=CART.filter(i=>i.c!==code);updateCartUI();
  const btn=document.getElementById("addbtn-"+code);if(btn){{btn.textContent="+ Add to Cart";btn.classList.remove("added");}}
  const flag=document.getElementById("flag-"+code);if(flag)flag.classList.remove("show");
  if(openProduct&&openProduct.c===code)syncModalBtn();
  renderCartItems();
}}
function changeQty(code,delta){{const item=CART.find(i=>i.c===code);if(!item)return;item.qty=Math.max(1,item.qty+delta);updateCartUI();renderCartItems();}}
function cartTotal(){{return CART.reduce((s,i)=>s+(parseFloat(i.p)||0)*i.qty,0);}}
function selState(){{const el=document.getElementById("co-state");return el?el.value:"";}}
function taxAmt(){{return selState()===TAX_STATE?cartTotal()*TAX_RATE:0;}}
function grandTotal(){{return cartTotal()+taxAmt();}}
function updateCartUI(){{
  saveCart();
  const total=CART.reduce((s,i)=>s+i.qty,0);
  const badge=document.getElementById("cart-badge");
  if(total>0){{badge.textContent=total;badge.classList.add("show");}}else badge.classList.remove("show");
  document.getElementById("cart-total").textContent=fmt(cartTotal());
  document.getElementById("cart-footer").style.display=CART.length?"block":"none";
  renderCartItems();renderOrderSummary();
}}
function renderCartItems(){{
  const el=document.getElementById("drawer-items");
  if(!CART.length){{el.innerHTML="<div class='drawer-empty'><div class='de-icon'>🛒</div><p>Your cart is empty</p></div>";return;}}
  el.innerHTML=CART.map(p=>{{
    const img=p.imgs&&p.imgs.length?p.imgs[0]:"";
    return `<div class="ci">${{img?`<img class="ci-img" src="${{e(img)}}" alt="" onerror="this.style.display='none'">`:`<div class="ci-img" style="display:flex;align-items:center;justify-content:center;color:#252836;font-size:1.4rem;">🚗</div>`}}<div class="ci-info"><div class="ci-name">${{e(p.n)}}</div><div class="ci-meta"><span class="ci-sku">SKU# ${{e(p.c)}}</span><span class="ci-price">${{fmt(parseFloat(p.p)*p.qty)}}</span></div><div class="ci-qty"><button class="qty-btn" onclick="changeQty('${{e(p.c)}}',-1)">−</button><span class="qty-num">${{p.qty}}</span><button class="qty-btn" onclick="changeQty('${{e(p.c)}}',1)">+</button></div></div><button class="ci-remove" onclick="removeFromCart('${{e(p.c)}}')">✕</button></div>`;
  }}).join("");
}}
function renderOrderSummary(){{
  const el=document.getElementById("co-summary");if(!el)return;
  if(!CART.length){{el.innerHTML="<div style='color:var(--muted);font-size:0.8rem;text-align:center;padding:8px 0;'>No items in cart</div>";return;}}
  el.innerHTML=CART.map(p=>`<div class="os-row"><span class="os-name">${{e(p.n)}}</span><span style="white-space:nowrap;">×${{p.qty}} ${{fmt(parseFloat(p.p)*p.qty)}}</span></div>`).join("")+`<div class="os-row"><span>Subtotal</span><span>${{fmt(cartTotal())}}</span></div>`+(taxAmt()>0?`<div class="os-row"><span>${{TAX_LABEL}}</span><span>${{fmt(taxAmt())}}</span></div>`:(selState()?"":`<div class="os-row"><span>Tax</span><span>Select state</span></div>`))+`<div class="os-row total"><span>Total</span><span>${{fmt(grandTotal())}}</span></div>`;
}}
function switchTab(tab){{
  ["cart","checkout"].forEach(t=>{{document.getElementById("tab-"+t).classList.toggle("on",t===tab);document.getElementById("panel-"+t).classList.toggle("on",t===tab);}});
  if(tab==="checkout")renderOrderSummary();
}}
async function placeOrder(){{
  const fname=document.getElementById("co-fname").value.trim();
  const lname=document.getElementById("co-lname").value.trim();
  const email=document.getElementById("co-email").value.trim();
  const phone=document.getElementById("co-phone").value.trim();
  const addr1=document.getElementById("co-addr1").value.trim();
  const city=document.getElementById("co-city").value.trim();
  const state=document.getElementById("co-state").value;
  const zip=document.getElementById("co-zip").value.trim();
  const errEl=document.getElementById("co-err");
  if(!fname||!lname||!email||!phone||!addr1||!city||!state||!zip){{errEl.textContent="Please fill in all required fields.";errEl.classList.add("show");return;}}
  if(!CART.length){{errEl.textContent="Your cart is empty.";errEl.classList.add("show");return;}}
  errEl.classList.remove("show");
  const addr2=document.getElementById("co-addr2").value.trim();
  // Build an order reference + the full order, and stash it in the browser.
  // The thank-you page (reached only AFTER a successful Square payment) reads
  // this and emails the full details. Only a short reference goes in the URL.
  const now=new Date();
  const ymd=now.getFullYear().toString()+String(now.getMonth()+1).padStart(2,"0")+String(now.getDate()).padStart(2,"0");
  const ref="DCN-"+ymd+"-"+Math.random().toString(36).slice(2,6).toUpperCase();
  const count=CART.reduce((s,i)=>s+i.qty,0);
  const order={{
    ref:ref,placed:now.toISOString(),
    customer:{{fname,lname,email,phone,addr1,addr2,city,state,zip}},
    items:CART.map(p=>({{n:p.n,c:p.c,qty:p.qty,p:p.p}})),
    count:count,subtotal:fmt(cartTotal()),tax:fmt(taxAmt()),taxLabel:(taxAmt()>0?TAX_LABEL:""),total:fmt(grandTotal())
  }};
  try{{localStorage.setItem("dcn_pending_order_v1",JSON.stringify(order));}}catch(_){{}}
  // Ask our checkout Worker to mint a Square payment link for THIS cart's exact
  // total. The amount is recomputed server-side from the published price list,
  // so it can't be tampered with in the browser.
  const payBtn=document.querySelector("#panel-checkout .place-btn");
  const payLabel=payBtn?payBtn.textContent:"";
  if(payBtn){{payBtn.disabled=true;payBtn.textContent="Processing…";}}
  errEl.classList.remove("show");
  try{{
    const resp=await fetch(CHECKOUT_ENDPOINT,{{
      method:"POST",
      headers:{{"Content-Type":"application/json"}},
      body:JSON.stringify({{ref:ref,state:state,items:CART.map(p=>({{c:p.c,qty:p.qty}}))}})
    }});
    const data=await resp.json().catch(()=>null);
    if(!resp.ok||!data||!data.url){{throw new Error(data&&data.error?data.error:"checkout failed");}}
    // Success: clear the cart (order is saved for the thank-you page) and go to Square.
    closeDrawer();CART=[];updateCartUI();
    document.querySelectorAll(".add-btn").forEach(b=>{{b.textContent="+ Add to Cart";b.classList.remove("added");}});
    document.querySelectorAll(".in-cart-flag").forEach(f=>f.classList.remove("show"));
    if(openProduct)syncModalBtn();
    window.location.href=data.url;
  }}catch(err){{
    if(payBtn){{payBtn.disabled=false;payBtn.textContent=payLabel||"Pay with Square →";}}
    errEl.textContent="Sorry, we couldn't start checkout. Please try again in a moment.";
    errEl.classList.add("show");
  }}
}}
function syncModalBtn(){{const btn=document.getElementById("m-add-btn");if(!openProduct)return;if(isInCart(openProduct.c)){{btn.textContent="✓ In Cart";btn.classList.add("added");}}else{{btn.textContent="+ Add to Cart";btn.classList.remove("added");}}}}
function addFromModal(){{if(!openProduct)return;isInCart(openProduct.c)?removeFromCart(openProduct.c):addToCart(openProduct);syncModalBtn();}}
function openM(idx){{
  const p=fil[idx];if(!p)return;openProduct=p;pendingIdx=p.i;
  document.getElementById("msk").textContent="SKU# "+p.c;document.getElementById("mbrand").textContent=p.b;
  document.getElementById("mtitle").textContent=p.n;document.getElementById("mprice").textContent=p.p?"$"+p.p:"—";
  document.getElementById("mdesc").innerHTML="<span class='dload'>Loading description…</span>";syncModalBtn();
  const imgs=p.imgs||[];const gm=document.getElementById("gmain");const gt=document.getElementById("gthumbs");
  if(imgs.length){{gm.src=imgs[0];gm.style.display="block";if(imgs.length>1){{gt.style.display="flex";gt.innerHTML=imgs.map((s,i)=>`<img class="gthumb ${{i===0?"on":""}}" src="${{e(s)}}" onclick="setImg(this,'${{e(s)}}')" loading="lazy">`).join("");}}else{{gt.style.display="none";}}}}else{{gm.style.display="none";gt.style.display="none";}}
  document.getElementById("mbg").classList.add("open");document.body.style.overflow="hidden";loadDescs();
}}
function loadDescs(){{
  if(pendingIdx===null){{return;}}
  const ck=Math.floor(pendingIdx/DC);
  if(DESC_CACHE[ck]){{showDesc();return;}}
  if(descLoading)return;descLoading=true;
  fetch("descs/"+ck+".json").then(r=>r.json()).then(d=>{{DESC_CACHE[ck]=d;descLoading=false;showDesc();}}).catch(()=>{{descLoading=false;document.getElementById("mdesc").innerHTML="<span class='dload'>Description unavailable.</span>";}});
}}
function showDesc(){{
  if(pendingIdx===null)return;
  const ck=Math.floor(pendingIdx/DC),chunk=DESC_CACHE[ck];
  if(!chunk)return;
  const d=chunk[pendingIdx%DC]||"";
  document.getElementById("mdesc").innerHTML=d?`<div>${{d}}</div>`:"<span class='dload'>No description available.</span>";
}}
function setImg(el,src){{document.getElementById("gmain").src=src;document.querySelectorAll(".gthumb").forEach(t=>t.classList.remove("on"));el.classList.add("on");}}
function closeM(){{document.getElementById("mbg").classList.remove("open");document.body.style.overflow="";}}
function bgClick(ev){{if(ev.target===document.getElementById("mbg"))closeM();}}
function openDrawer(){{document.getElementById("drawer-bg").classList.add("open");document.getElementById("drawer").classList.add("open");document.body.style.overflow="hidden";}}
function closeDrawer(){{document.getElementById("drawer-bg").classList.remove("open");document.getElementById("drawer").classList.remove("open");document.body.style.overflow="";}}
document.addEventListener("keydown",ev=>{{if(ev.key==="Escape"){{closeM();closeDrawer();}}}});
setTimeout(()=>{{
  document.getElementById("tb").textContent=PRODUCTS.length.toLocaleString()+" Models";
  const brands={brands_json};
  const sel=document.getElementById("bs");
  brands.forEach(b=>{{const o=document.createElement("option");o.value=b;o.textContent=b;sel.appendChild(o);}});
  const scales={scales_json};
  const szsel=document.getElementById("szs");
  scales.forEach(s=>{{const o=document.createElement("option");o.value=s;o.textContent=s+" Scale";szsel.appendChild(o);}});
  fil=[...PRODUCTS];aF();updateCartUI();
  document.getElementById("loader").style.display="none";
}},50);
</script>
</body>
</html>"""

with open("index.html","w",encoding="utf-8") as f:
    f.write(html_out)
print(f"Built index.html ({os.path.getsize('index.html')//1024}KB) — {total} products, {len(brands)} brands")

# ── Thank-you / order-confirmation page ──────────────────────────────────────
# Square redirects here after a successful payment. It reads the order that the
# catalog stashed in the browser and emails the full details to ORDER_EMAIL via
# Web3Forms, then clears it so a refresh can't double-send.
thankyou_out = f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
<meta charset=\"UTF-8\">
<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0, viewport-fit=cover\">
<meta name=\"robots\" content=\"noindex\">
<title>Order Confirmed — DiecastNeeds.com</title>
<link rel=\"icon\" href=\"logo.png\">
<link href=\"https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Sans:wght@300;400;500&display=swap\" rel=\"stylesheet\">
<style>
:root{{--bg:#0d0f1a;--surface:#13151f;--card:#1a1c2a;--border:#252836;--border2:#2e3148;--pink:#ff2d6b;--pink-dim:#cc1f55;--white:#f5f5f5;--muted:#6b6f85;--text:#e8eaf2;--green:#22c55e;}}
*{{box-sizing:border-box;margin:0;padding:0;}}
body{{background:var(--bg);color:var(--text);font-family:\"DM Sans\",sans-serif;min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:18px;padding:48px 24px;text-align:center;}}
.logo{{height:80px;width:80px;object-fit:contain;border-radius:14px;margin-bottom:6px;}}
.icon{{font-size:4rem;}}
h1{{font-family:\"Bebas Neue\",sans-serif;font-size:2.4rem;letter-spacing:4px;color:var(--green);}}
p{{color:var(--muted);font-size:0.95rem;line-height:1.7;max-width:420px;}}
.ref{{font-family:\"Courier New\",monospace;color:var(--white);background:var(--card);border:1px solid var(--border2);padding:10px 18px;border-radius:10px;font-size:1rem;letter-spacing:1px;}}
.detail{{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:16px 20px;max-width:420px;width:100%;text-align:left;font-size:0.86rem;color:var(--text);}}
.detail .row{{display:flex;justify-content:space-between;gap:10px;padding:4px 0;}}
.detail .row span:first-child{{color:var(--muted);}}
.btn{{margin-top:8px;padding:14px 34px;background:var(--pink);border:none;color:#fff;border-radius:10px;font-family:\"DM Sans\",sans-serif;font-size:1rem;font-weight:500;cursor:pointer;text-decoration:none;}}
.btn:hover{{background:var(--pink-dim);}}
.muted-note{{font-size:0.75rem;color:var(--muted);max-width:420px;}}
</style>
</head>
<body>
<img class=\"logo\" src=\"{logo_src}\" alt=\"DiecastNeeds\">
<div class=\"icon\">✅</div>
<h1 id=\"headline\">Thank You!</h1>
<p id=\"sub\">Your payment was received. We're getting your order ready to ship.</p>
<div class=\"ref\" id=\"refbox\" style=\"display:none;\"></div>
<div class=\"detail\" id=\"detail\" style=\"display:none;\"></div>
<p class=\"muted-note\">A receipt has been emailed to you by Square. Questions? Email {ORDER_EMAIL}.</p>
<a class=\"btn\" href=\"/\">← Back to Catalog</a>
<script>
const ACCESS_KEY=\"{WEB3FORMS_ACCESS_KEY}\";
const ORDER_EMAIL=\"{ORDER_EMAIL}\";
const KEY_SET=ACCESS_KEY && ACCESS_KEY.indexOf(\"PASTE-\")===-1;
function qp(){{const o={{}};new URLSearchParams(location.search).forEach((v,k)=>o[k]=v);return o;}}
function esc(s){{return String(s==null?\"\":s);}}
(function(){{
  let order=null;
  try{{const r=localStorage.getItem(\"dcn_pending_order_v1\");if(r)order=JSON.parse(r);}}catch(_){{}}
  if(!order){{return;}}  // direct visit or already processed — show generic thanks
  // Show the customer their order summary
  document.getElementById(\"refbox\").style.display=\"block\";
  document.getElementById(\"refbox\").textContent=\"Order \"+order.ref;
  const c=order.customer;
  const itemsHtml=order.items.map(i=>`<div class=\"row\"><span>${{esc(i.n)}} (SKU ${{esc(i.c)}}) ×${{i.qty}}</span><span>$${{esc(i.p)}}</span></div>`).join(\"\");
  document.getElementById(\"detail\").style.display=\"block\";
  document.getElementById(\"detail\").innerHTML=itemsHtml+`<div class=\"row\"><span>Subtotal</span><span>${{esc(order.subtotal||order.total)}}</span></div>`+(order.tax&&order.taxLabel?`<div class=\"row\"><span>${{esc(order.taxLabel)}}</span><span>${{esc(order.tax)}}</span></div>`:"")+`<div class=\"row\" style=\"border-top:1px solid var(--border);margin-top:8px;padding-top:10px;font-weight:600;color:#fff;\"><span>Total</span><span>${{esc(order.total)}}</span></div>`;
  // Email the full order to the store (only after this page loads = after payment)
  const sq=qp();
  const itemsText=order.items.map(i=>`• ${{i.n}} (SKU ${{i.c}}) ×${{i.qty}} @ $${{i.p}}`).join(\"\\n\");
  const payload={{
    access_key:ACCESS_KEY,
    subject:\"New Order \"+order.ref+\" — DiecastNeeds.com\",
    from_name:\"DiecastNeeds Store\",
    replyto:c.email,
    order_reference:order.ref,
    placed_at:order.placed,
    customer_name:c.fname+\" \"+c.lname,
    customer_email:c.email,
    customer_phone:c.phone,
    shipping_address:[c.addr1,c.addr2,c.city+\", \"+c.state+\" \"+c.zip].filter(Boolean).join(\"\\n\"),
    item_count:order.count,
    subtotal:order.subtotal||"",
    tax:(order.tax&&order.taxLabel?order.taxLabel+": "+order.tax:"No tax (shipped outside TX)"),
    order_total:order.total,
    items:itemsText,
    square_transaction:sq.transactionId||sq.orderId||sq.referenceId||\"(see Square dashboard)\"
  }};
  function done(){{ try{{localStorage.removeItem(\"dcn_pending_order_v1\");}}catch(_){{}} }}
  if(!KEY_SET){{
    console.warn(\"Web3Forms access key not set — order email skipped. Order:\",payload);
    return; // leave order in storage so it can be recovered once the key is set
  }}
  fetch(\"https://api.web3forms.com/submit\",{{
    method:\"POST\",
    headers:{{\"Content-Type\":\"application/json\",\"Accept\":\"application/json\"}},
    body:JSON.stringify(payload)
  }}).then(r=>r.json()).then(d=>{{ if(d && d.success){{done();}} }})
    .catch(e=>console.error(\"Order email failed:\",e));
}})();
</script>
</body>
</html>"""

with open("thankyou.html","w",encoding="utf-8") as f:
    f.write(thankyou_out)
print(f"Built thankyou.html ({os.path.getsize('thankyou.html')//1024}KB)")

# ── Static info pages (About / Contact / Shipping / Returns / Privacy) ────────
# Each shares the catalog's dark theme and the same footer. Edit the wording
# below freely — these are your store's policies in your own voice.
def info_page(slug, page_title, body_html):
    css = (
        ":root{--bg:#0d0f1a;--surface:#13151f;--card:#1a1c2a;--border:#252836;"
        "--border2:#2e3148;--pink:#ff2d6b;--pink-dim:#cc1f55;--white:#f5f5f5;"
        "--muted:#6b6f85;--text:#e8eaf2;--green:#22c55e;}"
        "*{box-sizing:border-box;margin:0;padding:0;}"
        "body{background:var(--bg);color:var(--text);font-family:'DM Sans',sans-serif;"
        "min-height:100vh;display:flex;flex-direction:column;line-height:1.7;}"
        "header{background:var(--surface);border-bottom:2px solid var(--pink);"
        "padding:12px 20px;display:flex;align-items:center;gap:14px;position:sticky;top:0;z-index:50;}"
        ".logo-img{height:56px;width:56px;object-fit:contain;border-radius:10px;}"
        ".site-name{font-family:'Bebas Neue',sans-serif;font-size:1.5rem;letter-spacing:3px;"
        "color:var(--white);text-decoration:none;}"
        ".site-name span{color:var(--pink);}"
        ".back{margin-left:auto;color:var(--pink);text-decoration:none;font-size:0.85rem;}"
        ".back:hover{text-decoration:underline;}"
        "main{flex:1;max-width:760px;margin:0 auto;padding:40px 22px 60px;width:100%;}"
        "h1{font-family:'Bebas Neue',sans-serif;font-size:2.4rem;letter-spacing:2px;"
        "color:var(--white);margin-bottom:6px;}"
        ".updated{color:var(--muted);font-size:0.78rem;margin-bottom:26px;}"
        "h2{font-size:1.1rem;color:var(--white);margin:26px 0 8px;}"
        "p{margin-bottom:14px;color:#c7cbdb;}"
        "ul{margin:0 0 16px 22px;color:#c7cbdb;}"
        "li{margin-bottom:8px;}"
        "a{color:var(--pink);}"
        ".card{background:var(--card);border:1px solid var(--border2);border-radius:12px;"
        "padding:18px 20px;margin-bottom:16px;}"
        ".card a{font-weight:500;}"
        + footer_css_for_pages
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
<title>{page_title} — DiecastNeeds.com</title>
<meta name="description" content="{page_title} for DiecastNeeds.com — diecast model cars with free U.S. shipping.">
<link rel="icon" href="logo.png">
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Sans:wght@300;400;500&display=swap" rel="stylesheet">
<style>{css}</style>
</head>
<body>
<header>
  <img class="logo-img" src="{logo_src}" alt="DiecastNeeds">
  <a class="site-name" href="/">DiecastNeeds<span>.com</span></a>
  <a class="back" href="/">← Back to Catalog</a>
</header>
<main>
{body_html}
</main>
{footer_html}
</body>
</html>"""

# Footer CSS for the standalone pages (plain braces — not inside an f-string template).
footer_css_for_pages = (
 ".site-footer{background:var(--surface);border-top:2px solid var(--pink);"
 "padding:28px 20px;padding-bottom:max(28px,env(safe-area-inset-bottom));}"
 ".footer-inner{max-width:1000px;margin:0 auto;display:flex;flex-direction:column;align-items:center;gap:14px;text-align:center;}"
 ".footer-links{display:flex;flex-wrap:wrap;justify-content:center;gap:8px 22px;}"
 ".footer-links a{color:var(--text);text-decoration:none;font-size:0.85rem;letter-spacing:.3px;}"
 ".footer-links a:hover{color:var(--pink);}"
 ".footer-contact{display:flex;flex-wrap:wrap;justify-content:center;align-items:center;gap:8px;font-size:0.85rem;}"
 ".footer-contact a{color:var(--pink);text-decoration:none;}"
 ".footer-contact span{color:var(--muted);}"
 ".footer-legal{color:var(--muted);font-size:0.72rem;line-height:1.6;}"
)

POLICY_UPDATED = "Last updated: June 2026"

about_body = f"""<h1>About DiecastNeeds.com</h1>
<div class="updated">{POLICY_UPDATED}</div>
<p>DiecastNeeds.com is an online diecast model store operated by {BUSINESS_NAME}, based in {BUSINESS_LOCATION}. We're car enthusiasts first, and we built this shop to make it easy to find quality diecast models at fair prices.</p>
<p>Our catalog features thousands of officially licensed diecast cars, trucks, motorcycles, and aircraft across popular scales (1/64, 1/24, 1/18 and more) from trusted manufacturers like Maisto, Greenlight, Auto World, and others.</p>
<h2>Why shop with us</h2>
<ul>
<li><strong>Free shipping</strong> on every order to U.S. addresses.</li>
<li>A large, regularly updated selection of in-demand models.</li>
<li>Secure checkout handled by Square — we never see or store your card details.</li>
<li>Real people behind the store. Questions? <a href="contact.html">Get in touch</a> any time.</li>
</ul>
<p>Thanks for supporting a small business and sharing the hobby with us.</p>"""

contact_body = f"""<h1>Contact Us</h1>
<div class="updated">We're happy to help with orders, products, or anything else.</div>
<div class="card">
<p style="margin-bottom:8px;"><strong>Email:</strong> <a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a></p>
<p style="margin-bottom:8px;"><strong>Phone:</strong> <a href="tel:{CONTACT_PHONE.replace(' ','').replace('(','').replace(')','').replace('-','')}">{CONTACT_PHONE}</a></p>
<p style="margin-bottom:8px;"><strong>Hours:</strong> {SUPPORT_HOURS}</p>
<p style="margin-bottom:0;"><strong>Location:</strong> {BUSINESS_LOCATION}</p>
</div>
<h2>Order questions</h2>
<p>For the fastest help with an existing order, email us with your order number (it looks like <em>DCN-YYYYMMDD-XXXX</em>) and we'll get right back to you, usually within one business day.</p>"""

shipping_body = f"""<h1>Shipping Policy</h1>
<div class="updated">{POLICY_UPDATED}</div>
<h2>Free U.S. shipping</h2>
<p>Every order ships <strong>free</strong> via standard ground service to addresses within the United States. The price you see is the price you pay — shipping is already included.</p>
<h2>Processing &amp; delivery</h2>
<p>Orders are typically processed within 1–3 business days. Once shipped, standard ground delivery usually takes several business days depending on your location. Tracking is provided whenever it's available from the carrier.</p>
<h2>U.S. addresses only</h2>
<p>We ship to U.S. addresses only. If a package is sent to a U.S. freight forwarder and then re-shipped internationally, we cannot be responsible for any loss or damage that occurs after it leaves the original U.S. delivery address.</p>
<h2>Sales tax</h2>
<p>Orders shipped to Texas addresses include {TAX_RATE*100:g}% Texas sales tax, calculated and shown at checkout before you pay. Orders shipped outside Texas are not charged sales tax.</p>
<h2>Questions</h2>
<p>Email <a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a> with any shipping questions.</p>"""

returns_body = f"""<h1>Returns &amp; Exchanges</h1>
<div class="updated">{POLICY_UPDATED}</div>
<p>We want you to be happy with your order. Please read the conditions below — because of how our products are sourced and shipped, these terms are firm.</p>
<h2>Timeframes</h2>
<ul>
<li><strong>Damaged or defective items:</strong> contact us <strong>within 48 hours of delivery</strong> so we can file a claim with the carrier. Reports made after that window cannot be honored.</li>
<li><strong>Returns or exchanges:</strong> you must notify us with your reason <strong>within 14 days of delivery</strong>. Requests outside this window cannot be accepted.</li>
</ul>
<h2>Condition requirements</h2>
<ul>
<li>Items must be in original factory condition, in the original manufacturer's box, and packed exactly as they arrived.</li>
<li>Please do not glue, modify, or repair any parts without our authorization. Items that have been glued or modified, or returned without the original box, cannot be accepted.</li>
</ul>
<h2>Shipping charges</h2>
<p>Shipping and handling costs are non-refundable, <strong>except</strong> when we shipped the wrong item. In that case we'll cover return shipping and send the correct item, or issue a full refund if it's unavailable. Please report an incorrect item within one week of delivery.</p>
<h2>Refused or undeliverable packages</h2>
<p>Packages that are refused, unclaimed, or undeliverable will be canceled and refunded, less the original shipping cost.</p>
<h2>How to start a return</h2>
<p>Email <a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a> with your order number and the reason for the return, and we'll guide you through the next steps.</p>"""

privacy_body = f"""<h1>Privacy Policy</h1>
<div class="updated">{POLICY_UPDATED}</div>
<p>This policy explains what information we collect when you shop at DiecastNeeds.com and how we use it.</p>
<h2>What we collect</h2>
<p>When you place an order, we collect the details you provide: your name, email address, phone number, shipping address, and the items in your order. We use this only to process, ship, and support your order.</p>
<h2>Payments</h2>
<p>Payments are processed securely by Square. Your card details are entered on Square's secure checkout — we never see or store your full payment card information.</p>
<h2>Who we share with</h2>
<ul>
<li><strong>Square</strong> — to process your payment.</li>
<li><strong>Our fulfillment partner and shipping carriers</strong> — to pack and deliver your order.</li>
</ul>
<p>We do not sell your personal information, and we don't share it for unrelated marketing.</p>
<h2>Your choices</h2>
<p>You can ask us what information we have about you, or request that we delete it, by emailing <a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a>.</p>"""

events_cta = f'<p><a href="{EVENTS_URL}" target="_blank" rel="noopener" style="display:inline-block;background:var(--pink);color:#fff;text-decoration:none;padding:14px 28px;border-radius:10px;font-weight:500;margin:6px 0 4px;">Visit UltimateGarageEventsTX.com &rarr;</a></p>'
page_social = "".join(
    f'<a href="{u}" target="_blank" rel="noopener" style="display:inline-block;border:1px solid var(--border2);color:var(--text);text-decoration:none;padding:9px 16px;border-radius:8px;margin:4px 8px 4px 0;font-size:0.9rem;">{name}</a>'
    for name, u in SOCIAL.items() if u
)
events_body = f"""<h1>Car Shows &amp; Events</h1>
<div class="updated">Presented by {BUSINESS_NAME}</div>
<p>DiecastNeeds.com is the model-car side of {BUSINESS_NAME} &mdash; but for us, cars aren't just a hobby, they're a whole community. Through <strong>Ultimate Garage Events</strong> we host judged car &amp; truck shows, meets, and cruises across Texas.</p>
<p>If you love the diecast in your display case, you'll love seeing the real thing in person. Come hang out, show off your ride, and talk cars with fellow enthusiasts.</p>
<div class="card">
<h2 style="margin-top:0;">Come check out a show</h2>
<p>See upcoming events, locations, and tickets:</p>
{events_cta}
</div>
<h2>Follow along</h2>
<p>Event announcements, build features, and behind-the-scenes content:</p>
<p>{page_social}</p>"""

for slug, title, body in [
    ("about", "About Us", about_body),
    ("events", "Car Shows & Events", events_body),
    ("contact", "Contact Us", contact_body),
    ("shipping", "Shipping Policy", shipping_body),
    ("returns", "Returns & Exchanges", returns_body),
    ("privacy", "Privacy Policy", privacy_body),
]:
    with open(f"{slug}.html", "w", encoding="utf-8") as f:
        f.write(info_page(slug, title, body))
print("Built info pages: about, events, contact, shipping, returns, privacy")
