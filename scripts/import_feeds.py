"""MicCheckCT feed importer: copies shows from venue calendar feeds (ICS) into
the events table. Runs daily in GitHub Actions; can also be run by hand.

  python scripts/import_feeds.py --dry-run   # read the feeds, show what would change, write nothing
  python scripts/import_feeds.py             # read the feeds and save the shows

Reads SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY from environment variables
(GitHub Actions secrets) or the local .env file. Reads every active 'ics'
row in sources; per-feed filters are in FEED_RULES below.
"""

import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import icalendar

ROOT = Path(__file__).resolve().parent.parent
CT = ZoneInfo("America/New_York")
USER_AGENT = "MicCheckCT feed reader (+https://miccheckct.com)"
HORIZON_DAYS = 60   # upcoming_listings shows 60 days
MAX_PAGES = 8       # most feeds send 30 events per request
PAUSE_SECONDS = 3   # between requests to the same site

# Per-feed rules, keyed by source name. Anything not listed uses the defaults.
#   keep:      regex on title + categories; only matching events are kept
#   skip:      regex on title + categories; matching events are skipped
#   local_time: the feed mislabels its time zone; read clock times as Connecticut time
FEED_RULES = {
    "Hartford Jazz Society calendar (ICS)": {},
    "CT Examiner calendar (ICS)": {
        "keep": r"music|concert",
        "skip": r"\b(film|screening|lecture|talk|town hall|class|workshop|exhibit|gala|auditions?|markets?|musical)\b",
    },
    "The MAC calendar (ICS)": {
        "keep": r"\bconcerts?\b|open mic nites?",
    },
    "The Breakwall calendar (ICS)": {
        "skip": r"trivia|bingo|open mic|feud",
        "local_time": True,
    },
    "The Griswold Inn calendar (ICS)": {
        "keep": r"tap room",
        "local_time": True,
    },
    "Bill's Seafood calendar (ICS)": {
        "skip": r"o[ck]toberfest",
    },
    "CT Public community calendar: Music & Performance (ICS)": {
        "skip": r"theat(er|re)|\bplays?\b|musical|comedy|\breading\b|storytelling|lecture|presentation"
                r"|\bfairs?\b|antiques|trivia|\bgala\b|auditions?|dances? with|\bsession\b",
    },
}

# Other names feeds use for venues already in the database: feed name -> venue name
ALIASES = {
    "The Katharine Hepburn Cultural Arts Center": "The Kate",
}

OUT_OF_STATE = re.compile(r"^(NY|NYC|RI|MA|NJ|VT|NH|PA|ME|Brooklyn|Manhattan|New York)$", re.I)


# ---------------------------------------------------------------- setup
def load_settings():
    values = {}
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                values[k.strip()] = v.strip().strip('"').strip("'")
    url = (os.environ.get("SUPABASE_URL") or values.get("SUPABASE_URL", "")).rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or values.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        sys.exit("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are both needed.")
    return url, key


