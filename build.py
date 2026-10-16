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

ROOT = Path(__file__).parent
DATA = ROOT / "data"
DIST = ROOT / "dist"
ASSETS = ROOT / "assets"

SITE_NAME = os.environ.get("SITE_NAME", "HolidayLeft")
SITE_URL = os.environ.get("SITE_URL", "https://holidayleft.com").rstrip("/")
API = "https://date.nager.at/api/v3"
REFRESH = "--refresh" in sys.argv

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


def flag(cc):
    return "".join(chr(0x1F1E6 + ord(c) - 65) for c in cc.upper())


def fmt_date(d, weekday=True):
    s = f"{d.day} {MONTHS[d.month - 1]} {d.year}"
    return f"{WD[d.weekday()]}, {s}" if weekday else s


def plural(n, w):
    return f"{n} {w}{'' if n == 1 else 's'}"


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
def layout(path, title, desc, body, data=None, crumbs=None):
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
<link rel="stylesheet" href="/s.css">
</head>
<body>
<header><a class="logo" href="/">📅 {esc(SITE_NAME)}</a>
<nav><a href="/holidays/">Countries</a><a href="/days-until/">Days until</a></nav></header>
<main>
{crumb_html}
{body}
</main>
<footer>
<p>Public holiday data from <a href="https://date.nager.at" rel="noopener">Nager.Date</a>, refreshed daily. Dates can change at short notice, so check official government sources before you plan travel or business around them.</p>
<p><a href="/about/">About</a> · <a href="/privacy/">Privacy</a> · © {YEAR} {esc(SITE_NAME)}</p>
</footer>
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
    return f"""<div class="card">
<div class="big"><span id="days">{days}</span><small id="unit">{unit}</small></div>
<p style="margin:10px 0 0"><strong id="when">{esc(when)}</strong></p>
<p class="mut" id="wk" style="margin:4px 0 0">{extra}</p>
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

    parts = [f'<h1>{flag(c["cc"])} Public holidays in {esc(name)} {YEAR}</h1>']
    if nxt:
        days = (nxt["date"] - today).days
        parts.append(f"""<div class="card"><p class="mut" style="margin:0">Next public holiday in {esc(name)}</p>
<h2 style="margin:4px 0 8px" id="nname">{esc(nxt["name"])}</h2>
<div class="big"><span id="days">{days}</span><small id="unit">{"day" if days == 1 else "days"}</small></div>
<p style="margin:10px 0 0"><strong id="when">{esc(fmt_date(nxt["date"]))}</strong></p>
<p class="mut" id="wk" style="margin:4px 0 0">{wk_text(days)}</p></div>""")
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

    parts.append(f"""<h2>Frequently asked questions</h2>
<p><strong>How many public holidays does {esc(name)} have?</strong><br>
In {YEAR}, {sum(1 for r in c["pub"] if r["date"].year == YEAR and r["global"])} nationwide public holidays are listed above, plus any that apply to single regions.</p>
<p><strong>What is the next public holiday in {esc(name)}?</strong><br>
{esc(nxt["name"]) + " on " + esc(fmt_date(nxt["date"])) if nxt else "See the list above."}</p>""")

    dates = [[r["date"].isoformat(), r["name"]] for r in headline(c)]
    title = f"Public Holidays in {name} {YEAR} and {YEAR + 1} – Dates and Countdown"
    desc = f"Full list of {name} public holidays for {YEAR} and {YEAR + 1}, long weekends, and a live countdown to the next holiday."
    add(f"/holidays/{s}/", layout(f"/holidays/{s}/", title, desc, "\n".join(parts),
                                  {"type": "country", "tz": c["tz"], "dates": dates},
                                  [("Home", "/"), ("Countries", "/holidays/"), (name, f"/holidays/{s}/")]))


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
        nxt_html = f"""<h2>Next public holiday in {esc(name)}</h2>
<p><strong id="nname">{esc(nxt["name"])}</strong> on <span id="nwhen">{esc(fmt_date(nxt["date"]))}</span> – in <span id="ndays">{plural(d, "day")}</span>.</p>"""
    other = "tomorrow" if offset == 0 else "today"
    other_path = f"/is-{other}-a-holiday-in-{s}/"
    body = f"""<h1>Is {word} a public holiday in {esc(name)}?</h1>
