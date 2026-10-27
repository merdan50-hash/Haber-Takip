// Haber Takip motoru: sitelerin RSS/Atom akışlarını (yoksa ana sayfadaki haber bağlantılarını) bulur,
// tarar ve kayıtları chrome.storage.local'da tutar. Eklentinin arka plan çalışanında çalışır;
// testler için Node.js'te de yüklenebilir (DOM kullanmaz).
"use strict";

const POLLS = [5, 10, 15, 30, 60, 120, 300];
const STATE_KEY = "durum";
const MAX_ARTICLES = 5000;
const KEEP_SECONDS = 30 * 24 * 3600;
const MAX_PER_SCAN = 150;
const MAX_BACKOFF = 1800;
const MAX_DOWNLOAD = 8 * 1024 * 1024;
const FETCH_TIMEOUT = 20000;
const PARALLEL_SCANS = 4;
const FEED_PATHS = ["/feed", "/rss", "/rss.xml", "/feed.xml", "/atom.xml", "/index.xml"];
const FEED_ACCEPT = "application/rss+xml, application/atom+xml, application/xml, text/xml, text/html;q=0.9, */*;q=0.5";

// --- Yardımcılar --------------------------------------------------------------

const hostOf = value => {
  try { return new URL(value).hostname.replace(/^www\./, ""); } catch { return ""; }
};
const trLower = text => String(text).toLocaleLowerCase("tr-TR");

function normalizeUrl(value, base) {
  try {
    const url = new URL(String(value).trim(), base);
    if (!/^https?:$/.test(url.protocol) || url.username || url.password) return null;
    url.hash = "";
    return url.href;
  } catch { return null; }
}

const ENTITIES = {
  amp: "&", lt: "<", gt: ">", quot: '"', apos: "'", nbsp: " ", rsquo: "’", lsquo: "‘", rdquo: "”", ldquo: "“",
  hellip: "…", ndash: "–", mdash: "—", laquo: "«", raquo: "»", ccedil: "ç", Ccedil: "Ç", ouml: "ö", Ouml: "Ö",
  uuml: "ü", Uuml: "Ü", acirc: "â", Acirc: "Â", icirc: "î", Icirc: "Î", ucirc: "û", Ucirc: "Û", eacute: "é", bull: "•",
  middot: "·", copy: "©", reg: "®", deg: "°", euro: "€", trade: "™", prime: "′", Prime: "″", shy: "",
};

function decodeEntities(text) {
  return String(text).replace(/&(#x[0-9a-f]+|#\d+|[a-z]+);/gi, (match, name) => {
    if (name[0] === "#") {
      const code = name[1].toLowerCase() === "x" ? parseInt(name.slice(2), 16) : parseInt(name.slice(1), 10);
      try { return String.fromCodePoint(code); } catch { return match; }
    }
    return Object.prototype.hasOwnProperty.call(ENTITIES, name) ? ENTITIES[name] : match;
  });
}

function cleanText(value) {
  const text = String(value || "").replace(/^\s*<!\[CDATA\[([\s\S]*?)\]\]>\s*$/, "$1");
  // Bazı akışlar başlıktaki HTML'yi ikinci kez kodlar ("&lt;b&gt;"); çözdükten sonra kalan etiketleri de temizle.
  return decodeEntities(text.replace(/<[^>]+>/g, " ")).replace(/<\/?[a-z][^>]*>/gi, " ").replace(/\s+/g, " ").trim();
}

function attributes(tag) {
  const result = {};
  for (const [, name, double, single, bare] of tag.matchAll(/([\w:-]+)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))/g)) {
    result[name.toLowerCase()] = decodeEntities(double ?? single ?? bare ?? "");
  }
  return result;
}

// --- Tarih --------------------------------------------------------------------

function parseDate(value) {
  value = String(value || "").trim();
  if (!value) return {t: null, dateOnly: null};
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    const t = Date.parse(value + "T00:00:00Z");
    return Number.isFinite(t) ? {t: t / 1000, dateOnly: value} : {t: null, dateOnly: null};
  }
  const t = Date.parse(value.replace(/([+-]\d{2})(\d{2})$/, "$1:$2").replace(/^(\d{4}-\d{2}-\d{2}) /, "$1T"));
  const fallback = Date.parse(value);
  const stamp = Number.isFinite(t) ? t : fallback;
  return Number.isFinite(stamp) ? {t: stamp / 1000, dateOnly: null} : {t: null, dateOnly: null};
}

