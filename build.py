#!/usr/bin/env python3
"""Staatilise saidi generaator: pühad + päevaloendurid.

Kasutus:
    python build.py            # kasutab data/ vahemälu, laeb puuduva API-st
    python build.py --refresh  # laeb pühade andmed uuesti
Keskkonnamuutujad: SITE_URL, SITE_NAME
"""
import datetime as dt
import html
import json
import os
import re
import shutil
import sys
import time
import unicodedata
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

import content as TXT

ROOT = Path(__file__).parent
DATA = ROOT / "data"
DIST = ROOT / "dist"
ASSETS = ROOT / "assets"

SITE_NAME = (os.environ.get("SITE_NAME") or "HolidayLeft")
SITE_URL = (os.environ.get("SITE_URL") or "https://holidayleft.com").rstrip("/")
API = "https://date.nager.at/api/v3"
REFRESH = "--refresh" in sys.argv
# Contact form: Web3Forms public access key (safe to keep in the repo) and/or a visible contact address.
CONTACT_KEY = os.environ.get("CONTACT_KEY") or "f2e221ad-2414-4d34-b5ba-c0ae5ff9285b"  # Web3Forms public access key
CONTACT_EMAIL = os.environ.get("CONTACT_EMAIL") or "hello@holidayleft.com"
OWNER = os.environ.get("OWNER") or "3Sped OÜ"
GA_ID = os.environ.get("GA_ID") or "G-638VP6DVLH"   # Google Analytics 4 measurement ID (loaded only after consent)
CONTACT_ON = bool(CONTACT_KEY or CONTACT_EMAIL)

NOW_UTC = dt.datetime.now(dt.timezone.utc)
YEAR = NOW_UTC.year
YEARS = [YEAR, YEAR + 1]
WD = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]

pages = {}  # path -> html


# ---------------------------------------------------------------- utils
def slugify(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = s.lower().replace("'", "")
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def esc(s):
    return html.escape(str(s), quote=True)


def flag(cc, big=False):
    cls = "fl fl-lg" if big else "fl"
    w, h = (48, 36) if big else (24, 18)
    return f'<img class="{cls}" src="/flags/{cc.lower()}.svg" alt="" width="{w}" height="{h}" loading="lazy">'


EMOJI = {
    "christmas": "🎄", "christmas-eve": "🎁", "new-years-eve": "🥂", "new-years-day": "🎆",
    "valentines-day": "💝", "st-patricks-day": "🍀", "easter": "🐣", "good-friday": "✝️",
    "easter-monday": "🌷", "april-fools-day": "🃏", "earth-day": "🌍", "mothers-day-us": "💐",
    "fathers-day-us": "👔", "memorial-day": "🎖️", "independence-day-us": "🎇", "labor-day-us": "🛠️",
    "halloween": "🎃", "thanksgiving-us": "🦃", "black-friday": "🛍️", "cyber-monday": "💻",
    "summer-solstice": "☀️", "winter-solstice": "❄️",
}
NAMED_DATES = {}
COUNTRIES = []
HOLIDAY_INDEX = {}   # holiday-name slug -> [(country, record), ...] (nationwide public holidays only)
REGION_OF = {}       # cc -> region name
REGION_SLUG = {"Europe": "europe", "Americas": "americas", "Asia": "asia", "Africa": "africa", "Oceania": "oceania"}
_REGION_OVERRIDE = {"BM": "Americas", "CV": "Africa", "FK": "Americas", "FO": "Europe", "IS": "Europe", "SH": "Africa",
                    "CC": "Asia", "CX": "Asia", "KM": "Africa", "MG": "Africa", "SC": "Africa", "SJ": "Europe",
                    "CY": "Europe", "MU": "Africa", "MV": "Asia", "YT": "Africa", "RE": "Africa"}


def region_for(c):
    if c["cc"] in _REGION_OVERRIDE:
        return _REGION_OVERRIDE[c["cc"]]
    pre = c["tz"].split("/")[0]
    return {"Europe": "Europe", "America": "Americas", "Asia": "Asia", "Africa": "Africa",
            "Australia": "Oceania", "Pacific": "Oceania"}.get(pre, "Asia")


def fit_title(long, short, limit=66):
    if len(long) <= limit:
        return long
    if len(short) <= limit:
        return short
    return short[:limit - 1].rstrip() + "…"


def email_link(addr):
    """E-mail shown as text for scrapers; a script turns it into a mailto link in the browser."""
    u, d = addr.split("@", 1)
    return (f'<span class="eml" data-u="{esc(u)}" data-d="{esc(d)}">'
            f'{esc(u)} [at] {esc(d.replace(".", " [dot] "))}</span>')


def faq_html(items, heading="Frequently asked questions"):
    out = "".join(f"<h3>{esc(q)}</h3><p>{a}</p>" for q, a in items)
    return f'<section class="faq"><h2>{esc(heading)}</h2>{out}</section>'


def cname_links(pairs, limit=40):
    """pairs: [(country, record)] -> comma separated links (names) with a '+N more' tail."""
    shown = pairs[:limit]
    txt = ", ".join(f'<a href="/holidays/{c["slug"]}/">{esc(c["name"])}</a>' for c, _ in shown)
    if len(pairs) > limit:
        txt += f" and {len(pairs) - limit} more"
    return txt


def fmt_date(d, weekday=True):
    s = f"{d.day} {MONTHS[d.month - 1]} {d.year}"
    return f"{WD[d.weekday()]}, {s}" if weekday else s


def plural(n, w):
    if n == 1:
        return f"{n} {w}"
    if w.endswith("y") and w[-2:-1] not in "aeiou":
        return f"{n} {w[:-1]}ies"
    return f"{n} {w}s"


def get_json(url):
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "nextholiday-builder"})
            with urllib.request.urlopen(req, timeout=30) as r:
                body = r.read()
                return json.loads(body) if body else []
        except Exception as e:  # noqa: BLE001
            if attempt == 3:
                print("FAIL", url, e)
                return None
            time.sleep(1.5 * (attempt + 1))


def cached(name, url):
    f = DATA / name
    if f.exists() and not REFRESH:
        return json.loads(f.read_text(encoding="utf8"))
    data = get_json(url)
    if data is None:
        if f.exists():
            return json.loads(f.read_text(encoding="utf8"))
        return None
    f.write_text(json.dumps(data, ensure_ascii=False), encoding="utf8")
    return data


def country_tz():
    f = DATA / "country_tz.json"
    if f.exists():
        return json.loads(f.read_text(encoding="utf8"))
    import tzdata  # noqa: PLC0415
    tab = Path(tzdata.__file__).parent / "zoneinfo" / "zone.tab"
    out = {}
    for line in tab.read_text(encoding="utf8").splitlines():
        if line.startswith("#") or not line.strip():
            continue
        cols = line.split("\t")
        out.setdefault(cols[0], cols[2])
    f.write_text(json.dumps(out), encoding="utf8")
    return out


# ---------------------------------------------------------------- layout
LOGO = ('<svg viewBox="0 0 32 32" aria-hidden="true"><rect width="32" height="32" rx="9" fill="#0b6b57"/>'
        '<rect x="6" y="9" width="20" height="17" rx="3" fill="#fff"/><rect x="6" y="9" width="20" height="5" rx="2" fill="#e8962b"/>'
        '<rect x="10" y="5" width="2.5" height="6" rx="1.2" fill="#fff"/><rect x="19.5" y="5" width="2.5" height="6" rx="1.2" fill="#fff"/>'
        '<path d="M11 20l3.2 3L21 17" stroke="#0b6b57" stroke-width="2.4" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>')


