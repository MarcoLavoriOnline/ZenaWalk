#!/usr/bin/env python3
"""
Genera le pagine statiche /itinerari/{id}.html — landing SEO leggere,
non più cloni da 236KB dell'app intera.

Perché esiste questo script:
Prima, ogni pagina itinerario era una copia integrale di index.html (~236KB),
identica per il 99% tra un itinerario e l'altro — solo <title>/<meta> cambiavano.
Google la vedeva come contenuto duplicato e non la indicizzava.
Ora ogni pagina ha SOLO head (title/meta/canonical/OG/JSON-LD) + un corpo HTML
reale, statico, leggibile senza eseguire JavaScript — la vera descrizione,
cosa include, cosa aspettarsi, i luoghi toccati. Il bottone porta all'app vera
tramite /app/itinerari/{id}, che carica index.html interattivo (mappa, player,
audio) e poi ripulisce l'URL in /itinerari/{id} per i link condivisi.

Uso: python3 generate_seo_pages.py
Legge da data/catalog.json + data/{id}.json, scrive in itinerari/{id}.html
Rigenerare ogni volta che cambia un testo in un itinerario o nel configuratore.
"""
import json
import html
import os
import re

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT, 'data')
OUT_DIR = os.path.join(ROOT, 'itinerari')

# Itinerari con pagina pubblica indicizzabile — whitelist esplicita, non
# generiamo pagine per tutto ciò che appare in catalog.json (es. eventi ad
# accesso privato via codice, come "forchette-foreste", restano fuori: sono
# pensati per QR/link diretto, non per la ricerca organica).
LIVE_IDS = [
    'genova-essenziale', 'genoa-cfc', 'i-forti-di-genova',
    'mangia-come-un-genovese', 'la-storia-di-de-andre', 'genova-misteriosa',
    'genoa-e-samp-rivalita-calcistica', 'levante-coast-to-coast',
    'nervi-parchi-e-scogliere', 'tra-moli-e-lanterna',
]

BASE_URL = 'https://zenawalk.com'


def esc(s):
    return html.escape(s or '', quote=True)


def teaser_list_items(raw):
    """teaser_include arriva come stringa con \n tra le voci."""
    if not raw:
        return []
    return [line.strip() for line in raw.split('\n') if line.strip()]


def tappe_names(itin):
    names = []
    for t in itin.get('tappe', []):
        n = (t.get('nome') or '').strip()
        if n and n.lower() != 'introduzione':
            names.append(n)
    return names


def price_line(entry):
    if entry.get('accesso') == 'free':
        return 'Gratuito'
    prezzo = entry.get('prezzo')
    if prezzo:
        return f'€ {prezzo:.2f}'.replace('.', ',')
    return 'Premium'