// --- Akış ve sayfa ayrıştırma ---------------------------------------------------

function looksLikeFeed(text) {
  const head = String(text).replace(/^﻿/, "").trimStart().slice(0, 2000).toLowerCase();
  if (/^<!doctype html|^<html/.test(head)) return false;
  return /^(<\?xml[^>]*>\s*)?(<!--[\s\S]*?-->\s*|<\?[^>]*>\s*)*<(rss|feed|rdf:rdf)\b/.test(head);
}

function field(block, names) {
  for (const name of names) {
    const match = block.match(new RegExp(`<${name}\\b[^>]*>([\\s\\S]*?)</${name}>`, "i"));
    if (match) return match[1];
  }
  return null;
}

function parseFeed(text, base) {
  const result = [];
  for (const [block] of String(text).matchAll(/<(item|entry)\b[\s\S]*?<\/\1>/gi)) {
    let link = null;
    for (const [tag] of block.matchAll(/<link\b[^>]*>/gi)) {
      const attrs = attributes(tag);
      if (attrs.href && (!attrs.rel || attrs.rel === "alternate")) { link = attrs.href; break; }
    }
    if (!link) link = cleanText(field(block, ["link"]) || "") || null;
    if (!link) {
      const guid = block.match(/<guid\b([^>]*)>([\s\S]*?)<\/guid>/i);
      if (guid && !/ispermalink\s*=\s*["']false/i.test(guid[1])) link = cleanText(guid[2]);
    }
    const title = cleanText(field(block, ["title"]) || "");
    const url = link ? normalizeUrl(decodeEntities(link), base) : null;
    if (url && title) {
      result.push({title: title.slice(0, 500), link: url,
        date: cleanText(field(block, ["pubDate", "dc:date", "published", "updated", "issued"]) || "")});
    }
  }
  return result;
}

function parsePage(html, base) {
  const text = String(html).replace(/<(script|style|noscript|template)\b[\s\S]*?<\/\1>/gi, " ");
  const feeds = [], links = [];
  for (const [tag] of text.matchAll(/<link\b[^>]*>/gi)) {
    const attrs = attributes(tag);
    if (/\balternate\b/i.test(attrs.rel || "") && /^application\/(rss|atom)\+xml$/i.test(attrs.type || "") && attrs.href) {
      feeds.push(attrs.href);
    }
  }
  for (const [, attrText, inner] of text.matchAll(/<a\b([^>]*)>([\s\S]*?)<\/a>/gi)) {
    links.push({href: attributes(attrText).href, text: inner});
  }
  return {feeds, links};
}

// RSS'i olmayan siteler için ana sayfadaki haber başlığına benzeyen bağlantılar.
function pageHeadlines(page, base) {
  const site = hostOf(base), seen = new Set(), result = [];
  for (const {href, text} of page.links) {
    const link = href ? normalizeUrl(href, base) : null;
    // Ana sayfalardaki "15:14 Başlık" biçimindeki saat önekini başlıktan ayıkla.
    const title = cleanText(text).replace(/^\d{1,2}[:.]\d{2}\s+/, "");
    if (!link || seen.has(link) || title.length < 25 || title.length > 300) continue;
    const path = new URL(link).pathname;
    if (!hostOf(link).endsWith(site) || path.length < 8 || !/[-_]|\d/.test(path)) continue;
    seen.add(link);
    result.push({title, link, date: null});
  }
  return result;
}

// --- İndirme ------------------------------------------------------------------

function decodeBody(buffer, contentType) {
  const bytes = new Uint8Array(buffer);
  const head = new TextDecoder("latin1").decode(bytes.subarray(0, 4096));
  const match = /charset=["']?([\w-]+)/i.exec(contentType || "") || /<\?xml[^>]+encoding=["']([\w-]+)/i.exec(head) ||
    /<meta[^>]+charset=["']?([\w-]+)/i.exec(head);
  try { return new TextDecoder(match ? match[1] : "utf-8").decode(bytes); }
  catch { return new TextDecoder("utf-8").decode(bytes); }
}

async function fetchText(url, timeout = FETCH_TIMEOUT) {
  let response;
  try {
    response = await fetch(url, {headers: {Accept: FEED_ACCEPT}, credentials: "omit", cache: "no-store",
      redirect: "follow", signal: AbortSignal.timeout(timeout)});
  } catch (error) {
    throw new Error(error && error.name === "TimeoutError" ? "Site zamanında yanıt vermedi." : "Siteye bağlanılamadı.");
  }
  if (!response.ok) throw new Error(`Site HTTP ${response.status} yanıtı verdi.`);
  const buffer = await response.arrayBuffer();
  if (buffer.byteLength > MAX_DOWNLOAD) throw new Error("Sayfa çok büyük.");
  return {text: decodeBody(buffer, response.headers.get("content-type")), url: response.url || url};
}

async function articleKey(link) {
  const digest = await crypto.subtle.digest("SHA-1", new TextEncoder().encode(link));
  return Array.from(new Uint8Array(digest).slice(0, 10), byte => byte.toString(16).padStart(2, "0")).join("");
}

// --- Motor --------------------------------------------------------------------

class Engine {
  constructor(storage, fetcher = fetchText, clock = () => Date.now() / 1000) {
    this.storage = storage;
    this.fetch = fetcher;
    this.now = clock;
    this.busy = new Set();
    this.inflight = new Set();
    this.loaded = null;
    this.saveTimer = null;
  }

  load() {
    this.loaded ||= this.storage.get(STATE_KEY).then(stored => {
      const state = stored[STATE_KEY] || {};
      this.state = {imported: false, poll: 60, sites: [], articles: {}, runtime: {}, revision: 1, ...state};
    });
    return this.loaded;
  }

  changed() {
    this.state.revision += 1;
    clearTimeout(this.saveTimer);
    this.saveTimer = setTimeout(() => this.save(), 500);
  }

  async save() {
    clearTimeout(this.saveTimer);
    await this.storage.set({[STATE_KEY]: this.state});
  }

  runtime(url) {
    return this.state.runtime[url] ||= {lastSuccess: null, error: null, errors: 0, due: 0};
  }

  sortKey(item) {
    if (item.a) return item.seen;
    return item.dateOnly ? item.t : Math.min(item.t, item.seen);
  }

  unread() {
    let count = 0;
    for (const item of Object.values(this.state.articles)) if (item.f) count++;
    return count;
  }

  // --- İstekler (eklenti sayfası chrome.runtime.sendMessage ile çağırır) ---

  async handle({path, method = "GET", body = {}}) {
    await this.load();
    const [route, query = ""] = String(path).split("?");
    const key = `${method} ${route}`;
    switch (key) {
      case "GET /api/status": return this.status();
      case "GET /api/articles": return this.articles(new URLSearchParams(query));
      case "POST /api/import": return this.importLegacy(body || {});
      case "POST /api/sources": return this.addSource(body || {});
      case "DELETE /api/sources": return this.removeSource(body || {});
      case "POST /api/read": return this.markRead(body || {});
      case "PATCH /api/config": return this.config(body || {});
      default: throw new Error("Bilinmeyen istek.");
    }
  }

  status() {
    const counts = {};
    for (const item of Object.values(this.state.articles)) counts[item.src] = (counts[item.src] || 0) + 1;
    const sources = this.state.sites.map(site => {
      const state = this.runtime(site.url);
      return {url: site.url, feed: site.feed || null, count: counts[site.url] || 0, lastSuccess: state.lastSuccess,
        error: state.error, partialError: null, errors: state.errors, next: state.error ? Math.round(state.due * 1000) : null};
    });
    return {sites: this.state.sites.map(site => site.url), sources, revision: this.state.revision,
      poll: this.state.poll, unread: this.unread(), update: this.state.update || null};
  }

  articles(params) {
    const query = trLower((params.get("query") || "").trim()), site = params.get("site") || "";
    const unread = params.get("unread") === "1";
    const offset = Math.max(0, parseInt(params.get("offset"), 10) || 0);
    const limit = Math.min(500, Math.max(1, parseInt(params.get("limit"), 10) || 200));
    const found = Object.values(this.state.articles).filter(item =>
      (!site || item.site === site) && (!unread || item.f) &&
      (!query || trLower(item.title).includes(query) || item.site.includes(query)));
    found.sort((a, b) => this.sortKey(b) - this.sortKey(a));
    return {articles: found.slice(offset, offset + limit).map(({src, ...item}) => item), total: found.length,
      revision: this.state.revision};
  }

  addSite(url, feed = null) {
    if (this.state.sites.some(site => hostOf(site.url) === hostOf(url))) return false;
    this.state.sites.push({url, feed, scanned: false});
    this.runtime(url);
    this.changed();
    return true;
  }

  // 1.x sürümünün tarayıcıda sakladığı site listesini yalnızca ilk açılışta aktarır.
  async importLegacy(body) {
    if (this.state.imported) return {ok: true, imported: false};
    const feeds = body.feeds && typeof body.feeds === "object" ? body.feeds : {};
    for (const value of Array.isArray(body.sites) ? body.sites : []) {
      const url = typeof value === "string" ? normalizeUrl(value) : null;
      if (url) this.addSite(url, typeof feeds[value] === "string" ? normalizeUrl(feeds[value]) : null);
    }
    if (POLLS.includes(body.poll)) this.state.poll = body.poll;
    this.state.imported = true;
    this.changed();
    await this.save();
    return {ok: true, imported: true};
  }

  async addSource(body) {
    const url = typeof body.url === "string" ? normalizeUrl(body.url) : null;
    if (!url) throw new Error("Geçerli bir HTTP veya HTTPS adresi girin.");
    if (!this.addSite(url)) throw new Error(`${hostOf(url)} zaten ekli.`);
    await this.save();
    this.start(this.state.sites[this.state.sites.length - 1]); // yeni kaynağı sırasını beklemeden hemen tara
    return {ok: true};
  }

  async removeSource(body) {
    const before = this.state.sites.length;
    this.state.sites = this.state.sites.filter(site => site.url !== body.url);
    if (this.state.sites.length === before) throw new Error("Kaynak bulunamadı.");
    delete this.state.runtime[body.url];
    for (const [key, item] of Object.entries(this.state.articles)) if (item.src === body.url) delete this.state.articles[key];
    this.changed();
    await this.save();
    return {ok: true};
  }

  async markRead(body) {
    let changed = 0;
    if (Array.isArray(body.keys)) {
      for (const key of body.keys.slice(0, 5000)) {
        const item = this.state.articles[key];
        if (item && item.f) { item.f = false; changed++; }
      }
    } else if (Number.isFinite(body.before)) {
      for (const item of Object.values(this.state.articles)) {
        if (item.f && this.sortKey(item) <= body.before) { item.f = false; changed++; }
      }
    } else {
      throw new Error("Okundu bilgisi eksik.");
    }
    if (changed) { this.changed(); await this.save(); }
    return {ok: true, changed};
  }

  async config(body) {
    if (!POLLS.includes(body.poll)) throw new Error("Geçersiz tarama aralığı.");
    this.state.poll = body.poll;
    const now = this.now();
    for (const state of Object.values(this.state.runtime)) if (!state.error) state.due = Math.min(state.due, now + body.poll);
    this.changed();
    await this.save();
    return {ok: true};
  }

  // --- Tarama ---

  // Zamanı gelen kaynakları (aynı anda en çok PARALLEL_SCANS tane) taramaya başlar ve bitmelerini bekler.
  // Her kaynak bağımsız taranır; yavaş bir site diğerlerini bekletmez. Bir şey değiştiyse true döndürür.
  async tick() {
    await this.load();
    const now = this.now();
    const due = this.state.sites.filter(site => !this.busy.has(site.url) && this.runtime(site.url).due <= now)
      .slice(0, Math.max(0, PARALLEL_SCANS - this.busy.size));
    if (!due.length) return false;
    const revision = this.state.revision;
    await Promise.all(due.map(site => this.start(site)));
    await this.save();
    return this.state.revision !== revision;
  }

  start(site) {
    const scan = this.scan(site).finally(() => this.inflight.delete(scan));
    this.inflight.add(scan);
    return scan;
  }

  // Süren bütün taramaların bitmesini bekler (testler ve kapanış için).
  async idle() {
    while (this.inflight.size) await Promise.all([...this.inflight]);
    await this.save();
  }

  async discover(url) {
    const page = await this.fetch(url);
    if (looksLikeFeed(page.text)) return {feed: url, items: parseFeed(page.text, page.url)};
    const parsed = parsePage(page.text, page.url);
    const root = new URL(page.url).origin;
    const candidates = [...new Set([...parsed.feeds.map(href => normalizeUrl(href, page.url)), ...FEED_PATHS.map(path => root + path)]
      .filter(Boolean))];
    for (const candidate of candidates) {
      try {
        const feed = await this.fetch(candidate, 12000);
        if (!looksLikeFeed(feed.text)) continue;
        const items = parseFeed(feed.text, feed.url);
        if (items.length) return {feed: candidate, items};
      } catch { /* sonraki adayı dene */ }
    }
    return {feed: null, items: pageHeadlines(parsed, page.url)};
  }

  async scan(site) {
    const url = site.url;
    this.busy.add(url);
    let feed = site.feed || null, items = [], error = null;
    try {
      if (feed) {
        try {
          const response = await this.fetch(feed);
          if (!looksLikeFeed(response.text)) throw new Error("RSS adresi artık akış döndürmüyor.");
          items = parseFeed(response.text, response.url);
        } catch (failure) {
          if (this.runtime(url).errors < 2) throw failure;
          ({feed, items} = await this.discover(url)); // akış birkaç kez başarısızsa yeniden ara
        }
      } else {
        ({feed, items} = await this.discover(url));
      }
      if (!items.length) throw new Error("Sitede haber bulunamadı. RSS adresini doğrudan eklemeyi deneyin.");
    } catch (failure) {
      error = failure && failure.message ? failure.message : "Site okunamadı.";
    } finally {
      this.busy.delete(url);
    }
    await this.finish(url, feed, items, error);
  }

  async finish(url, feed, items, error) {
    const site = this.state.sites.find(entry => entry.url === url);
    if (!site) return; // tarama sürerken kaynak kaldırıldı
    const state = this.runtime(url), now = this.now(), poll = this.state.poll;
    if (error) {
      state.errors += 1;
      state.error = error;
      state.due = now + Math.min(MAX_BACKOFF, Math.max(poll, 15 * 2 ** (state.errors - 1)));
      this.changed();
      return;
    }
    Object.assign(state, {error: null, errors: 0, lastSuccess: now, due: now + poll});
    site.feed = feed;
    const baseline = !site.scanned; // ilk taramadaki haberler "yeni" sayılmaz
    site.scanned = true;
    const name = hostOf(url), articles = this.state.articles;
    let added = 0;
    for (const item of items.slice(0, MAX_PER_SCAN)) {
      const key = await articleKey(item.link);
      const existing = articles[key];
      if (existing) {
        if (existing.title !== item.title) { existing.title = item.title; added++; }
        continue;
      }
      const {t, dateOnly} = parseDate(item.date);
      articles[key] = {k: key, src: url, site: name, title: item.title, link: item.link, t: t ?? now, seen: now,
        a: t === null, dateOnly, f: !baseline};
      added++;
    }
    if (added) this.prune();
    this.changed();
  }

  prune() {
    const articles = this.state.articles, limit = this.now() - KEEP_SECONDS;
    for (const [key, item] of Object.entries(articles)) if (item.seen < limit && !item.f) delete articles[key];
    const values = Object.values(articles);
    if (values.length > MAX_ARTICLES) {
      values.sort((a, b) => this.sortKey(a) - this.sortKey(b));
      for (const item of values.slice(0, values.length - MAX_ARTICLES)) delete articles[item.k];
    }
  }
}

if (typeof module !== "undefined") {
  module.exports = {Engine, parseFeed, parsePage, pageHeadlines, parseDate, looksLikeFeed, decodeEntities, cleanText,
    normalizeUrl, decodeBody, hostOf, POLLS, STATE_KEY};
}
