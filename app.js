const DEFAULT = ["https://bianet.org", "https://sendika.org", "https://yeniyasamgazetesi9.com",
  "https://mezopotamyaajansi45.com", "https://etha57.com", "https://medyascope.tv",
  "https://www.evrensel.net", "https://www.birgun.net", "https://www.agos.com.tr/tr", "https://anitsayac.com"];
const $ = selector => document.querySelector(selector);
const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"}[c]));
const host = value => { try { return new URL(value).hostname.replace(/^www\./, ""); } catch { return ""; } };
const hue = name => { let h = 0; for (const c of name) h = (h * 31 + c.charCodeAt(0)) % 360; return h; };
const hm = value => new Date(value * 1000).toLocaleTimeString("tr-TR", {hour:"2-digit", minute:"2-digit", second:"2-digit"});
const PAGE_SIZE = 200;
const POLLS = [5, 10, 15, 30, 60, 120, 300];
const BACKUP_KEY = "haberTakipMigrationBackup120";
let sound = false, audio, status = null, articles = [], total = 0, sel = null, query = "", unreadOnly = false;
let visibleLimit = PAGE_SIZE, generation = 0, articleGeneration = -1, articleRevision = null;
let refreshing = false, refreshAgain = false, imported = false, importData, connected = false, configBusy = false, ready = false;
let previousUnread = null, unseen = 0, messageKind = "", lastChips = "";
const pendingRead = new Set();

function notify(message, kind = "action") {
  messageKind = kind;
  $("#message").textContent = message;
}
function safeURL(value) {
  try {
    const url = new URL(value);
    if (!/^https?:$/.test(url.protocol) || url.username || url.password) return null;
    url.hash = "";
    return url.href;
  } catch { return null; }
}
function bridge() {
  const config = globalThis.HABER_BRIDGE;
  if (!config || !safeURL(config.url) || typeof config.token !== "string" || !config.token) {
    throw new Error("Haber Takip hizmet bağlantısı ayarlanmamış. Kurulum aracını çalıştırın.");
  }
  return config;
}
async function api(path, method = "GET", body) {
  if (!ready) throw new Error("Haber Takip bağlantısı hazırlanıyor. Biraz sonra yeniden deneyin.");
  const config = bridge(), controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 12000);
  try {
    const headers = {Authorization: `Bearer ${config.token}`, Accept: "application/json"};
    if (body !== undefined) headers["Content-Type"] = "application/json";
    let response;
    try {
      response = await fetch(new URL(path, config.url).href, {
        method, headers, body: body === undefined ? undefined : JSON.stringify(body),
        signal: controller.signal, credentials: "omit", cache: "no-store"
      });
    } catch (error) {
      if (error.name === "AbortError") throw new Error("Haber Takip hizmeti 12 saniyede yanıt vermedi. Hizmet bağlantısı yeniden denenecek.");
      throw new Error("Haber Takip hizmetine bağlanılamıyor. Yerel hizmetin çalıştığını kontrol edin; bağlantı yeniden denenecek.");
    }
    const text = await response.text();
    let result;
    try { result = text ? JSON.parse(text) : null; } catch { throw new Error("Haber Takip hizmetinden geçersiz yanıt alındı."); }
    if (!response.ok) {
      if (response.status === 401 || response.status === 403) throw new Error("Haber Takip hizmet bağlantısının anahtarı geçersiz. Kurulum aracını yeniden çalıştırın.");
      throw new Error(typeof result?.error === "string" ? result.error.slice(0, 250) : `Haber Takip hizmeti hata döndürdü (HTTP ${response.status}).`);
    }
    return result;
  } catch (error) {
    if (error.name === "AbortError") throw new Error("Haber Takip hizmeti 12 saniyede yanıt vermedi. Hizmet bağlantısı yeniden denenecek.");
    throw error;
  } finally { clearTimeout(timeout); }
}

