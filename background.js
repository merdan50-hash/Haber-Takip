const APP_URL = () => chrome.runtime.getURL("app.html");

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

// Otomatik güncellemeyle yeniden yüklenince kapanan uygulama sekmesini geri açar.
// runtime.reload() her zaman onInstalled olayı üretmediği için servis çalışanı her başladığında denetlenir.
(async () => {
  const {reopenApp} = await chrome.storage.local.get("reopenApp");
  if (!reopenApp) return;
  await chrome.storage.local.remove("reopenApp");
  await chrome.tabs.create({url: APP_URL(), active: reopenApp === "active"});
})().catch(error => console.warn("Uygulama sekmesi yeniden açılamadı:", error));
