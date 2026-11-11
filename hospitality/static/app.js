/* Maison Sanaa — accessible guest ordering and staff demo interfaces */
"use strict";
const $ = id => document.getElementById(id);
const fmt = amount => "KSh " + new Intl.NumberFormat("en-KE", {maximumFractionDigits:0}).format(Number(amount || 0));
const node = (tag, className, content) => {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (content !== undefined && content !== null) element.textContent = String(content);
  return element;
};
function detailMessage(value) {
  if (typeof value === "string") return value;
  if (Array.isArray(value)) return value.map(detailMessage).join("; ");
  return "Please check your details and try again.";
}
async function api(url, options) {
  const response = await fetch(url, Object.assign({credentials:"same-origin",cache:"no-store"}, options || {}));
  let payload;
  try { payload = await response.json(); } catch { payload = {}; }
  if (!response.ok) throw new Error(detailMessage(payload.detail || "Request failed (" + response.status + ")"));
  return payload;
}
function jsonOptions(data) {
  return {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(data)};
}
const navButton = $("nav-toggle");
if (navButton) navButton.addEventListener("click", () => {
  const open = $("primary-nav").classList.toggle("open");
  navButton.setAttribute("aria-expanded", String(open));
  navButton.textContent = open ? "Close ✕" : "Menu ☰";
});
if ("serviceWorker" in navigator) window.addEventListener("load", () => {
  navigator.serviceWorker.register("/sw.js").catch(() => {});
});
let installPrompt = null;
window.addEventListener("beforeinstallprompt", event => {
  event.preventDefault();
  installPrompt = event;
  if ($("install-btn")) $("install-btn").hidden = false;
});
if ($("install-btn")) $("install-btn").addEventListener("click", async () => {
  if (!installPrompt) return;
  installPrompt.prompt();
  await installPrompt.userChoice;
  installPrompt = null;
  $("install-btn").hidden = true;
});

if (document.body.classList.contains("ordering-page")) initOrderApp();
if (document.body.classList.contains("staff-page")) initStaffApp();