function sourceStatus(source) {
  if (!source.error && !source.partialError) return "";
  const next = Number(source.next);
  const remaining = Number.isFinite(next) && next > 0 ? Math.max(0, Math.ceil((next - Date.now()) / 1000)) : 0;
  if (!source.error) return `Kısmi veri · ${remaining} sn sonra tekrar`;
  return `${Math.max(1, Number(source.errors) || 1)} hata · ${remaining} sn sonra tekrar`;
}
function chips() {
  const sources = Array.isArray(status?.sources) ? status.sources : [];
  const healthy = sources.filter(source => source.lastSuccess && !source.error && !source.partialError).length;
  $("#st").textContent = connected ? `${healthy}/${sources.length} kaynak erişilebilir` : "Hizmete bağlanılamıyor";
  $("#live").classList.toggle("off", !connected || healthy === 0);
  const html = sources.map(source => {
    const name = host(source.url), selected = sel === name;
    const color = source.error ? "var(--bad)" : source.partialError ? "#b57c00" : source.lastSuccess ? "var(--ok)" : "var(--mut)";
    const title = source.error ? String(source.error) : source.partialError ? `Ek içerik alınamadı: ${source.partialError}` : source.feed ? `RSS: ${source.feed}` : name;
    return `<span class="chip${selected ? " sel" : ""}" title="${esc(title)}"><i class="dot" style="background:${color}"></i>
      <button class="f" type="button" data-n="${esc(name)}" aria-pressed="${selected}">${esc(name)} <b>${Number(source.count) || 0}</b><small class="retry-status" data-source="${esc(source.url)}">${esc(sourceStatus(source))}</small></button>
      <button class="x" type="button" data-u="${esc(source.url)}" aria-label="${esc(name)} sitesini kaldır">×</button></span>`;
  }).join("");
  if (html !== lastChips) { $("#chips").innerHTML = html; lastChips = html; }
}
function clockText(item) {
  if (/^\d{4}-\d{2}-\d{2}$/.test(item.dateOnly || "")) {
    return new Date(item.dateOnly + "T00:00:00Z").toLocaleDateString("tr-TR", {day:"numeric", month:"short", timeZone:"UTC"});
  }
  return hm(item.a && Number.isFinite(item.seen) ? item.seen : item.t);
}
function clockExplanation(item) {
  if (item.dateOnly) return `Kaynak yalnızca yayın tarihini bildiriyor: ${item.dateOnly}. Yayın saati belirtilmemiş.`;
  if (!item.a) return "Kaynağın yayın saati · cihazınızın saat diliminde";
  return "Kaynakta doğrulanmış yayın saati yok. Gösterilen saat, bu kaydın takipte ilk görülme saatidir.";
}
function relativeTime(item) {
  if (item.dateOnly) return "saat belirtilmemiş";
  if (item.a) return "ilk görülme";
  const date = new Date(item.t * 1000), seconds = Date.now() / 1000 - item.t;
  if (date.toDateString() !== new Date().toDateString()) return date.toLocaleDateString("tr-TR", {day:"numeric", month:"short"});
  if (seconds < 0) return "yayın saati";
  return seconds < 5 ? "şimdi" : seconds < 60 ? Math.floor(seconds) + " sn önce" : seconds < 3600 ? Math.floor(seconds / 60) + " dk önce" : Math.floor(seconds / 3600) + " sa önce";
}
function updateCount() {
  $("#count").textContent = `${articles.length}/${total} haber · ${Number(status?.unread) || 0} okunmamış`;
  $("#more").hidden = articles.length >= total;
  $("#more").disabled = refreshing;
}
function render() {
  $("#list").innerHTML = articles.length ? articles.map(item => `<a class="row${item.f && !pendingRead.has(item.k) ? " new" : ""}" href="${esc(item.link)}" target="_blank" rel="noopener noreferrer" data-k="${esc(item.k)}">
    <span class="tm" title="${esc(clockExplanation(item))}">${clockText(item)}<span class="ago">${esc(relativeTime(item))}</span></span>
    <span><span class="sn" style="color:hsl(${hue(item.site)} 62% 46%)">${esc(item.site)}</span><br><span class="ti">${esc(item.title)}</span></span></a>`).join("")
    : `<div class="empty">${!connected ? "Haber hizmeti bağlantısı bekleniyor." : !status?.sites?.length ? "Başlamak için bir site veya RSS adresi ekleyin." : query || sel || unreadOnly ? "Bu filtrelerle eşleşen haber yok." : "Henüz haber yok."}</div>`;
  updateCount();
}
function tick() {
  const sources = new Map((status?.sources || []).map(source => [source.url, source]));
  document.querySelectorAll(".retry-status").forEach(element => { element.textContent = sourceStatus(sources.get(element.dataset.source) || {}); });
  const byKey = new Map(articles.map(item => [item.k, item]));
  document.querySelectorAll(".row").forEach(element => {
    const item = byKey.get(element.dataset.k);
    if (item) element.querySelector(".ago").textContent = relativeTime(item);
  });
}
function beep() {
  if (!sound) return;
  try {
    audio ||= new AudioContext(); audio.resume().catch(() => {});
    const oscillator = audio.createOscillator(), gain = audio.createGain();
    oscillator.connect(gain); gain.connect(audio.destination); oscillator.frequency.value = 880; gain.gain.value = .08;
    oscillator.onended = () => { oscillator.disconnect(); gain.disconnect(); };
    oscillator.start(); oscillator.stop(audio.currentTime + .12);
  } catch { }
}
function acceptStatus(value) {
  if (!value || !Array.isArray(value.sites) || !Array.isArray(value.sources) || value.revision === undefined) throw new Error("Haber hizmetinin durum yanıtı eksik.");
  status = value; connected = true;
  if (!configBusy && POLLS.includes(value.poll)) $("#iv").value = value.poll;
  if (sel && !value.sites.some(url => host(url) === sel)) { sel = null; generation++; visibleLimit = PAGE_SIZE; }
  const unread = Number(value.unread) || 0;
  if (previousUnread !== null && unread > previousUnread) {
    beep();
    if (document.hidden) { unseen += unread - previousUnread; document.title = `(${unseen}) Haber Takip 1.2.0`; }
  }
  previousUnread = unread;
  chips(); updateCount();
}
async function refresh() {
  if (!ready) return;
  if (refreshing) { refreshAgain = true; return; }
  refreshing = true; $("#more").disabled = true;
  try {
    if (!imported) { await api("/api/import", "POST", importData); imported = true; }
    acceptStatus(await api("/api/status"));
    if (messageKind === "connection") notify("");
    const currentGeneration = generation;
    if (articleGeneration !== currentGeneration || articleRevision !== status.revision) {
      const filter = {query, sel, unreadOnly}, limit = visibleLimit, loaded = [], keys = new Set();
      let offset = 0, available = 0, revision, consistent = true;
      do {
        const params = new URLSearchParams({query:filter.query, offset:String(offset), limit:String(Math.min(PAGE_SIZE, limit - offset))});
        if (filter.sel) params.set("site", filter.sel);
        if (filter.unreadOnly) params.set("unread", "1");
        const page = await api("/api/articles?" + params);
        if (currentGeneration !== generation) return;
        if (!page || !Array.isArray(page.articles) || !Number.isFinite(page.total) || page.revision === undefined) throw new Error("Haber hizmetinin haber yanıtı eksik.");
        if (offset === 0) revision = page.revision;
        else if (revision !== page.revision) consistent = false;
        available = Math.max(0, page.total);
        for (const item of page.articles) {
          if (!item || typeof item.k !== "string" || typeof item.site !== "string" || typeof item.title !== "string" || !safeURL(item.link) || !Number.isFinite(item.t) || keys.has(item.k)) continue;
          keys.add(item.k); loaded.push(item);
        }
        offset += page.articles.length;
        if (!page.articles.length) break;
      } while (offset < limit && offset < available);
      if (currentGeneration !== generation) return;
      articles = loaded; total = available; articleGeneration = currentGeneration; articleRevision = consistent ? revision : null;
      render();
    }
  } catch (error) {
    connected = false; chips();
    notify(error.message || "Haber Takip hizmetine bağlanılamıyor.", "connection");
    if (!articles.length) render();
  } finally {
    refreshing = false; updateCount();
    if (refreshAgain) { refreshAgain = false; setTimeout(refresh, 0); }
  }
}
function invalidate(reset = false) {
  generation++;
  if (reset) visibleLimit = PAGE_SIZE;
  refresh();
}
async function markRead(event) {
  if (event.button > 1) return;
  const row = event.target.closest(".row"), key = row?.dataset.k;
  if (!key || pendingRead.has(key)) return;
  pendingRead.add(key); row.classList.remove("new");
  try { await api("/api/read", "POST", {keys:[key]}); invalidate(); }
  catch (error) { notify(error.message); invalidate(); }
  finally { pendingRead.delete(key); }
}
$("#list").addEventListener("click", markRead);
$("#list").addEventListener("auxclick", markRead);
$("#rd").onclick = async event => {
  const button = event.currentTarget; button.disabled = true;
  try { await api("/api/read", "POST", {before:Date.now() / 1000}); invalidate(); }
  catch (error) { notify(error.message); }
  finally { button.disabled = false; }
};
$("#snd").onclick = async () => {
  sound = !sound; setSoundButton(); beep();
  try { await chrome.storage.local.set({sound}); } catch { notify("Ses tercihi kaydedilemedi."); }
};
function setSoundButton() {
  $("#snd").textContent = sound ? "Ses açık" : "Ses kapalı";
  $("#snd").classList.toggle("on", sound); $("#snd").setAttribute("aria-pressed", String(sound));
}
$("#iv").onchange = async event => {
  const poll = Number(event.target.value); if (!POLLS.includes(poll)) return;
  configBusy = true; event.target.disabled = true;
  try { await api("/api/config", "PATCH", {poll}); refresh(); }
  catch (error) { notify(error.message); if (status) $("#iv").value = status.poll; }
  finally { configBusy = false; $("#iv").disabled = false; }
};
$("#chips").onclick = async event => {
  const remove = event.target.closest(".x"), filter = event.target.closest(".f");
  if (remove) {
    const url = remove.dataset.u;
    if (!confirm(host(url) + " kaldırılsın mı?")) return;
    remove.disabled = true;
    try {
      await api("/api/sources", "DELETE", {url});
      if (sel === host(url)) sel = null;
      invalidate(true);
    } catch (error) { notify(error.message); remove.disabled = false; }
  } else if (filter) {
    sel = sel === filter.dataset.n ? null : filter.dataset.n;
    chips(); invalidate(true);
  }
};
$("#f").onsubmit = async event => {
  event.preventDefault();
  let value = $("#dm").value.trim(); if (!value) return;
  if (!/^[a-z][a-z0-9+.-]*:/i.test(value)) value = "https://" + value;
  const url = safeURL(value);
  if (!url) { notify("Geçerli bir HTTP veya HTTPS adresi girin."); return; }
  const button = $("#f button"); button.disabled = true;
  try {
    await api("/api/sources", "POST", {url}); $("#dm").value = "";
    notify("Kaynak eklendi."); invalidate();
  } catch (error) { notify(error.message); }
  finally { button.disabled = false; }
};
$("#search").oninput = event => { query = event.target.value.trim().toLocaleLowerCase("tr-TR"); invalidate(true); };
$("#unread").onclick = event => {
  unreadOnly = !unreadOnly; event.currentTarget.classList.toggle("on", unreadOnly);
  event.currentTarget.setAttribute("aria-pressed", String(unreadOnly)); invalidate(true);
};
$("#more").onclick = () => { visibleLimit += PAGE_SIZE; invalidate(); };
document.addEventListener("visibilitychange", () => {
  if (!document.hidden) { unseen = 0; document.title = "Haber Takip 1.2.0"; refresh(); }
});
window.addEventListener("online", refresh);

(async () => {
  const stored = await chrome.storage.local.get(["sites", "feeds", "poll", "articles", "dates", "lastVisit", "prev", "sound", BACKUP_KEY]);
  sound = !!stored.sound; setSoundButton();
  importData = {
    sites: Array.isArray(stored.sites) ? stored.sites : DEFAULT,
    feeds: stored.feeds || {}, poll: POLLS.includes(stored.poll) ? stored.poll : 60,
    articles: Array.isArray(stored.articles) ? stored.articles : [], dates: stored.dates || {},
    prev: stored.lastVisit || stored.prev || Date.now()
  };
  if (!stored[BACKUP_KEY]) {
    await chrome.storage.local.set({[BACKUP_KEY]: {createdAt:new Date().toISOString(), data:importData}});
  }
  ready = true;
  await refresh();
  setInterval(refresh, 2000); setInterval(tick, 1000);
})().catch(error => { notify("Uygulama başlatılamadı: " + (error.message || "Yerel kayıtlar okunamadı."), "connection"); });
