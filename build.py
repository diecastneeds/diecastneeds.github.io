"""
Build script for DiecastNeeds.com Catalog
- Reads products.xml
- Applies 25% markup, rounds up to nearest .99
- Embeds logo.png, outputs index.html + descs.json
Daily update: push new products.xml to GitHub — auto-rebuilds in ~60s.
"""
import xml.etree.ElementTree as ET
import json, math, html, re, os, base64

def markup_price(cost_str):
    try:
        cost = float(cost_str)
        if cost <= 0: return ""
        marked = cost * 1.25
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

print("Parsing products.xml...")
tree = ET.parse("products.xml")
root = tree.getroot()
px = root.findall("product")
print(f"  Found {len(px)} products")

products = []
descs = []
for p in px:
    cost = p.findtext("price","0") or p.findtext("calculated_price","0") or "0"
    sale_price = markup_price(cost)
    if not sale_price: continue
    imgs = []
    for key in ["image","image_1","image_2","image_3","image_4","image_5"]:
        v = (p.findtext(key,"") or "").strip()
        if v: imgs.append(v)
    products.append({
        "c": p.findtext("code","").strip(),
        "n": (p.findtext("name","") or p.findtext("n","")).strip(),
        "b": p.findtext("brand","").strip(),
        "p": sale_price,
        "imgs": imgs,
    })
    descs.append(clean_desc(p.findtext("description","")))

print(f"  Processed {len(products)} products")

with open("descs.json","w",encoding="utf-8") as f:
    json.dump(descs, f, separators=(",",":"), ensure_ascii=False)
print(f"  descs.json written ({os.path.getsize('descs.json')//1024}KB)")

CHUNK = 400
chunks = [products[i:i+CHUNK] for i in range(0, len(products), CHUNK)]
p_scripts = "\n".join([f"W.push({json.dumps(c, separators=(',',':'))});" for c in chunks])
brands = sorted(set(p["b"] for p in products if p["b"]))
brands_json = json.dumps(brands)
total = len(products)

SQUARE_PAYMENT_LINK = "YOUR_SQUARE_PAYMENT_LINK"