class Supabase:
    def __init__(self, url, key):
        self.url, self.key = url, key

    def request(self, method, path, body=None, prefer=None):
        headers = {"apikey": self.key, "Content-Type": "application/json", "User-Agent": USER_AGENT}
        if self.key.startswith("eyJ"):
            headers["Authorization"] = f"Bearer {self.key}"
        if prefer:
            headers["Prefer"] = prefer
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(f"{self.url}/rest/v1/{path}", data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                text = response.read().decode()
                return json.loads(text) if text else None
        except urllib.error.HTTPError as error:
            raise RuntimeError(f"Supabase {method} {path.split('?')[0]}: {error.code} {error.read().decode()[:300]}")

    def get_all(self, path):
        """GET every row, 1,000 at a time."""
        rows, offset = [], 0
        while True:
            page = self.request("GET", f"{path}&limit=1000&offset={offset}")
            rows += page
            if len(page) < 1000:
                return rows
            offset += 1000


# ---------------------------------------------------------------- text helpers
def norm(text):
    """Lowercase, '&' to 'and', no punctuation or 'the': for comparing names."""
    text = html.unescape(text or "").lower().replace("&", " and ").replace("’", "").replace("'", "")
    text = re.sub(r"\([^)]*\)", " ", text)  # drop "(North Haven)" style suffixes
    return " ".join(w for w in re.sub(r"[^a-z0-9]+", " ", text).split() if w != "the")


def clean(text):
    return re.sub(r"\s+", " ", html.unescape(str(text or ""))).strip()


def category_for(title):
    t = title.lower()
    if "open mic" in t:
        return "open_mic"
    if "karaoke" in t:
        return "karaoke"
    if re.search(r"\bjam\b", t):
        return "jam_session"
    return "live_music"


def uid_key(uid):
    """The Events Calendar UIDs look like '8455-1793390400-1793404800@site.com'.
    The start/end numbers change when a show is moved, so match on '8455@site.com'."""
    m = re.match(r"^(\d+)-\d+-\d+@(.+)$", uid)
    return f"{m.group(1)}@{m.group(2)}" if m else uid


# ---------------------------------------------------------------- feeds
_last_request = {}


def fetch(url):
    host = urllib.parse.urlsplit(url).netloc
    wait = PAUSE_SECONDS - (time.time() - _last_request.get(host, 0))
    if wait > 0:
        time.sleep(wait)
    for attempt in range(2):
        _last_request[host] = time.time()
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/calendar"})
        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                body = response.read()
                if b"BEGIN:VCALENDAR" not in body[:2000]:
                    raise RuntimeError("the site sent a web page, not a calendar (it may block automated readers)")
                return body
        except urllib.error.HTTPError as error:
            if error.code == 429 and attempt == 0:
                time.sleep(60)  # the site asked us to slow down
                continue
            raise RuntimeError(f"HTTP {error.code} from the feed")
    raise RuntimeError("the feed kept asking us to slow down (HTTP 429)")


def with_date(url, day):
    """The Events Calendar feeds accept tribe-bar-date to start from a given day."""
    parts = urllib.parse.urlsplit(url)
    query = [(k, v) for k, v in urllib.parse.parse_qsl(parts.query, keep_blank_values=True) if k != "tribe-bar-date"]
    query.append(("tribe-bar-date", day.isoformat()))
    return urllib.parse.urlunsplit(parts._replace(query=urllib.parse.urlencode(query)))


def read_feed(url):
    """All events from a feed, following pages until HORIZON_DAYS ahead."""
    horizon = datetime.now(CT).date() + timedelta(days=HORIZON_DAYS)
    events, seen, page_url, last, stepped = [], set(), url, None, False
    for _ in range(MAX_PAGES):
        cal = icalendar.Calendar.from_ical(fetch(page_url))
        page = list(cal.walk("VEVENT"))
        new = [e for e in page if str(e.get("UID")) not in seen]
        seen.update(str(e.get("UID")) for e in new)
        events += new
        dates = [as_date(e.get("DTSTART").dt) for e in page] + ([last] if last else [])
        if not dates:
            break
        last = max(dates)
        if last >= horizon:
            break
        if new:
            stepped = False
            page_url = with_date(url, last)  # ask from that day again: a page can end partway through a day
        elif not stepped:
            stepped = True
            last += timedelta(days=1)       # nothing new from that day: try the next day, once
            page_url = with_date(url, last)
        else:
            break
    return events


def as_date(value):
    return value.date() if isinstance(value, datetime) else value


def event_times(event, local_time):
    """Start and end as Connecticut-time datetimes, and whether the time is known."""
    start = event.get("DTSTART").dt
    end = event.get("DTEND").dt if event.get("DTEND") else None
    if not isinstance(start, datetime):  # all-day: date known, time not
        return datetime(start.year, start.month, start.day, tzinfo=CT), None, False

    def fix(dt):
        if dt.tzinfo is None or local_time:
            return dt.replace(tzinfo=CT)
        return dt.astimezone(CT)

    start = fix(start)
    end = fix(end) if isinstance(end, datetime) else None
    if end and not (start < end <= start + timedelta(days=1)):
        end = None  # some feeds carry nonsense end dates (e.g. 2028)
    return start, end, True


def categories(event):
    raw = event.get("CATEGORIES")
    groups = raw if isinstance(raw, list) else [raw] if raw else []
    return [clean(c) for g in groups for c in g.cats]


# ---------------------------------------------------------------- venues
class VenueMatcher:
    def __init__(self, venues, towns):
        self.venues = [v for v in venues if v["is_active"]]
        self.by_id = {v["id"]: v for v in venues}
        self.towns = {norm(t["name"]): t["name"] for t in towns if t["state"] == "CT"}
        for v in self.venues:
            v["_norm"] = norm(v["name"])
        by_name = {v["name"]: v for v in self.venues}
        self.aliases = {norm(alias): by_name[name] for alias, name in ALIASES.items() if name in by_name}

    def parse(self, location):
        """'Cafe Nine, 250 State St, New Haven, CT' -> ('cafe nine', 'New Haven', in_state)"""
        parts = [p.strip() for p in clean(location).split(",") if p.strip()]
        if not parts:
            return "", None, True
        if any(OUT_OF_STATE.match(p) for p in parts) or any(re.search(r"\b(NY|RI|MA)\s+\d{5}", p) for p in parts):
            return norm(parts[0]), None, False
        town = next((self.towns[norm(p)] for p in parts[1:] if norm(p) in self.towns), None)
        place = "" if norm(parts[0]) in ("ct", "c", "") else norm(parts[0])
        return place, town, True

    def match(self, place, town, title):
        if place in self.aliases:
            return self.aliases[place]
        if place:
            squash = place.replace(" ", "")  # "Firehouse12" matches "Firehouse 12"
            exact = [v for v in self.venues if v["_norm"].replace(" ", "") == squash]
            same_town = [v for v in exact if v["town"] == town]
            if len(same_town) == 1 or (len(exact) == 1 and not same_town):
                return (same_town or exact)[0]
            if town:
                # The venue's whole name inside the location ("bills seafood" in "bills seafood restaurant"),
                # never the reverse: "Mohegan Sun" alone must not pick one of its several stages.
                partial = [v for v in self.venues if v["town"] == town and len(v["_norm"]) >= 5
                           and f" {v['_norm']} " in f" {place} "]
                if len(partial) == 1:
                    return partial[0]
                # "Elicit Brewery" vs "Elicit Brewing Co": same distinctive first word, same town
                # A town name as the first word ("Chester Meeting House") says nothing about the venue.
                first = place.split()[0]
                generic = first in self.towns or first in ("north", "south", "east", "west", "great", "little")
                same_word = [v for v in self.venues if v["town"] == town and len(first) >= 5 and not generic
                             and v["_norm"].split()[:1] == [first] and not v["_norm"].startswith(place)]
                if len(same_word) == 1:
                    return same_word[0]
            return None
        # No usable location: look for a known venue name inside the title.
        found = [v for v in self.venues if len(v["_norm"]) >= 6 and f" {v['_norm']} " in f" {norm(title)} "]
        return found[0] if len(found) == 1 else None


# ---------------------------------------------------------------- main
def main():
    dry_run = "--dry-run" in sys.argv
    db = Supabase(*load_settings())
    now = datetime.now(timezone.utc)

    sources = db.get_all("sources?select=id,name,url,venue_id&source_type=eq.ics&is_active=is.true&order=name")
    matcher = VenueMatcher(db.get_all("venues?select=id,name,town,is_active"),
                           db.get_all("towns?select=name,state"))
    # Shows already in the database from any source, to avoid listing one show twice.
    since = urllib.parse.quote((now - timedelta(days=1)).isoformat())
    others = db.get_all(f"events?select=source_id,venue_id,start_at&start_at=gte.{since}&venue_id=not.is.null")
    # Regular nights (open mics, jams, karaoke) by venue and date.
    regulars = {(r["venue_id"], r["start_at"][:10], r["category"])
                for r in db.get_all("upcoming_listings?select=venue_id,start_at,category&listing_type=eq.recurring")}

    print(f"{'DRY RUN: nothing will be saved. ' if dry_run else ''}{len(sources)} active feeds\n")
    review, totals = [], {"new": 0, "updated": 0, "unchanged": 0}

    for source in sources:
        name, rules = source["name"], FEED_RULES.get(source["name"], {})
        print(f"== {name}")
        try:
            feed_events = read_feed(source["url"])
        except Exception as error:  # one broken feed must not stop the others
            status = f"error: {error}"
            print(f"   {status}\n")
            if not dry_run:
                db.request("PATCH", f"sources?id=eq.{source['id']}",
                           {"last_fetched_at": now.isoformat(), "last_status": status[:500]})
            continue

        existing = db.get_all(f"events?select=id,external_uid,title,start_at,end_at,time_tba,venue_id,status,event_url,category"
                              f"&source_id=eq.{source['id']}&external_uid=not.is.null")
        by_uid = {e["external_uid"]: e for e in existing}
        by_key = {}
        for e in existing:
            by_key.setdefault(uid_key(e["external_uid"]), []).append(e)
        other_starts = {(o["venue_id"], o["start_at"][:16]) for o in others if o["source_id"] != source["id"]}

        skipped, inserts, updates = {}, [], []

        def skip(reason):
            skipped[reason] = skipped.get(reason, 0) + 1

        for event in feed_events:
            uid = str(event.get("UID") or "").strip()
            title = clean(event.get("SUMMARY"))
            if not uid or not title or not event.get("DTSTART"):
                skip("missing ID, title or date")
                continue
            start, end, time_known = event_times(event, rules.get("local_time"))
            if start < now - timedelta(hours=6):
                skip("already past")
                continue
            text = " ".join([title] + categories(event))
            if rules.get("keep") and not re.search(rules["keep"], text, re.I):
                skip("not music (feed filter)")
                continue
            if rules.get("skip") and re.search(rules["skip"], text, re.I):
                skip("not music (feed filter)")
                continue

            location = clean(event.get("LOCATION"))
            venue = matcher.by_id.get(source["venue_id"]) if source["venue_id"] else None
            if not venue:
                place, town, in_state = matcher.parse(location)
                if not in_state:
                    skip("out of state")
                    continue
                if location.lower() in ("virtual event", "online"):
                    skip("online event")
                    continue
                venue = matcher.match(place, town, title)
            category = category_for(title)
            venue_id = venue["id"] if venue else None

            if venue_id and category != "live_music" and (venue_id, start.date().isoformat(), category) in regulars:
                skip("covered by a regular night")
                continue

            row = {
                "title": title[:300],
                "category": category,
                "venue_id": venue_id,
                "location_text": None if venue else (location or None),
                "start_at": start.isoformat(),
                "end_at": end.isoformat() if end else None,
                "time_tba": not time_known,
                "event_url": str(event.get("URL")) if event.get("URL") else None,
            }

            old = by_uid.get(uid)
            if not old:
                same_post = by_key.get(uid_key(uid), [])
                old = same_post[0] if len(same_post) == 1 else None  # the show was moved: same post, new times
            if old:
                changes = {k: v for k, v in row.items() if k != "location_text" and not same_value(old.get(k), v)}
                if old["external_uid"] != uid:
                    changes["external_uid"] = uid
                if venue_id and not old["venue_id"] and old["status"] == "hidden":
                    changes["status"] = "published"  # its venue has since been added
                if old["venue_id"] and not venue_id:
                    # matched before, not now (a matching fix): hide it until its venue is added
                    changes.update(status="hidden", location_text=location or None)
                    review.append(f"{start:%a %b %d} {title[:60]} | {location or '(no location)'} | {name}")
                if changes:
                    updates.append((old, changes))
                else:
                    totals["unchanged"] += 1
                continue

            if venue_id and (venue_id, start.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M")) in other_starts:
                skip("already listed from another source")
                continue
            row.update(source_id=source["id"], external_uid=uid, status="published" if venue else "hidden")
            inserts.append(row)
            if not venue:
                review.append(f"{start:%a %b %d} {title[:60]} | {location or '(no location)'} | {name}")

        kept = len(inserts) + len(updates)
        status = (f"ok: {len(feed_events)} read, {len(inserts)} new, {len(updates)} updated, "
                  f"{sum(skipped.values())} skipped")
        print(f"   {status}")
        for reason, n in sorted(skipped.items(), key=lambda x: -x[1]):
            print(f"     skipped {n}: {reason}")
        for row in inserts:
            where = matcher.by_id[row["venue_id"]]["name"] if row["venue_id"] else "NO VENUE MATCH (hidden)"
            print(f"   + {row['start_at'][:16]} {row['title'][:55]} @ {where}")
        for old, changes in updates:
            print(f"   ~ {old['title'][:55]}: {', '.join(changes)}")
        print()

        totals["new"] += len(inserts)
        totals["updated"] += len(updates)
        if not dry_run:
            if inserts:
                db.request("POST", "events", inserts, prefer="return=minimal")
            for old, changes in updates:
                db.request("PATCH", f"events?id=eq.{old['id']}", changes, prefer="return=minimal")
            db.request("PATCH", f"sources?id=eq.{source['id']}",
                       {"last_fetched_at": now.isoformat(), "last_status": status})

    # Hidden feed shows waiting for a venue: publish any whose venue has since been added,
    # even when today's feed couldn't be read.
    feed_ids = ",".join(s["id"] for s in sources)
    waiting = db.get_all(f"events?select=id,title,start_at,location_text&status=eq.hidden&venue_id=is.null"
                         f"&location_text=not.is.null&source_id=in.({feed_ids})")
    published = 0
    for e in waiting:
        place, town, in_state = matcher.parse(e["location_text"])
        venue = matcher.match(place, town, e["title"]) if in_state else None
        if not venue:
            continue
        published += 1
        print(f"   published {e['start_at'][:10]} {e['title'][:55]} @ {venue['name']}")
        if not dry_run:
            db.request("PATCH", f"events?id=eq.{e['id']}",
                       {"venue_id": venue["id"], "status": "published", "location_text": None}, prefer="return=minimal")
    if published:
        print(f"Venues added since: {published} hidden shows {'would be ' if dry_run else ''}published\n")

    print(f"Total: {totals['new']} new, {totals['updated']} updated, {totals['unchanged']} unchanged")
    if review:
        print(f"\nNeeds a venue ({len(review)}): saved hidden until the venue is added")
        for line in review:
            print(f"  {line}")


def same_value(a, b):
    if a is None or b is None:
        return a == b
    if isinstance(b, str) and re.match(r"\d{4}-\d\d-\d\dT", b):
        return datetime.fromisoformat(a) == datetime.fromisoformat(b)
    return a == b


if __name__ == "__main__":
    main()
