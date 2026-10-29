// MicCheckCT homepage. Reads listings from Supabase with the public key, then
// groups them by town, nearest first. The chosen town is kept only in this
// browser (local storage); nothing about the visitor is sent anywhere.
(function () {
  "use strict";

  const CONFIG = window.MICCHECK_CONFIG || {};
  const TZ = "America/New_York";
  const DEFAULT_TOWN = "New Haven";
  const DEFAULT_RADIUS = "15";
  const RADII = ["5", "10", "15", "25", "50"];
  const STORAGE_KEY = "miccheckct.town";
  const DAYS_PER_PAGE = 7;
  const MAX_DAYS = 56; // upcoming_listings covers 60 days
  const MAX_REGULARS = 6;

  // Database category: which type filter it falls under, its label and tag style
  const TYPES = {
    live_music: { filter: "live", label: "Live music", tag: "tag-live" },
    festival: { filter: "live", label: "Festival", tag: "tag-live" },
    open_mic: { filter: "open", label: "Open mic", tag: "tag-open" },
    jam_session: { filter: "open", label: "Jam session", tag: "tag-open" },
    karaoke: { filter: "karaoke", label: "Karaoke", tag: "tag-karaoke" },
  };
  const FILTERS = [["live", "Live music"], ["open", "Open mic"], ["karaoke", "Karaoke"], ["all", "All"]];
  const WEEKDAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
  const ORDINALS = { 1: "1st", 2: "2nd", 3: "3rd", 4: "4th", "-1": "Last" };

  const $ = (id) => document.getElementById(id);
  const els = {
    town: $("town"), radius: $("radius"), pills: $("pills"), summary: $("summary"),
    groups: $("groups"), status: $("status"), more: $("more"),
    regulars: $("regulars-list"), submit: $("submit-button"), submitNote: $("submit-note"),
  };

  // ---------- Dates, always in Connecticut time ----------
  const keyFormat = new Intl.DateTimeFormat("en-CA", { timeZone: TZ, year: "numeric", month: "2-digit", day: "2-digit" });
  const dayFormat = new Intl.DateTimeFormat("en-US", { timeZone: TZ, weekday: "short", month: "short", day: "numeric" });
  const timeFormat = new Intl.DateTimeFormat("en-US", { timeZone: TZ, hour: "numeric", minute: "2-digit" });

  const dateKey = (date) => keyFormat.format(date); // "2026-10-28"
  function addDays(key, n) {
    const d = new Date(key + "T12:00:00Z");
    d.setUTCDate(d.getUTCDate() + n);
    return d.toISOString().slice(0, 10);
  }
  function dayLabel(date) { // "Thu Oct 8"
    const p = Object.fromEntries(dayFormat.formatToParts(date).map((x) => [x.type, x.value]));
    return `${p.weekday} ${p.month} ${p.day}`;
  }

  const state = {
    town: DEFAULT_TOWN,
    radius: DEFAULT_RADIUS,
    filter: "live", // the page opens on live music
    today: dateKey(new Date()),
    days: 0,             // days of listings loaded so far
    towns: new Map(),    // name -> { name, state, kind, lat, lon }
    rules: new Map(),    // recurring_events id -> rule with its venue
    listings: [],
    seen: new Set(),
    error: false,
  };

  // ---------- Supabase ----------
  async function query(path) {
    const headers = { apikey: CONFIG.supabaseKey };
    if (CONFIG.supabaseKey.startsWith("eyJ")) headers.Authorization = "Bearer " + CONFIG.supabaseKey;
    const response = await fetch(`${CONFIG.supabaseUrl}/rest/v1/${path}`, { headers });
    if (!response.ok) throw new Error(`Supabase returned ${response.status} for ${path.split("?")[0]}`);
    return response.json();
  }

  async function loadTowns() {
    const rows = await query("towns?select=name,state,kind,latitude,longitude&limit=1000");
    for (const t of rows) {
      state.towns.set(t.name, { name: t.name, state: t.state, kind: t.kind, lat: Number(t.latitude), lon: Number(t.longitude) });
    }
  }

  async function loadRules() {
    const rows = await query("recurring_events?select=id,title,category,day_of_week,week_of_month,every_n_weeks,host,venues(name,town)&limit=1000");
    for (const r of rows) if (r.venues) state.rules.set(r.id, r);
  }

  // Loads the next DAYS_PER_PAGE days of listings.
  async function loadWeek() {
    const from = addDays(state.today, state.days);
    const to = addDays(state.today, state.days + DAYS_PER_PAGE);
    // Ask for a little extra on both ends (UTC vs Connecticut time), then keep only from..to.
    const rows = await query(
      "upcoming_listings?select=id,listing_type,title,category,venue_name,town,start_at,time_known,event_url,ticket_url" +
      `&start_at=gte.${from}T00:00:00Z&start_at=lt.${to}T12:00:00Z&order=start_at&limit=1000`);
    if (rows.length === 1000) console.warn("MicCheckCT: 1,000-row limit reached; some listings may be missing.");
    for (const r of rows) {
      const start = new Date(r.start_at);
      const key = dateKey(start);
      const id = `${r.listing_type}:${r.id}:${r.start_at}`;
      if (key < from || key >= to || state.seen.has(id)) continue;
      state.seen.add(id);
      state.listings.push(Object.assign(r, { start, key }));
    }
    state.days += DAYS_PER_PAGE;
  }

  // ---------- Helpers ----------
  function miles(a, b) {
    const R = 3958.8, rad = Math.PI / 180;
    const dLat = (b.lat - a.lat) * rad, dLon = (b.lon - a.lon) * rad;
    const h = Math.sin(dLat / 2) ** 2 + Math.cos(a.lat * rad) * Math.cos(b.lat * rad) * Math.sin(dLon / 2) ** 2;
    return 2 * R * Math.asin(Math.sqrt(h));
  }

  function distanceTo(townName) {
    const home = state.towns.get(state.town), place = state.towns.get(townName);
    if (!home || !place) return null;
    return townName === state.town ? 0 : miles(home, place);
  }

  // "Tuesdays", "2nd Fridays", "Last Sundays", "Every other Tuesday"
  function ruleWhen(rule) {
    const day = WEEKDAYS[rule.day_of_week];
    if (rule.week_of_month) return `${ORDINALS[rule.week_of_month]} ${day}s`;
    if (rule.every_n_weeks === 2) return `Every other ${day}`;
    if (rule.every_n_weeks > 2) return `Every ${rule.every_n_weeks} weeks`;
    return `${day}s`;
  }

  // Short note under a listing: how often a non-weekly night runs, and its host.
  function listingNote(listing) {
    if (listing.listing_type !== "recurring") return "";
    const rule = state.rules.get(listing.id);
    if (!rule) return "";
    const parts = [];
    if (rule.week_of_month || rule.every_n_weeks > 1) parts.push(ruleWhen(rule));
    if (rule.host) parts.push(rule.host);
    return parts.join(", ");
  }

  const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = text;
    return node;
  }

  function saveTown(name) {
    try { localStorage.setItem(STORAGE_KEY, name); } catch (e) { /* storage blocked: fine */ }
  }
  function savedTown() {
    try { return localStorage.getItem(STORAGE_KEY); } catch (e) { return null; }
  }

  // ---------- Rendering ----------
  function renderTownOptions() {
    const names = [...state.towns.values()].filter((t) => t.state === "CT").map((t) => t.name)
      .sort((a, b) => a.localeCompare(b));
    els.town.replaceChildren(...names.map((n) => new Option(n, n)));
    els.town.value = state.town;
  }

  function renderPills() {
    els.pills.replaceChildren(...FILTERS.map(([id, label]) => {
      const button = el("button", "pill", label);
      button.type = "button";
      button.dataset.filter = id;
      button.setAttribute("aria-pressed", String(state.filter === id));
      return button;
    }));
  }

  function listingRow(listing) {
    const type = TYPES[listing.category];
    const row = el("article", "listing");

    const when = el("div", "listing-when");
    when.append(el("div", "listing-day", dayLabel(listing.start)));
    when.append(listing.time_known
      ? el("div", "listing-time", timeFormat.format(listing.start))
      : el("div", "listing-time tba", "Time TBA"));

    const what = el("div", "listing-what");
    const title = el("h3");
    const url = listing.event_url || listing.ticket_url;
    if (url) {
      const link = el("a", null, listing.title);
      link.href = url;
      link.target = "_blank";
      link.rel = "noopener";
      title.append(link);
    } else {
      title.textContent = listing.title;
    }
    const where = el("p", "listing-where", listing.venue_name);
    const note = listingNote(listing);
    if (note) where.append(" ", el("span", "dot", "·"), " ", el("span", "listing-note", note));
    what.append(title, where);

    row.append(when, what, el("span", "tag " + type.tag, type.label));
    return row;
  }

  function render() {
    els.town.value = state.town;
    els.radius.value = state.radius;
    for (const button of els.pills.children) {
      button.setAttribute("aria-pressed", String(button.dataset.filter === state.filter));
    }

    const max = Number(state.radius);
    const groups = new Map();
    for (const listing of state.listings) {
      const type = TYPES[listing.category];
      if (!type || (state.filter !== "all" && type.filter !== state.filter)) continue;
      const d = distanceTo(listing.town);
      if (d == null || d > max) continue;
      if (!groups.has(listing.town)) groups.set(listing.town, { town: listing.town, d, rows: [] });
      groups.get(listing.town).rows.push(listing);
    }

    const sorted = [...groups.values()].sort((a, b) => a.d - b.d || a.town.localeCompare(b.town));
    for (const g of sorted) {
      // By date, then time; "Time TBA" goes last within its day.
      g.rows.sort((a, b) => a.key.localeCompare(b.key) || (b.time_known - a.time_known) || (a.start - b.start) || a.title.localeCompare(b.title));
    }

    els.groups.replaceChildren(...sorted.map((g) => {
      const section = el("section", "town-group");
      const head = el("div", "town-head");
      head.append(el("h2", null, g.town),
        el("span", "town-meta", `${g.d === 0 ? "Your town" : Math.max(1, Math.round(g.d)) + " mi away"} · ${plural(g.rows.length, "listing")}`));
      section.append(head, ...g.rows.map(listingRow));
      return section;
    }));

    const total = sorted.reduce((n, g) => n + g.rows.length, 0);
    const period = state.days <= DAYS_PER_PAGE ? "this week" : `in the next ${state.days} days`;
    const area = `within ${state.radius} miles of ${state.town} ${period}`;
    els.summary.textContent = state.error ? "Listings couldn't load."
      : total === 0 ? `No listings ${area}`
      : `${plural(total, "listing")} in ${plural(sorted.length, "town")} ${area}`;

    renderStatus(total);
    els.more.hidden = state.error || state.days >= MAX_DAYS;
    els.more.textContent = state.days <= DAYS_PER_PAGE ? "Show next week" : "Show another week";
    renderRegulars();
  }

  function renderStatus(total) {
    if (state.error) {
      const box = el("div", "notice");
      const retry = el("button", "button", "Try again");
      retry.type = "button";
      retry.addEventListener("click", () => location.reload());
      box.append(el("p", "notice-title", "Listings couldn't load."),
        el("p", "notice-text", "Check your connection and try again."), retry);
      els.status.replaceChildren(box);
      return;
    }
    if (total > 0) { els.status.replaceChildren(); return; }

    const box = el("div", "notice");
    box.append(el("p", "notice-title", "Nothing in range yet."),
      el("p", "notice-text", "Try a wider distance, or another type of night."));
    const wider = RADII[RADII.indexOf(state.radius) + 1];
    if (wider) {
      const widen = el("button", "button", `Widen to ${wider} miles`);
      widen.type = "button";
      widen.addEventListener("click", () => { state.radius = wider; render(); });
      box.append(widen);
    }
    els.status.replaceChildren(box);
  }

  function renderRegulars() {
    const max = Number(state.radius);
    const nearby = [];
    // Regular nights are mostly karaoke and open mics, so "Live music" shows them all too.
    const narrow = state.filter === "open" || state.filter === "karaoke";
    for (const rule of state.rules.values()) {
      const type = TYPES[rule.category];
      if (!type || (narrow && type.filter !== state.filter)) continue;
      const d = distanceTo(rule.venues.town);
      if (d != null && d <= max) nearby.push({ rule, d });
    }
    nearby.sort((a, b) => a.d - b.d || a.rule.day_of_week - b.rule.day_of_week || a.rule.title.localeCompare(b.rule.title));

    if (nearby.length === 0) {
      els.regulars.replaceChildren(el("li", "regulars-empty", state.error ? "Couldn't load." : "None in range yet."));
      return;
    }
    els.regulars.replaceChildren(...nearby.slice(0, MAX_REGULARS).map(({ rule }) => {
      const item = el("li");
      item.append(el("span", null, `${rule.title} · ${rule.venues.name}, ${rule.venues.town}`),
        el("span", "regulars-when", ruleWhen(rule)));
      return item;
    }));
  }

  // ---------- Events ----------
  els.town.addEventListener("change", () => {
    state.town = els.town.value;
    saveTown(state.town);
    render();
  });
  els.radius.addEventListener("change", () => { state.radius = els.radius.value; render(); });
  els.pills.addEventListener("click", (e) => {
    const button = e.target.closest(".pill");
    if (!button) return;
    state.filter = button.dataset.filter;
    render();
  });
  els.more.addEventListener("click", async () => {
    els.more.disabled = true;
    els.more.textContent = "Loading…";
    try {
      await loadWeek();
    } catch (err) {
      console.error(err);
    }
    els.more.disabled = false;
    render();
  });
  els.submit.addEventListener("click", () => { els.submitNote.hidden = false; });

  // ---------- Start ----------
  async function start() {
    const saved = savedTown();
    if (saved) state.town = saved;
    els.town.replaceChildren(new Option(state.town, state.town));
    renderPills();

    try {
      if (!CONFIG.supabaseUrl || !CONFIG.supabaseKey) throw new Error("config.js is missing");
      await Promise.all([loadTowns(), loadRules()]);
      await loadWeek();
    } catch (err) {
      console.error(err);
      state.error = true;
    }

    if (!state.towns.has(state.town) || state.towns.get(state.town).state !== "CT") state.town = DEFAULT_TOWN;
    if (state.towns.size) renderTownOptions();
    render();
  }

  start();
})();