html_out = f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
<meta charset=\"UTF-8\">
<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0, viewport-fit=cover\">
<meta name=\"apple-mobile-web-app-capable\" content=\"yes\">
<meta name=\"apple-mobile-web-app-status-bar-style\" content=\"black-translucent\">
<title>DiecastNeeds.com Catalog</title>
<link href=\"https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Sans:wght@300;400;500&display=swap\" rel=\"stylesheet\">
<style>
:root{{--bg:#0d0f1a;--surface:#13151f;--card:#1a1c2a;--border:#252836;--border2:#2e3148;--pink:#ff2d6b;--pink-dim:#cc1f55;--pink-glow:rgba(255,45,107,0.15);--white:#f5f5f5;--muted:#6b6f85;--text:#e8eaf2;--green:#22c55e;--green-dim:#16a34a;--green-glow:rgba(34,197,94,0.12);}}
*{{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent;}}
html{{font-size:16px;}}
body{{background:var(--bg);color:var(--text);font-family:\"DM Sans\",sans-serif;min-height:100vh;overflow-x:hidden;}}
header{{background:var(--surface);border-bottom:2px solid var(--pink);padding:10px 20px;padding-top:max(10px,env(safe-area-inset-top));display:flex;align-items:center;gap:14px;position:sticky;top:0;z-index:200;}}
.logo-img{{height:50px;width:50px;object-fit:contain;border-radius:8px;flex-shrink:0;}}
.logo-text{{display:flex;flex-direction:column;flex:1;min-width:0;}}
.site-name{{font-family:\"Bebas Neue\",sans-serif;font-size:1.5rem;letter-spacing:3px;color:var(--white);line-height:1;white-space:nowrap;}}
.site-name span{{color:var(--pink);}}
.site-sub{{font-size:0.6rem;color:var(--muted);letter-spacing:2.5px;text-transform:uppercase;margin-top:1px;}}
.header-right{{display:flex;align-items:center;gap:8px;flex-shrink:0;}}
.header-count{{background:var(--pink-glow);border:1px solid rgba(255,45,107,0.3);color:var(--pink);font-size:0.65rem;letter-spacing:1.5px;text-transform:uppercase;padding:5px 10px;border-radius:99px;white-space:nowrap;}}
.cart-btn{{position:relative;background:var(--pink);border:none;color:#fff;padding:8px 16px;border-radius:8px;cursor:pointer;font-family:\"DM Sans\",sans-serif;font-size:0.85rem;font-weight:500;display:flex;align-items:center;gap:6px;white-space:nowrap;transition:background .15s;}}
.cart-btn:hover{{background:var(--pink-dim);}}
.cart-badge{{background:#fff;color:var(--pink);font-size:0.65rem;font-weight:700;width:18px;height:18px;border-radius:50%;display:none;align-items:center;justify-content:center;}}
.cart-badge.show{{display:flex;}}
@media(max-width:420px){{.site-name{{font-size:1.2rem;}}.header-count{{display:none;}}}}
.controls{{padding:12px 16px;display:flex;flex-direction:column;gap:10px;border-bottom:1px solid var(--border);background:var(--surface);position:sticky;top:72px;z-index:100;}}
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
</style>
</head>
<body>
<div id=\"loader\"><div class=\"spin\"></div>LOADING CATALOG</div>
<header>
  <img class=\"logo-img\" src=\"{logo_src}\" alt=\"DiecastNeeds\">
  <div class=\"logo-text\">
    <span class=\"site-name\">DiecastNeeds<span>.com</span></span>
    <span class=\"site-sub\">Catalog</span>
  </div>
  <div class=\"header-right\">
    <span class=\"header-count\" id=\"tb\">— Models</span>
    <button class=\"cart-btn\" onclick=\"openDrawer()\">🛒 Cart<span class=\"cart-badge\" id=\"cart-badge\">0</span></button>
  </div>
</header>
<div class=\"controls\">
  <div class=\"sw\"><input type=\"text\" id=\"q\" placeholder=\"Search name, brand, SKU…\" oninput=\"onF()\" autocomplete=\"off\" autocorrect=\"off\" autocapitalize=\"off\" spellcheck=\"false\"></div>
  <div class=\"row\">
    <select id=\"bs\" onchange=\"onF()\"><option value=\"\">All Brands</option></select>
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
      <div class=\"cart-total\"><span class=\"cart-total-label\">Order Total</span><span class=\"cart-total-val\" id=\"cart-total\">$0.00</span></div>
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
          <div class=\"fi\"><label>State *</label><select class=\"fi-sel\" id=\"co-state\"><option value=\"\">State</option><option>AL</option><option>AK</option><option>AZ</option><option>AR</option><option>CA</option><option>CO</option><option>CT</option><option>DE</option><option>FL</option><option>GA</option><option>HI</option><option>ID</option><option>IL</option><option>IN</option><option>IA</option><option>KS</option><option>KY</option><option>LA</option><option>ME</option><option>MD</option><option>MA</option><option>MI</option><option>MN</option><option>MS</option><option>MO</option><option>MT</option><option>NE</option><option>NV</option><option>NH</option><option>NJ</option><option>NM</option><option>NY</option><option>NC</option><option>ND</option><option>OH</option><option>OK</option><option>OR</option><option>PA</option><option>RI</option><option>SC</option><option>SD</option><option>TN</option><option selected>TX</option><option>UT</option><option>VT</option><option>VA</option><option>WA</option><option>WV</option><option>WI</option><option>WY</option></select></div>
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
<script>
const SQUARE_PAYMENT_LINK=\"{SQUARE_PAYMENT_LINK}\";
const W=[];
{p_scripts}
const PRODUCTS=W.flat();
const PS=40;
let fil=[],pg=1,DESCS=null,descLoading=false,pendingIdx=null,openProduct=null,CART=[];
function e(s){{return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");}}
function fmt(n){{return"$"+parseFloat(n).toFixed(2);}}
function onF(){{pg=1;aF();}}
function aF(){{
  const q=document.getElementById("q").value.toLowerCase();
  const br=document.getElementById("bs").value;
  const so=document.getElementById("ss").value;
  fil=PRODUCTS.filter(p=>(!q||p.n.toLowerCase().includes(q)||p.b.toLowerCase().includes(q)||p.c.toLowerCase().includes(q))&&(!br||p.b===br));
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
    const ih=img?`<img src="${{e(img)}}" alt="" loading="lazy" onerror="this.parentElement.innerHTML='<div class=\\"ni\\">🚗</div>'">`:"<div class='ni'>🚗</div>";
    const ic=p.imgs&&p.imgs.length>1?`<span class="ic">📷 ${{p.imgs.length}}</span>`:"";
    const inCart=isInCart(p.c);
    return `<div class="card" onclick="openM(${{idx}})"><div class="iw">${{ih}}<span class="bt">${{e(p.b)}}</span>${{ic}}<span class="in-cart-flag${{inCart?" show":""}}" id="flag-${{e(p.c)}}">✓ In Cart</span></div><div class="cb"><div class="ct">${{e(p.n)}}</div><div class="sku-row"><span class="sku-label">SKU#</span><span class="sku-val">${{e(p.c)}}</span></div><div class="price-row"><span class="pr">${{p.p?"$"+p.p:"—"}}</span></div><button class="add-btn${{inCart?" added":""}}" id="addbtn-${{e(p.c)}}" onclick="event.stopPropagation();toggleCart(${{idx}})">${{inCart?"✓ In Cart":"+ Add to Cart"}}</button></div></div>`;
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
function updateCartUI(){{
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
  el.innerHTML=CART.map(p=>`<div class="os-row"><span class="os-name">${{e(p.n)}}</span><span style="white-space:nowrap;">×${{p.qty}} ${{fmt(parseFloat(p.p)*p.qty)}}</span></div>`).join("")+`<div class="os-row total"><span>Total</span><span>${{fmt(cartTotal())}}</span></div>`;
}}
function switchTab(tab){{
  ["cart","checkout"].forEach(t=>{{document.getElementById("tab-"+t).classList.toggle("on",t===tab);document.getElementById("panel-"+t).classList.toggle("on",t===tab);}});
  if(tab==="checkout")renderOrderSummary();
}}
function placeOrder(){{
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
  const note=`${{fname}} ${{lname}} | ${{email}} | ${{phone}} | ${{addr1}}${{addr2?" "+addr2:""}}, ${{city}} ${{state}} ${{zip}} | `+CART.map(p=>`${{p.n}} SKU#${{p.c}} x${{p.qty}} @$${{p.p}}`).join(" | ")+` | TOTAL: ${{fmt(cartTotal())}}`;
  window.open(SQUARE_PAYMENT_LINK+"?note="+encodeURIComponent(note.substring(0,500)),"_blank");
  document.getElementById("success-overlay").classList.add("show");
  closeDrawer();CART=[];updateCartUI();
  document.querySelectorAll(".add-btn").forEach(b=>{{b.textContent="+ Add to Cart";b.classList.remove("added");}});
  document.querySelectorAll(".in-cart-flag").forEach(f=>f.classList.remove("show"));
  if(openProduct)syncModalBtn();
}}
function syncModalBtn(){{const btn=document.getElementById("m-add-btn");if(!openProduct)return;if(isInCart(openProduct.c)){{btn.textContent="✓ In Cart";btn.classList.add("added");}}else{{btn.textContent="+ Add to Cart";btn.classList.remove("added");}}}}
function addFromModal(){{if(!openProduct)return;isInCart(openProduct.c)?removeFromCart(openProduct.c):addToCart(openProduct);syncModalBtn();}}
function openM(idx){{
  const p=fil[idx];if(!p)return;openProduct=p;pendingIdx=PRODUCTS.indexOf(p);
  document.getElementById("msk").textContent="SKU# "+p.c;document.getElementById("mbrand").textContent=p.b;
  document.getElementById("mtitle").textContent=p.n;document.getElementById("mprice").textContent=p.p?"$"+p.p:"—";
  document.getElementById("mdesc").innerHTML="<span class='dload'>Loading description…</span>";syncModalBtn();
  const imgs=p.imgs||[];const gm=document.getElementById("gmain");const gt=document.getElementById("gthumbs");
  if(imgs.length){{gm.src=imgs[0];gm.style.display="block";if(imgs.length>1){{gt.style.display="flex";gt.innerHTML=imgs.map((s,i)=>`<img class="gthumb ${{i===0?"on":""}}" src="${{e(s)}}" onclick="setImg(this,'${{e(s)}}')" loading="lazy">`).join("");}}else{{gt.style.display="none";}}}}else{{gm.style.display="none";gt.style.display="none";}}
  document.getElementById("mbg").classList.add("open");document.body.style.overflow="hidden";loadDescs();
}}
function loadDescs(){{if(DESCS){{showDesc();return;}}if(descLoading)return;descLoading=true;fetch("descs.json").then(r=>r.json()).then(d=>{{DESCS=d;showDesc();}}).catch(()=>{{document.getElementById("mdesc").innerHTML="<span class='dload'>Description unavailable.</span>";}});}}
function showDesc(){{if(pendingIdx===null||!DESCS)return;const d=DESCS[pendingIdx]||"";document.getElementById("mdesc").innerHTML=d?`<div>${{d}}</div>`:"<span class='dload'>No description available.</span>";}}
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
  fil=[...PRODUCTS];aF();updateCartUI();
  document.getElementById("loader").style.display="none";
}},50);
</script>
</body>
</html>"""

with open("index.html","w",encoding="utf-8") as f:
    f.write(html_out)
print(f"Built index.html ({os.path.getsize('index.html')//1024}KB) — {total} products, {len(brands)} brands")
