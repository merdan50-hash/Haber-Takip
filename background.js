importScripts("motor.js");

const APP_URL = () => chrome.runtime.getURL("app.html");
const RELEASES = "https://api.github.com/repos/merdan50-hash/Haber-Takip/releases/latest";
const engine = new Engine(chrome.storage.local);

// Okunmamış haber sayısını araç çubuğu simgesinde gösterir.
async function updateBadge() {
  const unread = engine.unread();
  await chrome.action.setBadgeText({text: unread ? (unread > 999 ? "999+" : String(unread)) : ""});
  await chrome.action.setBadgeBackgroundColor({color: "#d23b3b"});
}

// Sayfa açıkken her istekte, kapalıyken alarmla çağrılır; zaten taranan kaynakları motor atlar.
function tick() {
  return engine.tick().then(changed => changed && updateBadge()).catch(error => console.warn("Tarama hatası:", error));
}

function newer(a, b) {
  const x = String(a).split(".").map(Number), y = String(b).split(".").map(Number);
  for (let i = 0; i < Math.max(x.length, y.length); i++) {
    if ((x[i] || 0) !== (y[i] || 0)) return (x[i] || 0) > (y[i] || 0);
  }
  return false;
}

// GitHub'da yeni sürüm varsa uygulama sayfası indirme bağlantısını gösterir.
// Mağazadan yüklenen eklentiyi tarayıcı kendisi güncellediği için (manifest'e update_url eklenir) denetim yapılmaz.
async function checkUpdate() {
  if (chrome.runtime.getManifest().update_url) return;
  try {
    const response = await fetch(RELEASES, {headers: {Accept: "application/vnd.github+json"}, credentials: "omit",
      signal: AbortSignal.timeout(20000)});
    if (!response.ok) return;
    const release = await response.json();
    const latest = String(release.tag_name || "").replace(/^v/i, "");
    await engine.load();
    engine.state.update = newer(latest, chrome.runtime.getManifest().version)
      ? {latest, url: release.html_url || "https://github.com/merdan50-hash/Haber-Takip/releases/latest"} : null;
    engine.changed();
    await engine.save();
  } catch (error) {
    console.warn("Sürüm denetlenemedi:", error);
  }
}

chrome.runtime.onInstalled.addListener(() => {
  chrome.alarms.create("tara", {periodInMinutes: 0.5});
  chrome.alarms.create("surum", {delayInMinutes: 1, periodInMinutes: 360});
});
chrome.runtime.onStartup.addListener(() => {
  chrome.alarms.create("tara", {periodInMinutes: 0.5});
  tick();
});
chrome.alarms.onAlarm.addListener(alarm => {
  if (alarm.name === "tara") tick();
  if (alarm.name === "surum") checkUpdate();
});

chrome.runtime.onMessage.addListener((message, sender, reply) => {
  if (sender.id !== chrome.runtime.id || !message || typeof message.path !== "string") return false;
  engine.handle(message).then(result => {
    reply({ok: true, result});
    if (message.method && message.method !== "GET") engine.idle().then(updateBadge, () => {});
  }, error => reply({ok: false, error: error && error.message ? error.message : "Beklenmeyen hata."}));
  tick();
  return true;
});

// Uygulama sekmesi zaten açıksa onu öne getirir, değilse yeni sekmede açar.
// chrome.runtime.getContexts "tabs" izni istemeden eklentinin kendi sayfalarını bulur.
chrome.action.onClicked.addListener(async () => {
  const url = APP_URL();
  try {
    const [context] = await chrome.runtime.getContexts({contextTypes: ["TAB"], documentUrls: [url]});
    if (context && context.tabId >= 0) {
      await chrome.tabs.update(context.tabId, {active: true});
      if (context.windowId >= 0) await chrome.windows.update(context.windowId, {focused: true});
      return;
    }
  } catch (error) {
    console.warn("Açık Haber Takip sekmesi bulunamadı:", error);
  }
  await chrome.tabs.create({url});
});