<div class="card" style="text-align:center">
<div><span class="ans {cls}" id="ans">{ans}</span></div>
<p style="margin:14px 0 0"><strong id="target">{esc(fmt_date(target))}</strong></p>
<p class="mut" id="detail" style="margin:4px 0 0">{esc(detail)}</p>
</div>
{nxt_html}
<p><a href="{other_path}">Is {other} a holiday in {esc(name)}?</a> · <a href="/holidays/{s}/">All {esc(name)} public holidays {YEAR}</a></p>
<p class="mut">The answer is worked out for the date in {esc(name)}'s main time zone ({esc(c["tz"])}). "Partly" means the day is a holiday only in some regions.</p>"""
    title = f"Is {word.capitalize()} a Public Holiday in {name}? ({fmt_date(target, False)})"
    desc = f"Find out right now whether {word} is a public holiday in {name}, with the next holiday and a countdown."
    path = f"/is-{word}-a-holiday-in-{s}/"
    add(path, layout(path, title, desc, body,
                     {"type": "isday", "offset": offset, "tz": c["tz"], "h": hmap,
                      "dates": [[r["date"].isoformat(), r["name"]] for r in headline(c)]},
                     [("Home", "/"), (name, f"/holidays/{s}/")]))


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
<h2>More {esc(name)} holidays</h2>
<ul class="grid">{sib_html}</ul>
{country_nav(c)}"""
        path = f"/days-until/{s}/{sl}/"
        title = f"Days Until {r0['name']} in {name} – Countdown"
        desc = f"{r0['name']} in {name} is on {fmt_date(nxt)}. See how many days are left and the dates for the coming years."
        add(path, layout(path, title, desc, body,
                         {"type": "until", "dates": [[r["date"].isoformat(), r["name"]] for r in recs]},
                         [("Home", "/"), (name, f"/holidays/{s}/"), (r0["name"], path)]))
        made.append(sl)
    return made


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
<p><a href="/days-until/">More countdowns</a> · <a href="/holidays/">Public holidays by country</a></p>"""
        path = f"/days-until/{sl}/"
        add(path, layout(path, f"How Many Days Until {title}? Countdown {nxt.year}",
                         f"{title} {nxt.year} is on {fmt_date(nxt)}. Live countdown in days and weeks.",
                         body, {"type": "until", "dates": [[d.isoformat(), title] for d in dates]},
                         [("Home", "/"), ("Days until", "/days-until/"), (title, path)]))
        links.append((sl, title))
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
        body = f"""<h1>How many days until {label}?</h1>
{until_block(days, fmt_date(nxt), wk_text(days))}
<p>The next {label} is on a {WD[nxt.weekday()]}, {days} days from now.{leap}</p>
<h2>What day of the week is {label}?</h2>
<div class="tw"><table><tr><th>Year</th><th>Weekday</th></tr>{rows}</table></div>
<p><a href="/days-until/">More countdowns</a> · <a href="/holidays/">Public holidays by country</a></p>"""
        path = f"/days-until/{sl}/"
        add(path, layout(path, f"How Many Days Until {label}? Countdown {nxt.year}",
                         f"There are {days} days until {label} {nxt.year} ({WD[nxt.weekday()]}). Live countdown with weekdays for the coming years.",
                         body, {"type": "until", "dates": [[x.isoformat(), label] for x in dates]},
                         [("Home", "/"), ("Days until", "/days-until/"), (label, path)]))
        links.append((sl, label))
        d += dt.timedelta(days=1)
    return links