def ld_json(path, crumbs):
    graph = []
    if path == "/":
        graph.append({"@context": "https://schema.org", "@type": "WebSite", "name": SITE_NAME,
                      "url": SITE_URL + "/", "inLanguage": "en"})
    if crumbs:
        graph.append({"@context": "https://schema.org", "@type": "BreadcrumbList",
                      "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": t, "item": SITE_URL + u}
                                          for i, (t, u) in enumerate(crumbs)]})
    return "".join('<script type="application/ld+json">' + json.dumps(g, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/") + "</script>"
                   for g in graph)


def layout(path, title, desc, body, data=None, crumbs=None):
    if len(desc) > 160:
        desc = desc[:157].rstrip() + "…"
    CONTACT_LINK = '<br><a href="/contact/">Contact</a>' if CONTACT_ON else ""
    canon = f"{SITE_URL}{path}"
    crumb_html = ""
    if crumbs:
        crumb_html = '<div class="crumbs">' + " › ".join(
            f'<a href="{esc(u)}">{esc(t)}</a>' for t, u in crumbs) + "</div>"
    data_html = ""
    if data is not None:
        data_html = ('<script id="d" type="application/json">'
                     + json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
                     + "</script>")
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{esc(canon)}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:type" content="website">
<meta property="og:url" content="{esc(canon)}">
<meta property="og:site_name" content="{esc(SITE_NAME)}">
<meta property="og:locale" content="en_US">
<meta property="og:image" content="{SITE_URL}/og-image.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{esc(title)}">
<meta name="twitter:description" content="{esc(desc)}">
<meta name="twitter:image" content="{SITE_URL}/og-image.png">
{ld_json(path, crumbs)}
<meta name="theme-color" content="#0b6b57">
<meta name="msvalidate.01" content="07E77E2420E74B43C4CA521A5BFFC0DF">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="icon" href="/favicon.ico" sizes="48x48">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<script>try{{var t=localStorage.getItem("theme");if(t)document.documentElement.setAttribute("data-theme",t)}}catch(e){{}}</script>
<link rel="stylesheet" href="/s.css">
</head>
<body data-ga="{esc(GA_ID)}">
<header class="site"><div class="hd">
<a class="logo" href="/">{LOGO}{esc(SITE_NAME)}</a>
<nav><a href="/holidays/">Countries</a><a class="hide-s" href="/regions/">Regions</a><a class="hide-s" href="/holidays/world/">By month</a><a class="hide-s" href="/days-until/">Days until</a>
<button id="theme" type="button" aria-label="Switch between light and dark mode" title="Light / dark"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="9"/><path d="M12 3a9 9 0 0 1 0 18z" fill="currentColor"/></svg></button></nav>
</div></header>
<main>
{crumb_html}
{body}
</main>
<footer>
<div class="fl-row"><div style="max-width:560px"><p><strong>{esc(SITE_NAME)}</strong><br>Public holiday data from <a href="https://date.nager.at" rel="noopener">Nager.Date</a>, refreshed daily. Dates can change at short notice, so check official government sources before you plan travel or business around them.</p></div>
<p><a href="/holidays/">Countries</a><br><a href="/regions/">Regions</a><br><a href="/holidays/world/">Holidays by month</a><br><a href="/days-until/">Days until</a><br><a href="/faq/">FAQ</a><br><a href="/methodology/">How it works</a><br><a href="/about/">About</a>{CONTACT_LINK}<br><a href="/terms/">Terms</a><br><a href="/privacy/">Privacy</a><br><a href="#" id="cc-open">Cookie settings</a></p></div>
<p>© {YEAR} {esc(SITE_NAME)} · operated by {esc(OWNER)}</p>
</footer>
<div id="cc" class="cc" role="dialog" aria-live="polite" aria-label="Cookie choices" hidden>
<p><strong>Cookies?</strong> With your OK we use Google Analytics cookies to see which pages are used. No ads and no profiles. You can change your mind at any time under <em>Cookie settings</em> in the footer. <a href="/privacy/">Privacy policy</a></p>
<div class="cc-b"><button type="button" id="cc-no">Decline</button><button type="button" id="cc-yes">Accept</button></div>
</div>
{data_html}
<script src="/s.js" defer></script>
</body>
</html>
"""


def add(path, html_text):
    pages[path] = html_text


# ---------------------------------------------------------------- date rules (global countdowns)
def nth_weekday(y, m, wd, n):
    first = dt.date(y, m, 1)
    return first + dt.timedelta(days=(wd - first.weekday()) % 7 + 7 * (n - 1))


def last_weekday(y, m, wd):
    last = dt.date(y, 12, 31) if m == 12 else dt.date(y, m + 1, 1) - dt.timedelta(days=1)
    return last - dt.timedelta(days=(last.weekday() - wd) % 7)


def easter(y):
    a = y % 19
    b, c = divmod(y, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return dt.date(y, month, day + 1)


NAMED = [
    ("christmas", "Christmas", lambda y: dt.date(y, 12, 25), "Christmas Day is celebrated on 25 December in most countries."),
    ("christmas-eve", "Christmas Eve", lambda y: dt.date(y, 12, 24), "Christmas Eve is 24 December, the main gift-giving day in many countries."),
    ("new-years-eve", "New Year's Eve", lambda y: dt.date(y, 12, 31), "New Year's Eve is the last day of the year, 31 December."),
    ("new-years-day", "New Year's Day", lambda y: dt.date(y, 1, 1), "New Year's Day is 1 January and a public holiday almost everywhere."),
    ("valentines-day", "Valentine's Day", lambda y: dt.date(y, 2, 14), "Valentine's Day is celebrated on 14 February."),
    ("st-patricks-day", "St. Patrick's Day", lambda y: dt.date(y, 3, 17), "St. Patrick's Day is on 17 March."),
    ("easter", "Easter Sunday", easter, "Easter Sunday (Western churches) moves every year. It falls on the first Sunday after the first full moon after the spring equinox."),
    ("good-friday", "Good Friday", lambda y: easter(y) - dt.timedelta(days=2), "Good Friday is the Friday before Easter Sunday and a public holiday in many countries."),
    ("easter-monday", "Easter Monday", lambda y: easter(y) + dt.timedelta(days=1), "Easter Monday is the day after Easter Sunday and a public holiday in many countries."),
    ("april-fools-day", "April Fools' Day", lambda y: dt.date(y, 4, 1), "April Fools' Day is on 1 April."),
    ("earth-day", "Earth Day", lambda y: dt.date(y, 4, 22), "Earth Day is on 22 April."),
    ("mothers-day-us", "Mother's Day (US)", lambda y: nth_weekday(y, 5, 6, 2), "Mother's Day in the US and several other countries is the second Sunday of May."),
    ("fathers-day-us", "Father's Day (US)", lambda y: nth_weekday(y, 6, 6, 3), "Father's Day in the US, UK and many other countries is the third Sunday of June."),
    ("memorial-day", "Memorial Day (US)", lambda y: last_weekday(y, 5, 0), "Memorial Day is the last Monday of May."),
    ("independence-day-us", "Independence Day (US)", lambda y: dt.date(y, 7, 4), "Independence Day in the United States is on 4 July."),
    ("labor-day-us", "Labor Day (US)", lambda y: nth_weekday(y, 9, 0, 1), "Labor Day in the US is the first Monday of September."),
    ("halloween", "Halloween", lambda y: dt.date(y, 10, 31), "Halloween is on 31 October."),
    ("thanksgiving-us", "Thanksgiving (US)", lambda y: nth_weekday(y, 11, 3, 4), "US Thanksgiving is the fourth Thursday of November."),
    ("black-friday", "Black Friday", lambda y: nth_weekday(y, 11, 3, 4) + dt.timedelta(days=1), "Black Friday is the day after US Thanksgiving."),
    ("cyber-monday", "Cyber Monday", lambda y: nth_weekday(y, 11, 3, 4) + dt.timedelta(days=4), "Cyber Monday is the Monday after US Thanksgiving."),
    ("summer-solstice", "Summer Solstice (northern hemisphere)", lambda y: dt.date(y, 6, 21), "The June solstice is around 21 June, the longest day in the northern hemisphere."),
    ("winter-solstice", "Winter Solstice (northern hemisphere)", lambda y: dt.date(y, 12, 21), "The December solstice is around 21 December, the shortest day in the northern hemisphere."),
]


def next_on_or_after(dates, d):
    for x in dates:
        if x >= d:
            return x
    return None


def until_block(days, when, extra=""):
    unit = "day" if days == 1 else "days"
    return f"""<div class="cd">
<div class="big"><span id="days">{days}</span><small id="unit">{unit}</small></div>
<div class="cd-info"><strong id="when">{esc(when)}</strong><span class="mut" id="wk">{extra}</span></div>
</div>"""


def wk_text(days):
    if days == 0:
        return "That is today!"
    if days < 7:
        return ""
    w, r = divmod(days, 7)
    return f"That is {plural(w, 'week')}" + (f" and {plural(r, 'day')}" if r else "") + "."


# ---------------------------------------------------------------- load data
def load_countries():
    DATA.mkdir(exist_ok=True)
    cs = cached("countries.json", f"{API}/AvailableCountries")
    if not cs:
        sys.exit("Country list unavailable")
    tzs = country_tz()
    out = []
    for c in cs:
        cc = c["countryCode"]
        hols = {}
        ok = False
        for y in YEARS:
            data = cached(f"h_{cc}_{y}.json", f"{API}/PublicHolidays/{y}/{cc}")
            if data:
                ok = True
                hols[y] = data
        if not ok:
            continue
        pub, other = [], []
        for y in YEARS:
            for h in hols.get(y, []):
                rec = {
                    "date": dt.date.fromisoformat(h["date"]),
                    "name": h["name"],
                    "local": h.get("localName") or h["name"],
                    "global": bool(h.get("global", True)),
                    "counties": h.get("counties") or [],
                }
                (pub if "Public" in (h.get("types") or []) else other).append(rec)
        if not pub:
            continue
        pub.sort(key=lambda r: r["date"])
        other.sort(key=lambda r: r["date"])
        out.append({
            "cc": cc, "name": c["name"], "slug": slugify(c["name"]),
            "tz": tzs.get(cc, "UTC"), "pub": pub, "other": other,
        })
    out.sort(key=lambda c: c["name"])
    return out


def headline(c):
    """Records used for 'next holiday' headlines: nationwide ones when the country has any."""
    g = [r for r in c["pub"] if r["global"]]
    return g or c["pub"]


def country_today(c):
    try:
        return dt.datetime.now(ZoneInfo(c["tz"])).date()
    except Exception:  # noqa: BLE001
        return NOW_UTC.date()


# ---------------------------------------------------------------- page builders
def country_nav(c):
    s = c["slug"]
    return (f'<p><a href="/is-today-a-holiday-in-{s}/">Is today a holiday in {esc(c["name"])}?</a> · '
            f'<a href="/is-tomorrow-a-holiday-in-{s}/">Is tomorrow a holiday?</a> · '
            f'<a href="/holidays/{s}/">All public holidays</a></p>')


def scope_pill(r):
    if r["global"]:
        return '<span class="pill">Nationwide</span>'
    cs = ", ".join(r["counties"][:6]) + ("…" if len(r["counties"]) > 6 else "")
    return f'<span class="pill reg">Some regions{(": " + esc(cs)) if cs else ""}</span>'


def holiday_slugs(c):
    """slug -> list of records (unique names per country)"""
    m = {}
    for r in c["pub"]:
        m.setdefault(slugify(r["name"]), []).append(r)
    return m


def build_country(c, all_countries):
    s, name = c["slug"], c["name"]
    today = country_today(c)
    upcoming = [r for r in headline(c) if r["date"] >= today]
    nxt = upcoming[0] if upcoming else None
    slugs = holiday_slugs(c)

    parts = [f'<div class="pagehead">{flag(c["cc"], True)}<h1>Public holidays in {esc(name)} {YEAR}</h1></div>',
             f'<p class="mut" style="margin-top:-6px">Data updated {esc(fmt_date(NOW_UTC.date()))}.</p>']
    if nxt:
        days = (nxt["date"] - today).days
        parts.append(f"""<div class="cd"><p class="lbl">Next public holiday in {esc(name)}</p>
<h2 id="nname">{esc(nxt["name"])}</h2>
<div class="big"><span id="days">{days}</span><small id="unit">{"day" if days == 1 else "days"}</small></div>
<div class="cd-info"><strong id="when">{esc(fmt_date(nxt["date"]))}</strong><span class="mut" id="wk">{wk_text(days)}</span></div></div>""")
    parts.append(country_nav(c))

    for y in YEARS:
        rows = [r for r in c["pub"] if r["date"].year == y]
        if not rows:
            continue
        tr = []
        for r in rows:
            link = esc(r["name"])
            sl = slugify(r["name"])
            if sl in slugs:
                link = f'<a href="/days-until/{s}/{sl}/">{esc(r["name"])}</a>'
            local = f'<div class="mut">{esc(r["local"])}</div>' if r["local"] != r["name"] else ""
            tr.append(f'<tr><td>{r["date"].day} {MONTHS[r["date"].month - 1][:3]}</td>'
                      f'<td>{WD[r["date"].weekday()][:3]}</td><td>{link}{local}</td><td>{scope_pill(r)}</td></tr>')
        n_nat = sum(1 for r in rows if r["global"])
        parts.append(f'<h2>{esc(name)} public holidays {y}</h2>'
                     f'<p>{esc(name)} has {n_nat} nationwide public holidays in {y}'
                     f'{"" if n_nat == len(rows) else f" and {len(rows) - n_nat} more that apply in some regions only"}.</p>'
                     f'<div class="tw"><table><tr><th>Date</th><th>Day</th><th>Holiday</th><th>Applies</th></tr>{"".join(tr)}</table></div>')
        lw = [r for r in rows if r["global"] and r["date"].weekday() in (0, 4)]
        if lw:
            items = "".join(
                f'<li>{esc(fmt_date(r["date"]))}: {esc(r["name"])} ({"Friday to Sunday" if r["date"].weekday() == 4 else "Saturday to Monday"})</li>'
                for r in lw)
            parts.append(f'<h3>Long weekends in {esc(name)} in {y}</h3><p>Nationwide holidays that fall on a Friday or Monday give a three-day weekend:</p><ul>{items}</ul>')

    if c["other"]:
        oth = [r for r in c["other"] if r["date"].year == YEAR]
        if oth:
            items = "".join(f'<li>{r["date"].day} {MONTHS[r["date"].month - 1]}: {esc(r["name"])}</li>' for r in oth)
            parts.append(f'<details><summary>Other observances and bank holidays in {YEAR}</summary><ul>{items}</ul></details>')

    yr = [r for r in c["pub"] if r["date"].year == YEAR]
    nat = [r for r in yr if r["global"]]
    reg = [r for r in yr if not r["global"]]
    wk_end = [r for r in nat if r["date"].weekday() >= 5]
    wk_day = [r for r in nat if r["date"].weekday() < 5]
    by_m = {}
    for r in nat:
        by_m.setdefault(r["date"].month, []).append(r)
    busiest = max(by_m.items(), key=lambda kv: (len(kv[1]), -kv[0])) if by_m else None
    lw_all = [r for r in nat if r["date"].weekday() in (0, 4)]
    if by_m:
        li = "".join(
            f'<li><strong>{MONTHS[m - 1]}</strong>: ' + "; ".join(f'{esc(r["name"])} ({r["date"].day})' for r in rs) + "</li>"
            for m, rs in sorted(by_m.items()))
        empty = [MONTHS[m - 1] for m in range(1, 13) if m not in by_m]
        tail = (f"<p class=\"mut\">No nationwide public holidays in {', '.join(empty)}.</p>" if empty else "")
        parts.append(f"<h2>{esc(name)} public holidays by month in {YEAR}</h2><ul>{li}</ul>{tail}")
        parts.append(f"""<h2>How the holidays fall in {YEAR}</h2>
<div class="stats">
<div><b>{len(nat)}</b><span>nationwide public holidays</span></div>
<div><b>{len(wk_day)}</b><span>fall on Monday to Friday</span></div>
<div><b>{len(wk_end)}</b><span>fall on a weekend</span></div>
<div><b>{len(lw_all)}</b><span>give a long weekend</span></div>
</div>
<p>The first nationwide public holiday of {YEAR} is {esc(nat[0]["name"])} on {esc(fmt_date(nat[0]["date"]))}, and the last is {esc(nat[-1]["name"])} on {esc(fmt_date(nat[-1]["date"]))}. {MONTHS[busiest[0] - 1]} is the busiest month, with {plural(len(busiest[1]), "holiday")}. For people who work a standard Monday to Friday week, the {len(wk_day)} holidays on weekdays are the ones that usually mean a day away from work or school.</p>""")

    parts.append(f"""<h2>About public holidays in {esc(name)}</h2>
<p>This page lists the public holidays of {esc(name)} for {YEAR} and {YEAR + 1}, with the date and weekday of each one. A holiday marked <em>Nationwide</em> applies everywhere in the country. One marked <em>Some regions</em> applies only to part of it, for example a state or province. Where the official name is different from the English one, the local name appears under it.</p>
<p>Moveable holidays, such as the ones counted from Easter, change their date from year to year, so it is worth checking the table each year before you plan. Our main time zone for {esc(name)} is {esc(c["tz"])}, which is what the live countdown and the "is today a holiday" pages use.</p>""")

    faq_items = []
    faq_items.append((f"How many public holidays does {name} have in {YEAR}?",
                      f"{esc(name)} has {len(nat)} nationwide public holidays in {YEAR}"
                      + (f" and {len(reg)} more that apply in some regions only" if reg else "")
                      + ". The full list with dates and weekdays is in the table above."))
    if nxt:
        faq_items.append((f"What is the next public holiday in {name}?",
                          f"The next nationwide public holiday is {esc(nxt['name'])} on {esc(fmt_date(nxt['date']))}. The countdown at the top of this page shows the days left."))
    faq_items.append((f"Is today a public holiday in {name}?",
                      f'Use the live checker: <a href="/is-today-a-holiday-in-{s}/">is today a public holiday in {esc(name)}</a>. It works out the date in {esc(name)}\'s own time zone. You can also check <a href="/is-tomorrow-a-holiday-in-{s}/">tomorrow</a>.'))
    faq_items.append((f"Which public holidays in {name} fall on a weekend in {YEAR}?",
                      ("; ".join(f'{esc(r["name"])} ({esc(fmt_date(r["date"]))})' for r in wk_end) + ". Whether a day in lieu is given depends on local rules."
                       if wk_end else f"None of the nationwide public holidays in {YEAR} fall on a weekend.")))
    faq_items.append((f"Are there long weekends in {name} in {YEAR}?",
                      (f"Yes. {len(lw_all)} nationwide holidays fall on a Friday or a Monday: "
                       + "; ".join(f'{esc(r["name"])} ({esc(fmt_date(r["date"]))})' for r in lw_all)
                       + ". Taking a bridge day next to a holiday on a Tuesday or Thursday can also give a longer break.")
                      if lw_all else f"No nationwide holiday falls on a Friday or a Monday in {YEAR}, so there is no automatic three-day weekend. A holiday on a Tuesday or Thursday can still be turned into a longer break with a bridge day."))
    if busiest:
        faq_items.append((f"Which month has the most public holidays in {name}?",
                          f"{MONTHS[busiest[0] - 1]} has the most nationwide public holidays in {YEAR}: {plural(len(busiest[1]), 'holiday')}."))
    faq_items.append((f"Are the public holidays the same in all regions of {name}?",
                      (f"Not entirely. {len(reg)} holidays in the list apply only in some regions and are marked that way in the table. The rest apply nationwide."
                       if reg else f"The holidays listed here apply nationwide. If {esc(name)} has local or regional days off, they are not part of this list.")))
    faq_items.append(("How often is this page updated?",
                      "The whole site is rebuilt every day from the latest data, and the countdown on the page is calculated in your browser, so it stays correct without a reload."))
    reg_name = REGION_OF[c["cc"]]
    same = [x for x in COUNTRIES if REGION_OF[x["cc"]] == reg_name and x["cc"] != c["cc"]]
    if same:
        pos = sum(1 for x in same if x["name"] < name)
        rot = same[pos:] + same[:pos]
        tiles = "".join(f'<li><a href="/holidays/{x["slug"]}/">{flag(x["cc"])} {esc(x["name"])}</a></li>' for x in rot[:12])
        parts.append(f'<h2>More public holiday calendars in {esc(reg_name)}</h2><ul class="tiles">{tiles}</ul>'
                     f'<p><a href="/regions/{REGION_SLUG[reg_name]}/">All countries in {esc(reg_name)}</a></p>')
    parts.append(faq_html(faq_items))

    dates = [[r["date"].isoformat(), r["name"]] for r in headline(c)]
    title = f"Public Holidays in {name} {YEAR} and {YEAR + 1} – Dates and Countdown"
    desc = f"Full list of {name} public holidays for {YEAR} and {YEAR + 1}, long weekends, and a live countdown to the next holiday."
    add(f"/holidays/{s}/", layout(f"/holidays/{s}/", title, desc, "\n".join(parts),
                                  {"type": "country", "tz": c["tz"], "dates": dates},
                                  [("Home", "/"), (REGION_OF[c["cc"]], f"/regions/{REGION_SLUG[REGION_OF[c['cc']]]}/"), (name, f"/holidays/{s}/")]))


def upcoming_table(c, after):
    if not after:
        return ""
    rows = "".join(f'<tr><td>{esc(fmt_date(r["date"]))}</td><td>{esc(r["name"])}</td></tr>' for r in after[:6])
    return (f'<h2>Upcoming public holidays in {esc(c["name"])}</h2>'
            f'<div class="tw"><table><tr><th>Date</th><th>Holiday</th></tr>{rows}</table></div>'
            f'<p><a href="/holidays/{c["slug"]}/">See the full {esc(c["name"])} holiday calendar</a></p>')


def isday_faq(c, word, nxt):
    name, s = c["name"], c["slug"]
    n_nat = sum(1 for r in c["pub"] if r["global"] and r["date"].year == YEAR)
    other = "tomorrow" if word == "today" else "today"
    items = [
        (f"Is {word} a public holiday in {name}?",
         "The answer is at the top of this page. It is calculated from the official holiday list for the country and "
         f"the current date in {esc(c['tz'])}, so it stays correct even if you leave the page open."),
        (f"What does \"Partly\" mean?",
         "Some public holidays apply only in certain regions, states or provinces. When the date is a holiday in some regions but not in the whole country, the page shows Partly and names the holiday."),
        (f"How many public holidays does {name} have in {YEAR}?",
         f"{esc(name)} has {n_nat} nationwide public holidays in {YEAR}. See the <a href=\"/holidays/{s}/\">full list for {esc(name)}</a>."),
        (f"Are shops, banks and schools closed on public holidays in {name}?",
         "Opening rules differ by country, by type of business and sometimes by holiday. Many offices, schools and banks close on public holidays, while shops, restaurants and transport may stay open or run reduced hours. For a specific business, check its own opening hours."),
        (f"Is {other} a public holiday in {name}?",
         f'See <a href="/is-{other}-a-holiday-in-{s}/">is {other} a public holiday in {esc(name)}</a>.'),
    ]
    if nxt:
        items.append((f"When is the next public holiday in {name}?",
                      f"{esc(nxt['name'])} on {esc(fmt_date(nxt['date']))}."))
    return faq_html(items)


def build_isday(c, offset):
    s, name = c["slug"], c["name"]
    word = "today" if offset == 0 else "tomorrow"
    today = country_today(c)
    target = today + dt.timedelta(days=offset)
    hmap = {}
    for r in c["pub"]:
        key = r["date"].isoformat()
        if key not in hmap or (r["global"] and not hmap[key]["g"]):
            hmap[key] = {"n": r["name"], "g": r["global"]}
    h = hmap.get(target.isoformat())
    ans = ("Yes" if h["g"] else "Partly") if h else "No"
    cls = "yes" if h else "no"
    detail = (f'{h["n"]}{" (nationwide)" if h["g"] else " (some regions only)"}' if h
              else "No public holiday on this date.")
    after = [r for r in headline(c) if r["date"] > target]
    nxt = after[0] if after else None
    nxt_html = ""
    if nxt:
        d = (nxt["date"] - today).days
        nxt_html = f"""<div class="cd"><p class="lbl">Next public holiday in {esc(name)}</p>
<h2 id="nname">{esc(nxt["name"])}</h2>
<div class="big"><span id="ndays">{d}</span><small id="nunit">{"day" if d == 1 else "days"}</small></div>
<div class="cd-info"><strong id="nwhen">{esc(fmt_date(nxt["date"]))}</strong></div></div>"""
    other = "tomorrow" if offset == 0 else "today"
    other_path = f"/is-{other}-a-holiday-in-{s}/"
    body = f"""<div class="pagehead">{flag(c["cc"], True)}<h1>Is {word} a public holiday in {esc(name)}?</h1></div>
<div class="card answer">
<div><span class="ans {cls}" id="ans">{ans}</span></div>
<p style="margin:18px 0 0;font-size:19px"><strong id="target">{esc(fmt_date(target))}</strong></p>
<p class="mut" id="detail" style="margin:4px 0 0">{esc(detail)}</p>
</div>
{nxt_html}
<p><a href="{other_path}">Is {other} a holiday in {esc(name)}?</a> · <a href="/holidays/{s}/">All {esc(name)} public holidays {YEAR}</a></p>
<p class="mut">The answer is worked out for the date in {esc(name)}'s main time zone ({esc(c["tz"])}). "Partly" means the day is a holiday only in some regions.</p>
{upcoming_table(c, after)}
{isday_faq(c, word, nxt)}"""
    title = f"Is {word.capitalize()} a Public Holiday in {name}? ({fmt_date(target, False)})"
    desc = f"Find out right now whether {word} is a public holiday in {name}, with the next holiday and a countdown."
    path = f"/is-{word}-a-holiday-in-{s}/"
    add(path, layout(path, title, desc, body,
                     {"type": "isday", "offset": offset, "tz": c["tz"], "h": hmap,
                      "dates": [[r["date"].isoformat(), r["name"]] for r in headline(c)]},
                     [("Home", "/"), (name, f"/holidays/{s}/")]))


def holiday_extra(c, sl, recs, nxt):
    name, s = c["name"], c["slug"]
    r0 = recs[0]
    hn = r0["name"]
    items = []
    by_year = "; ".join(f'{r["date"].year}: {esc(fmt_date(r["date"]))}' for r in recs)
    items.append((f"When is {hn} in {name}?", f"{esc(hn)} falls on " + " and ".join(esc(fmt_date(r["date"])) for r in recs) + "."))
    nxt_rec = next(r for r in recs if r["date"] == nxt)
    items.append((f"Is {hn} a nationwide public holiday in {name}?",
                  f"Yes, {esc(hn)} is a public holiday across the whole country." if nxt_rec["global"]
                  else f"{esc(hn)} is a public holiday only in some regions of {esc(name)}, not in the whole country."))
    wkend = [r for r in recs if r["date"].weekday() >= 5]
    items.append((f"Does {hn} fall on a weekend?",
                  ("In " + " and ".join(f'{r["date"].year} it falls on a {WD[r["date"].weekday()]}' for r in wkend)
                   + ". Whether a day in lieu is given depends on local rules.") if wkend
                  else f"Not in the years listed: {esc(hn)} falls on a weekday in {', '.join(str(r['date'].year) for r in recs)}."))
    after = [r for r in headline(c) if r["date"] > nxt]
    if after:
        items.append((f"Which public holiday in {name} comes after {hn}?",
                      f"The next one is {esc(after[0]['name'])} on {esc(fmt_date(after[0]['date']))}."))
    items.append((f"How many days until {hn}?",
                  "The live countdown at the top of this page shows the days and weeks left. It is calculated from your device's date."))
    others = [(oc, orr) for oc, orr in HOLIDAY_INDEX.get(sl, []) if oc["cc"] != c["cc"]]
    out = ""
    if others:
        out += (f'<h2>Other countries with {esc(hn)}</h2><p>A nationwide public holiday with this name also appears in the '
                f'calendars of: {cname_links(others, 40)}.</p>')
    return out + faq_html(items)


def build_country_holiday(c):
    s, name = c["slug"], c["name"]
    today = country_today(c)
    slugs = holiday_slugs(c)
    made = []
    for sl, recs in slugs.items():
        recs.sort(key=lambda r: r["date"])
        r0 = recs[0]
        nxt = next_on_or_after([r["date"] for r in recs], today)
        if nxt is None:
            continue
        days = (nxt - today).days
        rec = next(r for r in recs if r["date"] == nxt)
        local = f' (<span lang="">{esc(r0["local"])}</span>)' if r0["local"] != r0["name"] else ""
        scope = "a nationwide public holiday" if rec["global"] else "a public holiday in some regions only"
        rows = "".join(
            f'<tr><td>{esc(fmt_date(r["date"]))}</td><td>{scope_pill(r)}</td></tr>' for r in recs)
        sibs = [x for x in slugs if x != sl][:10]
        sib_html = "".join(f'<li><a href="/days-until/{s}/{x}/">{esc(slugs[x][0]["name"])}</a></li>' for x in sibs)
        body = f"""<h1>How many days until {esc(r0["name"])} in {esc(name)}?</h1>
{until_block(days, fmt_date(nxt), wk_text(days))}
<p>{esc(r0["name"])}{local} is {scope} in {esc(name)}. In {nxt.year} it falls on a {WD[nxt.weekday()]}.</p>
<h2>{esc(r0["name"])} dates in {esc(name)}</h2>
<div class="tw"><table><tr><th>Date</th><th>Applies</th></tr>{rows}</table></div>
{holiday_extra(c, sl, recs, nxt)}
<h2>More {esc(name)} holidays</h2>
<ul class="tiles">{sib_html}</ul>
{country_nav(c)}"""
        path = f"/days-until/{s}/{sl}/"
        title = fit_title(f"{r0['name']} {nxt.year} in {name}: Date and Days Left", f"{r0['name']} in {name}: Days Left")
        desc = f"{r0['name']} in {name} is on {fmt_date(nxt)}. See how many days are left and the dates for the coming years."
        add(path, layout(path, title, desc, body,
                         {"type": "until", "dates": [[r["date"].isoformat(), r["name"]] for r in recs]},
                         [("Home", "/"), (REGION_OF[c["cc"]], f"/regions/{REGION_SLUG[REGION_OF[c['cc']]]}/"), (name, f"/holidays/{s}/"), (r0["name"], path)]))
        made.append(sl)
    return made


def named_extra(sl, title, dates):
    out = f"<h2>About {esc(title)}</h2><p>{esc(TXT.BACKGROUND.get(sl, ''))}</p>"
    obs = HOLIDAY_INDEX.get(TXT.NAMED_TO_HOLIDAY.get(sl, ""), [])
    us_map = {"memorial-day": "memorial-day", "independence-day-us": "independence-day",
              "labor-day-us": "labour-day", "thanksgiving-us": "thanksgiving-day"}
    us_path = f"/days-until/united-states/{us_map[sl]}/" if sl in us_map else ""
    items = []
    nxt = dates[0]
    items.append((f"When is {title} in {nxt.year}?", f"{esc(title)} falls on {esc(fmt_date(nxt))}."))
    items.append((f"What day of the week is {title} in the coming years?",
                  "; ".join(f"{d.year}: {WD[d.weekday()]}" for d in dates) + "."))
    items.append((f"How many days until {title}?",
                  "The live countdown at the top of this page shows the days and weeks left. It is calculated from your device's date, so it is always current."))
    if obs:
        items.append((f"Is {title} a public holiday?",
                      f"It is a nationwide public holiday in {len(obs)} of the countries and territories in our data, "
                      f"including {cname_links(obs, 12)}. See each country's page for official dates."))
        out += f'<h2>Countries where {esc(title)} is a public holiday</h2><p>{cname_links(obs, 60)}.</p>'
    elif us_path and us_path in pages:
        items.append((f"Is {title} a public holiday?",
                      f'In the United States it is a public holiday; see <a href="{us_path}">the United States page</a>. In most other countries it is not.'))
    else:
        items.append((f"Is {title} a public holiday?",
                      "In most countries it is not a public holiday but a day that people mark with traditions, events or shopping. Official days off are listed on each country's page."))
    items.append(("Does the date change every year?",
                  "Fixed-date events such as 25 December stay on the same calendar date and only the weekday changes. Events defined by a weekday rule or by Easter move around, as the table above shows."))
    return out + faq_html(items)


def build_named():
    today = NOW_UTC.date()
    links = []
    for sl, title, fn, blurb in NAMED:
        dates = [fn(y) for y in range(YEAR, YEAR + 4)]
        nxt = next_on_or_after(dates, today)
        days = (nxt - today).days
        rows = "".join(f"<tr><td>{d.year}</td><td>{esc(fmt_date(d))}</td></tr>" for d in dates)
        body = f"""<h1>How many days until {esc(title)}?</h1>
{until_block(days, fmt_date(nxt), wk_text(days))}
<p>{esc(blurb)}</p>
<h2>{esc(title)} dates</h2>
<div class="tw"><table><tr><th>Year</th><th>Date</th></tr>{rows}</table></div>
{named_extra(sl, title, dates)}
<p><a href="/days-until/">More countdowns</a> · <a href="/holidays/">Public holidays by country</a></p>"""
        path = f"/days-until/{sl}/"
        add(path, layout(path, f"How Many Days Until {title}? Countdown {nxt.year}",
                         f"{title} {nxt.year} is on {fmt_date(nxt)}. Live countdown in days and weeks.",
                         body, {"type": "until", "dates": [[d.isoformat(), title] for d in dates]},
                         [("Home", "/"), ("Days until", "/days-until/"), (title, path)]))
        links.append((sl, title))
        NAMED_DATES[sl] = [d.isoformat() for d in dates]
    return links


def build_monthday():
    today = NOW_UTC.date()
    links = []
    d = dt.date(2024, 1, 1)
    while d.year == 2024:
        m, dd = d.month, d.day
        label = f"{MONTHS[m - 1]} {dd}"
        sl = f"{MONTHS[m - 1].lower()}-{dd}"
        dates = []
        for y in range(YEAR, YEAR + 9):
            try:
                dates.append(dt.date(y, m, dd))
            except ValueError:
                pass
        nxt = next_on_or_after(dates, today)
        days = (nxt - today).days
        rows = "".join(f"<tr><td>{x.year}</td><td>{WD[x.weekday()]}</td></tr>" for x in dates[:6])
        leap = ' Because it exists only in leap years, the countdown skips to the next leap year.' if (m, dd) == (2, 29) else ""
        doy = nxt.timetuple().tm_yday
        left = (dt.date(nxt.year, 12, 31) - nxt).days
        iso_wk = nxt.isocalendar()[1]
        world = [(oc, orr) for oc in COUNTRIES for orr in oc["pub"]
                 if orr["global"] and orr["date"] == nxt]
        world_html = ""
        if world:
            lines = "".join(f'<li>{flag(oc["cc"])} <a href="/holidays/{oc["slug"]}/">{esc(oc["name"])}</a>: {esc(orr["name"])}</li>'
                            for oc, orr in world[:60])
            more = f"<p class=\"mut\">and {len(world) - 60} more.</p>" if len(world) > 60 else ""
            world_html = (f"<h2>Public holidays on {label} {nxt.year} around the world</h2>"
                          f"<p>In {nxt.year}, {label} is a nationwide public holiday in {len(world)} of the countries in our data.</p>"
                          f'<ul class="plain">{lines}</ul>{more}')
        else:
            world_html = (f"<h2>Public holidays on {label} {nxt.year}</h2>"
                          f"<p>None of the countries in our data has a nationwide public holiday on {label} in {nxt.year}.</p>")
        leap_note = "a leap year" if (nxt.year % 4 == 0 and (nxt.year % 100 != 0 or nxt.year % 400 == 0)) else "not a leap year"
        faq = faq_html([
            (f"How many days until {label}?", "The live countdown at the top of this page shows the exact number of days and weeks. It is calculated from your device's date."),
            (f"What day of the week is {label} in {nxt.year}?", f"{label} {nxt.year} is a {WD[nxt.weekday()]}."),
            (f"Which day of the year is {label}?", f"In {nxt.year}, {label} is day {doy} of the year, in ISO week {iso_wk}, with {left} days left in the year. {nxt.year} is {leap_note}."),
            (f"Is {label} a public holiday?", (f"In {nxt.year} it is a nationwide public holiday in {len(world)} countries in our data; see the list above." if world else f"Not in any of the countries in our data in {nxt.year}.")),
        ])
        body = f"""<h1>How many days until {label}?</h1>
{until_block(days, fmt_date(nxt), wk_text(days))}
<p>The next {label} is on a {WD[nxt.weekday()]}, {days} days from now.{leap}</p>
<div class="stats">
<div><b>{doy}</b><span>day of the year</span></div>
<div><b>{left}</b><span>days left that year</span></div>
<div><b>{iso_wk}</b><span>ISO week number</span></div>
</div>
<h2>What day of the week is {label}?</h2>
<div class="tw"><table><tr><th>Year</th><th>Weekday</th></tr>{rows}</table></div>
{world_html}
{faq}
<p><a href="/days-until/">More countdowns</a> · <a href="/holidays/">Public holidays by country</a></p>"""
        path = f"/days-until/{sl}/"
        add(path, layout(path, f"How Many Days Until {label}? Countdown {nxt.year}",
                         f"There are {days} days until {label} {nxt.year} ({WD[nxt.weekday()]}). Live countdown with weekdays for the coming years.",
                         body, {"type": "until", "dates": [[x.isoformat(), label] for x in dates]},
                         [("Home", "/"), ("Days until", "/days-until/"), (label, path)]))
        links.append((sl, label))
        d += dt.timedelta(days=1)
    return links


def region_tiles():
    out = ""
    for reg, sl in REGION_SLUG.items():
        n = sum(1 for c in COUNTRIES if REGION_OF[c["cc"]] == reg)
        out += f'<li><a href="/regions/{sl}/"><span class="t">{reg}</span><span class="dl">{n} countries</span></a></li>'
    return out


def build_indexes(countries, named, monthday, holiday_counts):
    opts = "".join(
        f'<option value="/holidays/{c["slug"]}/" data-cc="{c["cc"]}">{esc(c["name"])}</option>'
        for c in countries)
    clist = "".join(
        f'<li><a href="/holidays/{c["slug"]}/">{flag(c["cc"])} {esc(c["name"])}</a></li>' for c in countries)
    today = NOW_UTC.date()

    def ev_tile(sl, t):
        dates = NAMED_DATES[sl]
        nx = next((d for d in dates if d >= today.isoformat()), dates[-1])
        n = (dt.date.fromisoformat(nx) - today).days
        txt = "today" if n == 0 else "tomorrow" if n == 1 else f"in {n} days"
        return (f'<li><a href="/days-until/{sl}/" data-dates="{",".join(dates)}">'
                f'<span class="em">{EMOJI.get(sl, "📅")}</span><span class="t">{esc(t)}</span>'
                f'<span class="dl">{txt}</span></a></li>')

    pop = "".join(ev_tile(sl, t) for sl, t in named[:12])
    flt = '<input type="search" id="cf" class="filter" placeholder="Filter countries…" aria-label="Filter countries">'
    body = f"""<section class="hero">
<span class="eyebrow">{len(countries)} countries · updated daily</span>
<h1>Is it a public holiday?</h1>
<p class="lead">Check today, tomorrow or the next day off in any country, and count down the days.</p>
<div class="search"><select id="cs" aria-label="Country">{opts}</select><button class="pri" id="go" type="button">Show holidays</button></div>
<div id="me" class="me" hidden>
<div class="who"><img id="me-flag" class="fl fl-lg" src="/flags/ee.svg" alt="" width="48" height="36"><span id="me-title"></span></div>
<div class="res"><strong id="me-ans"></strong><span class="mut" id="me-detail"></span></div>
<a class="go" id="me-go" href="/holidays/">All holidays →</a>
</div>
</section>
<h2>Count down to…</h2>
<ul class="tiles ev">{pop}</ul>
<p><a href="/days-until/">See all countdowns, including any date of the year →</a></p>
<h2>How {esc(SITE_NAME)} works</h2>
<div class="steps">
<div><b>1</b><h3>Pick a country</h3><p>Choose from {len(countries)} countries and territories, or let the page detect yours.</p></div>
<div><b>2</b><h3>See today's status</h3><p>We check the date in the country's own time zone and tell you whether it is a public holiday.</p></div>
<div><b>3</b><h3>Plan ahead</h3><p>Browse the next holidays, long weekends and a live countdown for every date.</p></div>
</div>
<h2>Browse by region</h2>
<ul class="tiles">{region_tiles()}</ul>
<p><a href="/holidays/world/">See public holidays worldwide by month →</a></p>
<h2>Browse by country</h2>
{flt}
<ul class="tiles" id="clist">{clist}</ul>
{faq_html(TXT.GENERAL_FAQ[:6])}
<p><a href="/faq/">More questions and a glossary →</a></p>"""
    add("/", layout("/", f"{SITE_NAME}: Public Holidays and Days Until Countdowns",
                    f"Is today a public holiday? Check {len(countries)} countries, see the next holiday and count the days until Christmas, Easter or any date.",
                    body))
    add("/holidays/", layout("/holidays/", f"Public Holidays by Country {YEAR}",
                             f"Public holiday calendars for {len(countries)} countries in {YEAR} and {YEAR + 1}.",
                             f"<h1>Public holidays by country</h1>{flt}<ul class=\"tiles\" id=\"clist\">{clist}</ul>", None,
                             [("Home", "/")]))
    nl = "".join(ev_tile(sl, t) for sl, t in named)
    ml = "".join(f'<li><a href="/days-until/{sl}/">{esc(t)}</a></li>' for sl, t in monthday)
    add("/days-until/", layout("/days-until/", "Days Until Countdowns: Holidays and Any Date",
                               "How many days until Christmas, Easter, Halloween or any date of the year? Live countdowns in days and weeks.",
                               f"<h1>Days until…</h1><h2>Holidays and events</h2><ul class=\"tiles ev\">{nl}</ul><h2>Any date</h2><ul class=\"grid\">{ml}</ul>",
                               None, [("Home", "/")]))


def build_faq():
    gl = "".join(f"<dt>{esc(t)}</dt><dd>{esc(d)}</dd>" for t, d in TXT.GLOSSARY)
    body = (f"<h1>Questions and answers</h1><p>Short answers about public holidays and how this site works.</p>"
            + faq_html(TXT.GENERAL_FAQ, "Frequently asked questions")
            + f'<section class="faq"><h2>Glossary</h2><dl>{gl}</dl></section>'
            + '<p><a href="/holidays/">Browse public holidays by country</a></p>')
    add("/faq/", layout("/faq/", f"Public Holiday FAQ and Glossary | {SITE_NAME}",
                        "Answers to common questions about public holidays, bank holidays, regional holidays, days in lieu and how the dates are calculated.",
                        body, None, [("Home", "/")]))


def build_regions():
    today = NOW_UTC.date()
    idx = ""
    for reg, sl in REGION_SLUG.items():
        cs = [c for c in COUNTRIES if REGION_OF[c["cc"]] == reg]
        if not cs:
            continue
        counts = []
        rows = ""
        for c in cs:
            nat = [r for r in c["pub"] if r["global"] and r["date"].year == YEAR]
            counts.append((len(nat), c))
            up = next((r for r in headline(c) if r["date"] >= country_today(c)), None)
            nxt = f'{esc(up["name"])}<div class="mut">{esc(fmt_date(up["date"]))}</div>' if up else "-"
            rows += (f'<tr><td>{flag(c["cc"])} <a href="/holidays/{c["slug"]}/">{esc(c["name"])}</a></td>'
                     f'<td>{len(nat)}</td><td>{nxt}</td></tr>')
        counts.sort(key=lambda x: (-x[0], x[1]["name"]))
        top, low = counts[0], counts[-1]
        avg = sum(n for n, _ in counts) / len(counts)
        body = f"""<h1>Public holidays in {reg} {YEAR}</h1>
<p>{esc(TXT.REGION_TEXT[reg])}</p>
<div class="stats">
<div><b>{len(cs)}</b><span>countries and territories</span></div>
<div><b>{avg:.0f}</b><span>nationwide holidays on average in {YEAR}</span></div>
<div><b>{top[0]}</b><span>most: {esc(top[1]["name"])}</span></div>
<div><b>{low[0]}</b><span>fewest: {esc(low[1]["name"])}</span></div>
</div>
<h2>Countries in {reg}</h2>
<div class="tw"><table><tr><th>Country</th><th>Nationwide holidays {YEAR}</th><th>Next public holiday</th></tr>{rows}</table></div>
{faq_html([
    (f"Which {reg} country has the most public holidays in {YEAR}?", f"Among the countries in our data, {esc(top[1]['name'])} has the most nationwide public holidays in {reg} in {YEAR}: {top[0]}."),
    (f"How many public holidays does a typical {reg} country have?", f"The average across the {len(cs)} countries in our data is about {avg:.0f} nationwide public holidays in {YEAR}, but the range is wide."),
    ("Where can I see holidays for a single country?", 'Open any country in the table for its full calendar, long weekends and a live countdown.'),
])}
<p><a href="/regions/">All regions</a> · <a href="/holidays/world/">Holidays worldwide by month</a></p>"""
        add(f"/regions/{sl}/", layout(f"/regions/{sl}/", f"Public Holidays in {reg} {YEAR} – Countries and Next Holiday",
                                      f"Public holidays in {len(cs)} countries and territories in {reg} for {YEAR}: how many each has and the next holiday.",
                                      body, None, [("Home", "/"), ("Regions", "/regions/"), (reg, f"/regions/{sl}/")]))
        idx += f'<li><a href="/regions/{sl}/"><span class="t">{reg}</span><span class="dl">{len(cs)} countries</span></a></li>'
    add("/regions/", layout("/regions/", f"Public Holidays by Region {YEAR}",
                            "Public holidays in Europe, the Americas, Asia, Africa and Oceania.",
                            f"<h1>Public holidays by region</h1><ul class=\"tiles ev\">{idx}</ul>", None, [("Home", "/")]))


def build_world_months():
    links = ""
    for y in YEARS:
        for m in range(1, 13):
            groups = {}
            for c in COUNTRIES:
                for r in c["pub"]:
                    if r["global"] and r["date"].year == y and r["date"].month == m:
                        groups.setdefault((r["date"], r["name"]), []).append(c)
            if not groups:
                continue
            days = {}
            for (d, _), cs in groups.items():
                days[d] = days.get(d, 0) + len(cs)
            busiest = max(days.items(), key=lambda kv: (kv[1], -kv[0].toordinal()))
            rows = ""
            for (d, nm), cs in sorted(groups.items(), key=lambda kv: (kv[0][0], -len(kv[1]), kv[0][1])):
                shown = cs[:30]
                names = ", ".join(f'<a href="/holidays/{c["slug"]}/">{esc(c["name"])}</a>' for c in shown)
                if len(cs) > 30:
                    names += f" and {len(cs) - 30} more"
                rows += (f'<tr><td>{d.day} {MONTHS[m - 1][:3]}<div class="mut">{WD[d.weekday()][:3]}</div></td>'
                         f'<td>{esc(nm)}<div class="mut">{plural(len(cs), "country")}</div></td><td>{names}</td></tr>')
            sl = f"{MONTHS[m - 1].lower()}-{y}"
            path = f"/holidays/world/{sl}/"
            nav = ""
            body = f"""<h1>Public holidays worldwide in {MONTHS[m - 1]} {y}</h1>
<p>{len(groups)} different nationwide public holidays (counted by date and name) fall in {MONTHS[m - 1]} {y} across the countries in our data. The busiest date is {esc(fmt_date(busiest[0]))}, when {plural(busiest[1], "country")} have a public holiday. Holidays that apply only in some regions are not included here; open a country page for those.</p>
<div class="tw"><table><tr><th>Date</th><th>Holiday</th><th>Countries</th></tr>{rows}</table></div>
{faq_html([
    (f"Which date has the most public holidays in {MONTHS[m - 1]} {y}?", f"{esc(fmt_date(busiest[0]))}, when {plural(busiest[1], 'country')} have a public holiday."),
    (f"How many different public holidays are there in {MONTHS[m - 1]} {y}?", f"{len(groups)} distinct date and holiday combinations across all countries in our data."),
    ("Are regional holidays included?", "No. This page lists only holidays that apply in the whole country. Regional holidays are shown on each country's page."),
])}
<p><a href="/holidays/world/">All months</a> · <a href="/holidays/">Countries</a></p>"""
            add(path, layout(path, f"Public Holidays Worldwide in {MONTHS[m - 1]} {y} – By Country",
                             f"Every nationwide public holiday in {MONTHS[m - 1]} {y}, with the date and the countries that observe it.",
                             body, None, [("Home", "/"), ("By month", "/holidays/world/"), (f"{MONTHS[m - 1]} {y}", path)]))
            links += f'<li><a href="{path}"><span class="t">{MONTHS[m - 1]} {y}</span><span class="dl">{len(groups)} holidays</span></a></li>'
    add("/holidays/world/", layout("/holidays/world/", f"Public Holidays Worldwide by Month {YEAR}–{YEAR + 1}",
                                   "Month-by-month list of nationwide public holidays around the world, with the countries that observe each one.",
                                   f"<h1>Public holidays worldwide by month</h1><p>Pick a month to see every nationwide public holiday and the countries that observe it.</p><ul class=\"tiles ev\">{links}</ul>",
                                   None, [("Home", "/")]))


def build_static():
    n = esc(SITE_NAME)
    contact_p = ' If something looks wrong, <a href="/contact/">tell us</a> and we will check it.' if CONTACT_ON else ""
    add("/about/", layout("/about/", f"About {SITE_NAME}",
                          f"What {SITE_NAME} is, who it is for and where its data comes from.",
                          f"""<h1>About {n}</h1>
<p>{n} answers a simple question quickly: is today, or tomorrow, a public holiday in a given country? Next to that you find the date of the next holiday, long weekends, month-by-month overviews for the whole world and live countdowns to holidays and to any date of the year.</p>
<h2>Who it is for</h2>
<p>Travellers who want to know whether shops and offices are open, people who work with colleagues or customers in other countries, event planners, and anyone who wants to plan a long weekend.</p>
<h2>Where the data comes from</h2>
<p>Public holiday data comes from the open <a href="https://date.nager.at" rel="noopener">Nager.Date</a> project. The site is rebuilt every day. Read more about <a href="/methodology/">how the answers are calculated</a>.{contact_p}</p>
<p>{n} is operated by {esc(OWNER)}, a company registered in Estonia.</p>
<p>Holidays can be moved or added at short notice, so always confirm with an official government source before you plan around a date.</p>""",
                          None, [("Home", "/")]))
    add("/methodology/", layout("/methodology/", f"How {SITE_NAME} Works – Data and Methodology",
                                "Where the holiday data comes from, how we decide what counts as a public holiday and how countdowns and time zones are calculated.",
                                f"""<h1>How {n} works</h1>
<p>This page explains where the information comes from and how the answers on the site are produced.</p>
<h2>Data source</h2>
<p>The lists of public holidays come from the open <a href="https://date.nager.at" rel="noopener">Nager.Date</a> project. The site downloads the lists for the current and the next year, and the whole site is rebuilt every day, so changes in the source reach the pages within about a day.</p>
<h2>What counts as a public holiday</h2>
<p>Only days that the source marks as <em>public holidays</em> are used for the answers, the countdowns and the tables. Other entries, such as bank-only days, school days, optional days and observances, are not counted as public holidays. Some countries list them separately and we show them in a collapsed list on the country page.</p>
<h2>Nationwide and regional holidays</h2>
<p>A holiday is marked <em>Nationwide</em> when it applies everywhere in the country and <em>Some regions</em> when it applies only to a state, province or other part. The headline answers and the "next holiday" countdowns use nationwide holidays when a country has any, so a local holiday does not hide the real next day off for most people.</p>
<h2>Time zones</h2>
<p>"Is today a holiday" is answered for the date in the country's main time zone, using the time zone database. For countries with several time zones, such as the United States, Russia or Brazil, we use the main zone, so a holiday may start a few hours earlier or later in other parts of the country.</p>
<h2>Countdowns</h2>
<p>Countdowns are calculated in your browser from your device's date. We count calendar days, so a holiday tomorrow is one day away and a holiday today is zero days away. The week figure divides the number of days by seven.</p>
<h2>Moveable and approximate dates</h2>
<p>Western Easter and the holidays counted from it are calculated with the standard Gregorian method. The solstice pages use 21 June and 21 December as close approximations, because the exact moment varies by a day from year to year.</p>
<h2>Accuracy and corrections</h2>
<p>Governments can change holidays at short notice and some dates depend on religious or astronomical decisions. We cannot guarantee that every date is right.{contact_p} Please confirm important dates with an official government source before you book travel or plan business around them.</p>""",
                                None, [("Home", "/")]))
    add("/terms/", layout("/terms/", f"Terms of Use and Disclaimer | {SITE_NAME}",
                          f"Terms of use and disclaimer for {SITE_NAME}.",
                          f"""<h1>Terms of use and disclaimer</h1>
<p>{n} is operated by {esc(OWNER)} ("we", "us"). By using the site you agree to these terms. If you do not agree, please do not use the site.</p>
<h2>Information only</h2>
<p>Everything on this site is general information about public holidays and dates. We try to keep it accurate, but we make no promise that it is complete, current or free of errors. Do not rely on it alone for travel bookings, legal deadlines, payroll, contracts or other decisions with financial or legal consequences. Check an official government source first.</p>
<h2>No liability</h2>
<p>To the extent the law allows, we are not responsible for any loss or damage that results from using the site or from a wrong or missing date.</p>
<h2>Third-party content and links</h2>
<p>The site links to other websites, for example the data source. We do not control them and are not responsible for their content. Advertising or affiliate links may be added in the future and will be marked as such.</p>
<h2>Intellectual property</h2>
<p>The design and text of {n} belong to {esc(OWNER)}. The underlying public holiday data comes from the open Nager.Date project. Flag images come from the MIT-licensed flag-icons project. You may link to any page of the site freely.</p>
<h2>Acceptable use</h2>
<p>Please do not overload the site with automated requests or try to disrupt it.</p>
<h2>Changes</h2>
<p>We may change these terms and the site at any time. The current version is always on this page.</p>""",
                          None, [("Home", "/")]))
    captcha_note = ('<p>To keep automated spam out, the contact form uses the hCaptcha service. When you open the contact page, hCaptcha loads from its own servers and may process technical data such as your IP address and browser details, and may set cookies, to tell people from robots. It is loaded on the contact page only.</p>' if CONTACT_KEY else "")
    form_note = ' Messages sent with the contact form are delivered through the Web3Forms service, which processes the name, email address and message you enter so that we can read and answer them.' if CONTACT_KEY else ""
    add("/privacy/", layout("/privacy/", "Privacy Policy",
                            f"Privacy policy of {SITE_NAME}.",
                            f"""<h1>Privacy policy</h1>
<p>{n} is operated by {esc(OWNER)}, a company registered in Estonia, which is the controller of any personal data described on this page. {n} does not ask you to create an account and does not use advertising cookies.</p>
<h2>What stays on your device</h2>
<p>If you switch between light and dark mode, the site stores your choice in your browser's local storage on your own device. The site also reads your browser's language and time zone setting to preselect your country. Neither is sent to us.</p>
<h2>Hosting</h2>
<p>The site is hosted on GitHub Pages and its domain is managed through Cloudflare's DNS service. Like any web host, they may record technical data such as your IP address and the pages you request in their server logs.</p>
<h2>Contact{" form" if CONTACT_KEY else ""}</h2>
<p>If you write to us, we use your message and email address only to answer you.{form_note}</p>{captcha_note}
<h2>Analytics and cookies</h2>
<p>With your consent, we use Google Analytics 4, a service of Google, to learn which pages are visited and how people find the site. Google Analytics sets the cookies <code>_ga</code> and <code>_ga_*</code> and collects data such as the pages you view, your approximate location, your device and browser type, and the page you came from. We do not use it to identify you personally.</p>
<p>Analytics is switched off until you press <em>Accept</em> in the cookie notice. If you press <em>Decline</em>, nothing is loaded from Google. You can change your choice at any time with <em>Cookie settings</em> in the footer of every page, which also deletes the Analytics cookies when you decline. Google may process the data outside the European Economic Area under its own terms. See <a href="https://policies.google.com/technologies/partner-sites" rel="noopener">how Google uses data</a> for details.</p>
<p>Your choice is stored in your browser's local storage on your own device. If advertising is added in the future, this page will name the partners and ask for consent before any advertising cookie is used.</p>
<h2>Your rights</h2>
<p>You can ask us to see, correct or delete any message you sent us.{contact_p}</p>""",
                            None, [("Home", "/")]))
    if CONTACT_ON:
        parts = [f"<h1>Contact</h1><p>Found a wrong date or a missing holiday, or want to ask a question or make a suggestion? Write to us. When you report a date, please include the country, the holiday and a link to the official source if you have one.</p>"]
        if CONTACT_KEY:
            parts.append(f"""<form id="cform" class="form" method="post" action="https://api.web3forms.com/submit">
<input type="hidden" name="access_key" value="{esc(CONTACT_KEY)}">
<input type="hidden" name="subject" value="{n} contact form">
<input type="hidden" name="from_name" value="{n} website">
<input type="checkbox" name="botcheck" class="hp" tabindex="-1" autocomplete="off" aria-hidden="true">
<input type="text" name="website" class="hp" tabindex="-1" autocomplete="off" aria-hidden="true" value="">
<label>Your name<input type="text" name="name" autocomplete="name" required maxlength="100"></label>
<label>Email address<input type="email" name="email" autocomplete="email" required maxlength="150"></label>
<label>Topic<select name="topic"><option>Correction to a date</option><option>Question</option><option>Suggestion</option><option>Advertising or partnership</option><option>Other</option></select></label>
<label>Message<textarea name="message" rows="6" required minlength="10" maxlength="3000"></textarea></label>
<label class="chk"><input type="checkbox" name="consent" value="yes" required><span>I agree that my message is processed to answer me, as described in the <a href="/privacy/">privacy policy</a>.</span></label>
<div class="h-captcha" data-captcha="true"></div>
<button class="pri" type="submit">Send message</button>
<p id="cstatus" role="status" aria-live="polite"></p>
</form>
<script src="https://web3forms.com/client/script.js" async defer></script>""")
        if CONTACT_EMAIL:
            parts.append(f'<p>{"You can also write" if CONTACT_KEY else "Write"} to us by email: {email_link(CONTACT_EMAIL)}.</p>')
        add("/contact/", layout("/contact/", f"Contact {SITE_NAME}", f"Report a wrong date or send a question or suggestion to {SITE_NAME}.",
                                "".join(parts), None, [("Home", "/")]))
    add("/404.html", layout("/404.html", "Page not found", "Page not found.",
                            '<h1>Page not found</h1><p><a href="/">Back to the start</a></p>'))


# ---------------------------------------------------------------- main
def main():
    countries = load_countries()
    print("countries:", len(countries))
    COUNTRIES.extend(countries)
    for c in countries:
        REGION_OF[c["cc"]] = region_for(c)
        seen = set()
        for r in c["pub"]:
            if r["global"]:
                sl = slugify(r["name"])
                if (c["cc"], sl) not in seen:
                    seen.add((c["cc"], sl))
                    HOLIDAY_INDEX.setdefault(sl, []).append((c, r))
    holiday_counts = {}
    for c in countries:
        build_country(c, countries)
        build_isday(c, 0)
        build_isday(c, 1)
        holiday_counts[c["cc"]] = build_country_holiday(c)
    named = build_named()
    monthday = build_monthday()
    build_indexes(countries, named, monthday, holiday_counts)
    build_faq()
    build_regions()
    build_world_months()
    build_static()

    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir()
    for path, text in pages.items():
        if path.endswith(".html"):
            out = DIST / path.lstrip("/")
        else:
            out = DIST / path.lstrip("/") / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf8")
    for f in ASSETS.iterdir():
        if f.is_dir():
            shutil.copytree(f, DIST / f.name)
        else:
            shutil.copy(f, DIST / f.name)
    (DIST / "d").mkdir()
    for c in countries:
        hmap = {}
        for r in c["pub"]:
            key = r["date"].isoformat()
            if key not in hmap or (r["global"] and not hmap[key]["g"]):
                hmap[key] = {"n": r["name"], "g": r["global"]}
        blob = {"cc": c["cc"], "n": c["name"], "slug": c["slug"], "tz": c["tz"], "h": hmap,
                "dates": [[r["date"].isoformat(), r["name"]] for r in headline(c)]}
        (DIST / "d" / f'{c["cc"].lower()}.json').write_text(
            json.dumps(blob, ensure_ascii=False, separators=(",", ":")), encoding="utf8")
    shutil.copy(DATA / "zone_cc.json", DIST / "d" / "tz.json")
    (DIST / "favicon.svg").write_text(LOGO.replace("<svg ", '<svg xmlns="http://www.w3.org/2000/svg" ', 1), encoding="utf8")

    today = NOW_UTC.date().isoformat()
    urls = [p for p in pages if not p.endswith(".html")]
    sm = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    sm += [f"<url><loc>{SITE_URL}{u}</loc>" + (f"<lastmod>{today}</lastmod>" if u.startswith("/is-t") else "") + "</url>"
           for u in sorted(urls)]
    sm.append("</urlset>")
    (DIST / "sitemap.xml").write_text("\n".join(sm), encoding="utf8")
    (DIST / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n", encoding="utf8")
    print("pages:", len(pages), "->", DIST)


if __name__ == "__main__":
    main()