function initOrderApp() {
  let products = [];
  let category = "All";
  let search = "";
  let cart = {};
  let lastOrderCode = "";
  try {
    const stored = JSON.parse(localStorage.getItem("maison-cart-v1") || "{}");
    if (stored && typeof stored === "object" && !Array.isArray(stored)) {
      Object.keys(stored).forEach(id => {
        const count = Number(stored[id]);
        if (Number.isInteger(count) && count >= 1 && count <= 10) cart[id] = count;
      });
    }
  } catch {}
  const grid = $("menu-grid"), categories = $("categories"), cartItems = $("cart-items");
  const error = $("menu-error"), checkoutError = $("checkout-error");
  function saveCart() {
    try { localStorage.setItem("maison-cart-v1", JSON.stringify(cart)); } catch {}
  }
  function itemsInCart() { return Object.values(cart).reduce((sum, q) => sum + q, 0); }
  function total() {
    return products.reduce((sum, p) => sum + (cart[p.id] || 0) * p.price, 0);
  }
  function showError(element, message) {
    element.textContent = message;
    element.hidden = !message;
  }
  function setQuantity(id, qty) {
    if (qty <= 0) delete cart[id];
    else cart[id] = Math.min(10, qty);
    saveCart(); renderCart();
  }
  function renderCategories() {
    categories.replaceChildren();
    ["All", "Breakfast", "Mains", "Desserts", "Cold drinks", "Hot drinks"].forEach(name => {
      const button = node("button", name === category ? "active" : "", name);
      button.type = "button";
      button.setAttribute("aria-pressed", String(name === category));
      button.addEventListener("click", () => {
        category = name;
        renderCategories();
        renderMenu();
      });
      categories.append(button);
    });
  }
  function renderMenu() {
    const matching = products.filter(p => (category === "All" || p.category === category) &&
      (p.name + " " + p.description + " " + p.category).toLowerCase().includes(search));
    grid.replaceChildren();
    $("menu-heading").textContent = category === "All" ? "Explore our menu" : category;
    $("menu-count").textContent = matching.length + " items";
    if (!matching.length) {
      grid.append(node("p", "muted", "Nothing matches your search. Try another category or dish."));
      return;
    }
    matching.forEach(p => {
      const card = node("article", "menu-card");
      const photo = node("img", "menu-card-image");
      photo.src = p.image;
      photo.alt = p.name;
      photo.loading = "lazy";
      const body = node("div", "menu-card-body");
      body.append(node("span", "menu-card-cat", p.category));
      body.append(node("h3", "", p.name));
      body.append(node("p", "", p.description));
      const bottom = node("div", "menu-card-bottom");
      bottom.append(node("strong", "", fmt(p.price)));
      const add = node("button", "add-item", "+");
      add.type = "button";
      add.disabled = !p.available;
      add.setAttribute("aria-label", "Add " + p.name + " to basket");
      add.title = p.available ? "Add to basket" : "Not available";
      add.addEventListener("click", () => setQuantity(p.id, (cart[p.id] || 0) + 1));
      bottom.append(add);
      body.append(bottom);
      if (!p.available) body.append(node("small", "unavailable-note", "Temporarily unavailable — low ingredient stock"));
      card.append(photo, body);
      grid.append(card);
    });
  }
  function renderCart() {
    cartItems.replaceChildren();
    const rows = products.filter(p => cart[p.id] > 0);
    if (!rows.length) cartItems.append(node("div", "empty-cart", "Your next favourite starts here. Add something delicious from the menu."));
    rows.forEach(p => {
      const row = node("div", "cart-row");
      const info = node("div", "cart-row-info");
      info.append(node("strong", "", p.name));
      info.append(node("small", "", fmt(p.price) + " each"));
      const qty = node("div", "cart-quantity");
      const minus = node("button", "", "−");
      minus.type = "button";
      minus.setAttribute("aria-label", "Remove one " + p.name);
      minus.addEventListener("click", () => setQuantity(p.id, cart[p.id] - 1));
      const plus = node("button", "", "+");
      plus.type = "button";
      plus.disabled = cart[p.id] >= 10 || !p.available;
      plus.setAttribute("aria-label", "Add another " + p.name);
      plus.addEventListener("click", () => setQuantity(p.id, cart[p.id] + 1));
      qty.append(minus, node("span", "", cart[p.id]), plus);
      info.append(qty);
      row.append(info, node("strong", "", fmt(p.price * cart[p.id])));
      cartItems.append(row);
    });
    const count = itemsInCart();
    $("cart-count").textContent = count;
    $("mobile-cart-count").textContent = count;
    $("cart-subtotal").textContent = fmt(total());
    $("mobile-cart-total").textContent = fmt(total()) + " ↗";
    $("place-order").disabled = !count;
    $("place-order").textContent = count ? "Place demo order ↗" : "Choose something first";
  }
  function toggleCart(open) {
    document.body.classList.toggle("cart-open", open);
    $("cart-backdrop").hidden = !open;
    if (open) $("close-cart").focus();
    else $("open-cart").focus();
  }
  $("open-cart").addEventListener("click", () => toggleCart(true));
  $("close-cart").addEventListener("click", () => toggleCart(false));
  $("cart-backdrop").addEventListener("click", () => toggleCart(false));
  window.addEventListener("keydown", event => {
    if (event.key === "Escape" && document.body.classList.contains("cart-open")) toggleCart(false);
  });
  $("menu-search").addEventListener("input", event => {
    search = event.target.value.toLowerCase().trim();
    renderMenu();
  });
  $("delivery-type").addEventListener("change", event => {
    const type = event.target.value;
    $("location-label").textContent = type === "room" ? "Room number" : type === "table" ? "Table number" : "Pickup point";
    $("delivery-location").placeholder = type === "room" ? "e.g. 204" : type === "table" ? "e.g. T12" : "Collection desk";
    $("delivery-location").readOnly = type === "pickup";
    $("delivery-location").value = type === "pickup" ? "Collection desk" : "";
  });
  $("checkout-form").addEventListener("submit", async event => {
    event.preventDefault();
    showError(checkoutError, "");
    if (!itemsInCart()) return;
    const submit = $("place-order");
    submit.disabled = true;
    submit.textContent = "Placing order…";
    const payload = {
      guest_name: $("guest-name").value.trim(),
      delivery_type: $("delivery-type").value,
      location: $("delivery-location").value.trim(),
      note: $("order-note").value.trim(),
      items: Object.entries(cart).map(([id, quantity]) => ({id, quantity}))
    };
    try {
      const placed = await api("/api/orders", jsonOptions(payload));
      lastOrderCode = placed.code;
      cart = {};
      saveCart();
      $("checkout-form").reset();
      $("delivery-location").readOnly = false;
      $("location-label").textContent = "Room number";
      $("success-code").textContent = lastOrderCode;
      $("success-total").textContent = "Demo order value: " + fmt(placed.total);
      $("tracking-message").textContent = "";
      $("success-modal").hidden = false;
      document.body.classList.remove("cart-open");
      $("cart-backdrop").hidden = true;
      $("track-new-order").focus();
      await loadMenu();
    } catch (err) {
      showError(checkoutError, err.message);
      if (/stock/i.test(err.message)) await loadMenu();
    } finally {
      renderCart();
    }
  });
  $("track-new-order").addEventListener("click", async () => {
    const message = $("tracking-message");
    message.textContent = "Checking the kitchen…";
    try {
      const tracked = await api("/api/orders/" + encodeURIComponent(lastOrderCode));
      message.textContent = "Status: " + tracked.status.toUpperCase() + " · " +
        tracked.items.map(line => line.quantity + " × " + line.name).join(", ") + ".";
    } catch (err) { message.textContent = err.message; }
  });
  $("continue-ordering").addEventListener("click", () => {
    $("success-modal").hidden = true;
    $("menu-search").focus();
  });
  async function loadMenu() {
    try {
      products = await api("/api/menu");
      showError(error, "");
      Object.keys(cart).forEach(id => { if (!products.some(p => p.id === id)) delete cart[id]; });
      renderCategories();
      renderMenu();
      renderCart();
    } catch (err) {
      showError(error, "Unable to load the menu: " + err.message);
      grid.replaceChildren();
    }
  }
  loadMenu();
}