def build_indexes(countries, named, monthday, holiday_counts):
    opts = "".join(
        f'<option value="/holidays/{c["slug"]}/" data-cc="{c["cc"]}">{flag(c["cc"])} {esc(c["name"])}</option>'
        for c in countries)
    clist = "".join(
        f'<li><a href="/holidays/{c["slug"]}/">{flag(c["cc"])} {esc(c["name"])}</a></li>' for c in countries)
    pop = "".join(f'<li><a href="/days-until/{sl}/">{esc(t)}</a></li>' for sl, t in named[:12])
    body = f"""<h1>Is it a public holiday? Check any country, any day</h1>
<p>Pick a country to see today's status, the next public holiday and a live countdown. {len(countries)} countries, updated daily.</p>
<div class="card"><div class="row"><select id="cs" aria-label="Country">{opts}</select><button id="go" type="button">Show holidays</button></div></div>
<h2>Popular countdowns</h2>
<ul class="grid">{pop}</ul>
<p><a href="/days-until/">See all countdowns</a></p>
<h2>All countries</h2>
<ul class="grid">{clist}</ul>"""
    add("/", layout("/", f"{SITE_NAME}: Public Holidays and Days Until Countdowns",
                    f"Is today a public holiday? Check {len(countries)} countries, see the next holiday and count the days until Christmas, Easter or any date.",
                    body))
    add("/holidays/", layout("/holidays/", f"Public Holidays by Country {YEAR}",
                             f"Public holiday calendars for {len(countries)} countries in {YEAR} and {YEAR + 1}.",
                             f"<h1>Public holidays by country</h1><ul class=\"grid\">{clist}</ul>", None,
                             [("Home", "/")]))
    nl = "".join(f'<li><a href="/days-until/{sl}/">{esc(t)}</a></li>' for sl, t in named)
    ml = "".join(f'<li><a href="/days-until/{sl}/">{esc(t)}</a></li>' for sl, t in monthday)
    add("/days-until/", layout("/days-until/", "Days Until Countdowns: Holidays and Any Date",
                               "How many days until Christmas, Easter, Halloween or any date of the year? Live countdowns in days and weeks.",
                               f"<h1>Days until…</h1><h2>Holidays and events</h2><ul class=\"grid\">{nl}</ul><h2>Any date</h2><ul class=\"grid\">{ml}</ul>",
                               None, [("Home", "/")]))


def build_static():
    add("/about/", layout("/about/", f"About {SITE_NAME}",
                          f"What {SITE_NAME} is and where its data comes from.",
                          f"""<h1>About {esc(SITE_NAME)}</h1>
<p>{esc(SITE_NAME)} answers simple questions quickly: is today or tomorrow a public holiday in a given country, when is the next one, and how many days are left until a date.</p>
<p>Public holiday data comes from the open <a href="https://date.nager.at">Nager.Date</a> project and the site is rebuilt every day. Holidays can be moved or added at short notice, so always confirm with an official government source before you plan around a date.</p>""",
                          None, [("Home", "/")]))
    add("/privacy/", layout("/privacy/", "Privacy Policy",
                            f"Privacy policy of {SITE_NAME}.",
                            f"""<h1>Privacy policy</h1>
<p>{esc(SITE_NAME)} does not ask for an account, and it does not collect personal data in any form you fill in.</p>
<p>The site reads your browser's language setting only on your own device, to preselect a country. It is not sent anywhere.</p>
<p>If advertising or analytics are added later, they will use cookies provided by those third parties, and this page will name them and explain how to opt out.</p>""",
                            None, [("Home", "/")]))
    add("/404.html", layout("/404.html", "Page not found", "Page not found.",
                            '<h1>Page not found</h1><p><a href="/">Back to the start</a></p>'))


# ---------------------------------------------------------------- main
def main():
    countries = load_countries()
    print("countries:", len(countries))
    holiday_counts = {}
    for c in countries:
        build_country(c, countries)
        build_isday(c, 0)
        build_isday(c, 1)
        holiday_counts[c["cc"]] = build_country_holiday(c)
    named = build_named()
    monthday = build_monthday()
    build_indexes(countries, named, monthday, holiday_counts)
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
        shutil.copy(f, DIST / f.name)

    today = NOW_UTC.date().isoformat()
    urls = [p for p in pages if not p.endswith(".html")]
    sm = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    sm += [f"<url><loc>{SITE_URL}{u}</loc><lastmod>{today}</lastmod></url>" for u in sorted(urls)]
    sm.append("</urlset>")
    (DIST / "sitemap.xml").write_text("\n".join(sm), encoding="utf8")
    (DIST / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n", encoding="utf8")
    print("pages:", len(pages), "->", DIST)


if __name__ == "__main__":
    main()
