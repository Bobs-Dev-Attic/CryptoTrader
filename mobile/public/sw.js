/* CryptoTrader service worker: receives Web Push and shows notifications. */
self.addEventListener("push", (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch (e) {
    data = { title: "CryptoTrader", body: event.data ? event.data.text() : "" };
  }
  const title = data.title || "CryptoTrader alert";
  const options = {
    body: data.body || "",
    data: { url: data.url || "/alerts" },
    tag: data.tag || undefined,
    badge: undefined,
    icon: undefined,
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || "/alerts";
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clientList) => {
      for (const client of clientList) {
        if ("focus" in client) {
          client.navigate && client.navigate(url);
          return client.focus();
        }
      }
      if (self.clients.openWindow) return self.clients.openWindow(url);
    })
  );
});