def render_page(entry, itin):
    id_ = entry['id']
    titolo = entry['titolo']
    tema = entry.get('tema') or ''
    descrizione = entry.get('descrizione') or ''
    is_coming_soon = entry.get('stato') == 'coming_soon'

    title_tag = f"{titolo} — Tour a piedi Genova | ZenaWalk"
    meta_desc = (descrizione[:157] + '…') if len(descrizione) > 160 else descrizione
    canonical = f"{BASE_URL}/itinerari/{id_}"
    img = entry.get('img_card') or ''

    include_items = teaser_list_items(entry.get('teaser_include'))
    aspettarsi = entry.get('teaser_aspettarsi') or ''
    accessibilita = entry.get('teaser_accessibilita') or ''
    luoghi = tappe_names(itin)
    durata = entry.get('durata') or ''
    distanza = entry.get('distanza') or ''
    difficolta = entry.get('difficolta') or ''
    prezzo_label = price_line(entry)

    jsonld_product = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": titolo,
        "description": descrizione or meta_desc,
        "image": img or None,
        "brand": {"@type": "Brand", "name": "ZenaWalk"},
        "offers": {
            "@type": "Offer",
            "price": "0" if entry.get('accesso') == 'free' else str(entry.get('prezzo') or ''),
            "priceCurrency": "EUR",
            "availability": "https://schema.org/InStock"
        }
    }
    jsonld_product = {k: v for k, v in jsonld_product.items() if v is not None}

    # TouristTrip — dice a Google che questa non è una pagina prodotto
    # generica ma un percorso reale con tappe, luogo e durata. Solo per gli
    # itinerari con tappe vere (i coming_soon non ne hanno ancora — meglio
    # ometterlo che dichiarare un itinerario che di fatto non esiste).
    jsonld_trip = None
    if luoghi:
        jsonld_trip = {
            "@context": "https://schema.org",
            "@type": "TouristTrip",
            "name": titolo,
            "description": descrizione or meta_desc,
            "touristType": "Walking tour",
            "itinerary": {
                "@type": "ItemList",
                "itemListElement": [
                    {"@type": "ListItem", "position": i + 1,
                     "item": {"@type": "TouristAttraction", "name": nome, "address": "Genova, Italia"}}
                    for i, nome in enumerate(luoghi)
                ]
            }
        }
        if durata:
            jsonld_trip["duration"] = durata
        if img:
            jsonld_trip["image"] = img

    cta_label = "Ascolta con Cristoforo" if not is_coming_soon else "Scopri di più"
    status_badge = "In arrivo" if is_coming_soon else ("Gratuito" if entry.get('accesso') == 'free' else prezzo_label)

    meta_bits = []
    if durata:
        meta_bits.append(f'<span>{esc(durata)}</span>')
    if distanza:
        meta_bits.append(f'<span>{esc(distanza)}</span>')
    if difficolta:
        meta_bits.append(f'<span>{esc(difficolta.capitalize())}</span>')
    meta_row = '<span class="dot">·</span>'.join(meta_bits)

    include_html = ''
    if include_items:
        lis = ''.join(f'<li>{esc(i)}</li>' for i in include_items)
        include_html = f'<h2>Cosa include</h2><ul class="checklist">{lis}</ul>'

    aspettarsi_html = f'<h2>Cosa aspettarti</h2><p>{esc(aspettarsi)}</p>' if aspettarsi else ''

    luoghi_html = ''
    if luoghi:
        chips = ''.join(f'<li>{esc(l)}</li>' for l in luoghi)
        luoghi_html = f'<h2>I luoghi che attraverserai</h2><ul class="chips">{chips}</ul>'

    accessibilita_html = f'<p class="access-note">{esc(accessibilita)}</p>' if accessibilita else ''

    hero_style = f'background-image:url(\'{esc(img)}\')' if img else ''

    return f'''<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="theme-color" content="#1A1714">
<title>{esc(title_tag)}</title>
<meta name="description" content="{esc(meta_desc)}">
<link rel="canonical" href="{canonical}">
<meta name="robots" content="index, follow">
<meta property="og:type" content="website">
<meta property="og:title" content="{esc(title_tag)}">
<meta property="og:description" content="{esc(meta_desc)}">
<meta property="og:url" content="{canonical}">
{f'<meta property="og:image" content="{esc(img)}">' if img else ''}
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{esc(title_tag)}">
<meta name="twitter:description" content="{esc(meta_desc)}">
{f'<meta name="twitter:image" content="{esc(img)}">' if img else ''}
<link rel="manifest" href="/manifest.json">
<link rel="apple-touch-icon" href="/icon-180.png">
<link rel="icon" href="/icon-192.png" type="image/png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,300;0,9..144,600;1,9..144,300&family=DM+Sans:wght@300;400;500&display=swap" rel="stylesheet">
<script type="application/ld+json">{json.dumps(jsonld_product, ensure_ascii=False)}</script>
{f'<script type="application/ld+json">{json.dumps(jsonld_trip, ensure_ascii=False)}</script>' if jsonld_trip else ''}
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
:root{{--gold:#C49A3C;--gold-dim:#8A6B28;--ink:#1A1714;--paper:#F4EFE4;--white:#FFFFFF;--stone:#5C4E39;--mist:#E0D9CE}}
html,body{{background:var(--ink);color:var(--paper);font-family:'DM Sans',sans-serif;font-weight:300;line-height:1.6}}
.wrap{{max-width:640px;margin:0 auto;padding:0 20px 60px}}
.top{{padding:20px 0}}
.top a{{color:var(--gold);text-decoration:none;font-size:.9rem}}
.hero{{height:46vh;min-height:280px;background-size:cover;background-position:center;border-radius:14px;position:relative;margin-bottom:24px}}
.hero::after{{content:'';position:absolute;inset:0;background:linear-gradient(180deg,rgba(26,23,20,0) 40%,rgba(26,23,20,.85) 100%);border-radius:14px}}
.badge{{position:absolute;top:16px;right:16px;background:var(--gold);color:var(--ink);font-size:.75rem;font-weight:600;padding:6px 12px;border-radius:20px;z-index:2}}
h1{{font-family:'Fraunces',serif;font-weight:600;font-size:clamp(1.8rem,6vw,2.6rem);line-height:1.15;margin-bottom:8px}}
.tema{{color:var(--gold);font-size:1rem;font-style:italic;margin-bottom:20px}}
.meta-row{{display:flex;gap:10px;align-items:center;color:var(--stone);color:rgba(244,239,228,.65);font-size:.9rem;margin-bottom:24px}}
.dot{{opacity:.5}}
p{{color:rgba(244,239,228,.85);margin-bottom:14px}}
h2{{font-family:'Fraunces',serif;font-weight:600;font-size:1.3rem;margin:32px 0 12px;color:var(--paper)}}
.checklist{{list-style:none}}
.checklist li{{padding:8px 0 8px 28px;position:relative;border-bottom:.5px solid rgba(224,217,206,.15);color:rgba(244,239,228,.85)}}
.checklist li::before{{content:'✓';position:absolute;left:0;color:var(--gold)}}
.chips{{list-style:none;display:flex;flex-wrap:wrap;gap:8px}}
.chips li{{background:rgba(196,154,60,.12);border:.5px solid rgba(196,154,60,.35);color:var(--gold);font-size:.85rem;padding:6px 12px;border-radius:20px}}
.access-note{{font-size:.85rem;color:rgba(244,239,228,.6);margin-top:8px}}
.cta{{display:block;text-align:center;background:var(--gold);color:var(--ink);font-weight:600;text-decoration:none;padding:18px;border-radius:12px;margin-top:36px;font-size:1.05rem;min-height:44px}}
.cta:active{{background:#D4A84B}}
footer{{margin-top:40px;padding-top:20px;border-top:.5px solid rgba(224,217,206,.15);font-size:.8rem;color:rgba(244,239,228,.5)}}
footer a{{color:rgba(244,239,228,.5)}}
</style>
</head>
<body>
<div class="wrap">
<div class="top"><a href="/">← ZenaWalk</a></div>
<div class="hero" style="{hero_style}"><span class="badge">{esc(status_badge)}</span></div>
<h1>{esc(titolo)}</h1>
{f'<p class="tema">{esc(tema)}</p>' if tema else ''}
{f'<div class="meta-row">{meta_row}</div>' if meta_row else ''}
<p>{esc(descrizione)}</p>
{aspettarsi_html}
{include_html}
{luoghi_html}
{accessibilita_html}
<a class="cta" href="/app/itinerari/{id_}">{esc(cta_label)}</a>
<footer>
<p>ZenaWalk — Tour a piedi a Genova, la voce di Cristoforo che ti porta dove le guide non arrivano.</p>
<p><a href="/privacy.html">Privacy</a> · <a href="/termini.html">Termini</a></p>
</footer>
</div>
</body>
</html>
'''


def main():
    catalog = json.load(open(os.path.join(DATA_DIR, 'catalog.json'), encoding='utf-8'))
    by_id = {e['id']: e for e in catalog}
    os.makedirs(OUT_DIR, exist_ok=True)
    for id_ in LIVE_IDS:
        entry = by_id.get(id_)
        if not entry:
            print(f'  SALTATO {id_}: non trovato in catalog.json')
            continue
        itin_path = os.path.join(DATA_DIR, f'{id_}.json')
        if not os.path.exists(itin_path):
            print(f'  SALTATO {id_}: manca data/{id_}.json')
            continue
        itin = json.load(open(itin_path, encoding='utf-8'))
        page = render_page(entry, itin)
        out_path = os.path.join(OUT_DIR, f'{id_}.html')
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(page)
        print(f'  OK {id_}.html ({len(page.encode("utf-8"))} byte)')


if __name__ == '__main__':
    main()