function initStaffApp() {
  const loginScreen = $("staff-login"), dashboard = $("dashboard"), error = $("staff-login-error");
  let snapshot = null;
  let selectedTab = "orders";
  function notify(message, isError) {
    const target = $("dashboard-message");
    target.textContent = message;
    target.style.background = isError ? "#fbe8e2" : "";
    target.style.color = isError ? "#9c4337" : "";
  }
  function showDashboard(active) {
    loginScreen.hidden = active;
    dashboard.hidden = !active;
    $("logout-btn").hidden = !active;
  }
  $("staff-login-form").addEventListener("submit", async event => {
    event.preventDefault();
    error.hidden = true;
    const button = event.target.querySelector("button");
    button.disabled = true;
    button.textContent = "Checking credentials…";
    try {
      await api("/api/staff/login", jsonOptions({password:$("staff-password").value}));
      $("staff-password").value = "";
      await refresh();
    } catch (err) {
      error.textContent = err.message;
      error.hidden = false;
    } finally {
      button.disabled = false;
      button.textContent = "Open dashboard ↗";
    }
  });
  $("logout-btn").addEventListener("click", async () => {
    try { await api("/api/staff/logout", {method:"POST"}); } catch {}
    snapshot = null;
    showDashboard(false);
  });
  $("refresh-dashboard").addEventListener("click", async () => {
    await refresh();
    notify("Dashboard updated.", false);
  });
  document.querySelectorAll(".dash-tab").forEach(button => button.addEventListener("click", () => {
    selectedTab = button.dataset.tab;
    document.querySelectorAll(".dash-tab").forEach(b => {
      b.classList.toggle("active", b.dataset.tab === selectedTab);
      b.setAttribute("aria-selected", String(b.dataset.tab === selectedTab));
    });
    $("orders-view").hidden = selectedTab !== "orders";
    $("inventory-view").hidden = selectedTab !== "inventory";
  }));
  $("stock-search").addEventListener("input", () => renderStock());
  function renderStats() {
    $("stat-orders").textContent = snapshot.stats.orders;
    $("stat-active").textContent = snapshot.stats.active;
    $("stat-revenue").textContent = fmt(snapshot.stats.revenue);
    $("stat-low").textContent = snapshot.stats.low_stock;
    $("orders-tab-count").textContent = "(" + snapshot.orders.length + ")";
    $("stock-tab-count").textContent = "(" + snapshot.stock.length + ")";
  }
  function renderOrders() {
    const host = $("staff-orders");
    host.replaceChildren();
    if (!snapshot.orders.length) {
      host.append(node("p", "muted", "No orders yet. Try placing a guest order from the menu app."));
      return;
    }
    const next = {received:"preparing", preparing:"ready", ready:"served"};
    snapshot.orders.forEach(order => {
      const card = node("article", "staff-order");
      const top = node("div", "staff-order-top");
      top.append(node("span", "staff-order-code", "#" + order.code));
      const date = new Date(order.created_at);
      top.append(node("small", "staff-order-date", date.toLocaleString("en-KE",{dateStyle:"medium",timeStyle:"short"})));
      card.append(top);
      card.append(node("h3", "", order.guest_name));
      card.append(node("p", "staff-order-service",
        (order.delivery_type === "room" ? "Room service" : order.delivery_type === "table" ? "Table service" : "Pickup") +
        " · " + order.location));
      order.items.forEach(item => {
        const line = node("div", "staff-order-line");
        line.append(node("span", "", item.quantity + " × " + item.name));
        card.append(line);
      });
      const bottom = node("div", "staff-order-footer");
      const status = node("span", "status-badge " + order.status, order.status);
      const button = node("button", "", next[order.status] ? "Mark " + next[order.status] + " ↗" : "Completed");
      button.type = "button";
      button.disabled = !next[order.status];
      button.addEventListener("click", async () => {
        button.disabled = true;
        try {
          await api("/api/staff/orders/" + order.id + "/status", jsonOptions({status:next[order.status]}));
          notify("Updated order #" + order.code, false);
          await refresh();
        } catch (err) {
          notify(err.message, true);
          button.disabled = false;
        }
      });
      bottom.append(status, button);
      card.append(bottom);
      host.append(card);
    });
  }
  function renderStock() {
    if (!snapshot) return;
    const term = $("stock-search").value.toLowerCase().trim();
    const host = $("inventory-rows");
    host.replaceChildren();
    snapshot.stock.filter(item => item.name.toLowerCase().includes(term)).forEach(item => {
      const row = node("tr");
      row.append(node("td", "", item.name));
      row.append(node("td", "", Number(item.quantity).toLocaleString("en-KE",{maximumFractionDigits:2}) + " " + item.unit));
      row.append(node("td", "", item.minimum + " " + item.unit));
      const statusCell = node("td");
      const low = item.quantity <= item.minimum;
      statusCell.append(node("span", low ? "stock-low" : "stock-ok", low ? "Reorder soon" : "Healthy"));
      row.append(statusCell);
      const actionsCell = node("td");
      const actions = node("div", "adjust-tools");
      const input = node("input");
      input.type = "number";
      input.min = "0.01";
      input.max = "1000";
      input.step = "0.1";
      input.value = "5";
      input.setAttribute("aria-label", "Adjustment quantity for " + item.name);
      const plus = node("button", "", "+ Restock");
      const minus = node("button", "", "− Use");
      plus.type = minus.type = "button";
      async function adjust(sign, button) {
        const amount = Number(input.value);
        if (!Number.isFinite(amount) || amount <= 0 || amount > 1000) {
          notify("Enter an amount from 0.01 to 1,000.", true);
          return;
        }
        button.disabled = true;
        try {
          await api("/api/staff/inventory/" + encodeURIComponent(item.id), jsonOptions({
            delta: sign * amount,
            reason: sign > 0 ? "Demo manual restock" : "Demo inventory write-off"
          }));
          notify(item.name + " stock " + (sign > 0 ? "increased" : "decreased") + " by " + amount + " " + item.unit + ".", false);
          await refresh();
        } catch (err) { notify(err.message, true); }
        finally { button.disabled = false; }
      }
      plus.addEventListener("click", () => adjust(1, plus));
      minus.addEventListener("click", () => adjust(-1, minus));
      actions.append(input, plus, minus);
      actionsCell.append(actions);
      row.append(actionsCell);
      host.append(row);
    });
  }
  async function refresh() {
    try {
      snapshot = await api("/api/staff/snapshot");
      showDashboard(true);
      renderStats();
      renderOrders();
      renderStock();
    } catch (err) {
      if (/login|required|401/i.test(err.message)) showDashboard(false);
      else if (!dashboard.hidden) notify(err.message, true);
    }
  }
  refresh();
  window.setInterval(() => {
    if (!dashboard.hidden && !document.hidden) refresh();
  }, 25000);
}
