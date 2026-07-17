// Shared app layer: Firebase init, API client, navbar, cart, small UI helpers.

firebase.initializeApp(firebaseConfig);
const fbAuth = firebase.auth();
const fbDb = firebase.firestore();
if (typeof USE_EMULATOR !== "undefined" && USE_EMULATOR) {
  fbAuth.useEmulator("http://localhost:9099");
  fbDb.useEmulator("localhost", 8080);
}

// ---------- API client (every write goes through Flask with the ID token) ----------
async function api(path, { method = "GET", body = null, auth = true } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (auth && fbAuth.currentUser) {
    headers["Authorization"] = "Bearer " + (await fbAuth.currentUser.getIdToken());
  }
  const res = await fetch(API_BASE + path, {
    method,
    headers,
    body: body ? JSON.stringify(body) : null,
  });
  let data = {};
  try { data = await res.json(); } catch (_) {}
  if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);
  return data;
}

function waitForUser() {
  return new Promise((resolve) => {
    const off = fbAuth.onAuthStateChanged((u) => { off(); resolve(u); });
  });
}

async function currentProfile() {
  if (!fbAuth.currentUser) return null;
  try { return await api("/me"); } catch (_) { return null; }
}

// Redirect helper for role-gated pages.
async function requireRole(...roles) {
  const user = await waitForUser();
  if (!user) { location.href = "auth.html"; return null; }
  const profile = await currentProfile();
  if (!profile || !roles.includes(profile.role)) { location.href = "index.html"; return null; }
  return profile;
}

// ---------- Cart (localStorage; server recomputes everything at checkout) ----------
const Cart = {
  read() { return JSON.parse(localStorage.getItem("fc_cart") || "[]"); },
  write(items) {
    localStorage.setItem("fc_cart", JSON.stringify(items));
    Cart.badge();
  },
  add(item) {
    const items = Cart.read();
    if (items.length && items[0].farmer_id !== item.farmer_id) {
      toast("One order per farmer — your cart has items from another farmer.", "warning");
      return false;
    }
    const existing = items.find((i) => i.batch_id === item.batch_id);
    if (existing) existing.qty += item.qty; else items.push(item);
    Cart.write(items);
    toast(`Added ${item.qty} ${item.unit} ${item.name} to cart`);
    return true;
  },
  remove(batchId) { Cart.write(Cart.read().filter((i) => i.batch_id !== batchId)); },
  clear() { Cart.write([]); },
  badge() {
    const el = document.getElementById("cartCount");
    if (el) el.textContent = Cart.read().length || "";
  },
};

// ---------- UI helpers ----------
function toast(message, kind = "success") {
  const holder = document.getElementById("toasts") || (() => {
    const d = document.createElement("div");
    d.id = "toasts";
    d.className = "toast-container position-fixed bottom-0 end-0 p-3";
    document.body.appendChild(d);
    return d;
  })();
  const el = document.createElement("div");
  el.className = `toast align-items-center text-bg-${kind} border-0 show mb-2`;
  el.innerHTML = `<div class="d-flex"><div class="toast-body">${message}</div>
    <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button></div>`;
  holder.appendChild(el);
  setTimeout(() => el.remove(), 4500);
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function freshBadge(fresh) {
  if (!fresh) return "";
  const cls = fresh.aging ? "text-bg-warning" : "text-bg-success";
  return `<span class="badge ${cls}">${esc(fresh.label || fresh)}</span>`;
}

function uglyBadge(item) {
  return item.is_ugly
    ? `<span class="badge text-bg-danger">Ugly but Tasty −${item.discount_pct}%</span>` : "";
}

// ---------- Navbar ----------
async function renderNav(active) {
  const user = await waitForUser();
  const profile = user ? await currentProfile() : null;
  const role = profile?.role;
  const links = [
    ["index.html", "Home", true],
    ["browse.html", "Browse", true],
    ["groups.html", "Group Buys", true],
    ["orders.html", "My Orders", !!user],
    ["farmer.html", "Farmer Dashboard", role === "farmer"],
    ["admin.html", "Admin", role === "admin"],
  ];
  const nav = document.getElementById("nav");
  if (!nav) return profile;
  nav.innerHTML = `
  <nav class="navbar navbar-expand-lg navbar-dark bg-success">
    <div class="container">
      <a class="navbar-brand fw-bold" href="index.html">🌾 FarmConnect</a>
      <button class="navbar-toggler" data-bs-toggle="collapse" data-bs-target="#navc">
        <span class="navbar-toggler-icon"></span></button>
      <div class="collapse navbar-collapse" id="navc">
        <ul class="navbar-nav me-auto">
          ${links.filter((l) => l[2]).map(([href, label]) =>
            `<li class="nav-item"><a class="nav-link ${active === href ? "active fw-bold" : ""}"
              href="${href}">${label}</a></li>`).join("")}
        </ul>
        <a href="browse.html#cart" class="btn btn-light btn-sm me-2">🛒 Cart
          <span id="cartCount" class="badge text-bg-success"></span></a>
        ${user
          ? `<span class="navbar-text text-white me-2">${esc(profile?.name || user.email)}
               ${profile?.role === "farmer" && profile?.verified
                 ? '<span class="badge text-bg-light text-success">✔ Verified</span>' : ""}</span>
             <button class="btn btn-outline-light btn-sm" onclick="fbAuth.signOut().then(()=>location.href='index.html')">Logout</button>`
          : `<a class="btn btn-light btn-sm" href="auth.html">Login / Sign up</a>`}
      </div>
    </div>
  </nav>`;
  Cart.badge();
  return profile;
}

// ---------- Cloudinary unsigned upload ----------
async function uploadImage(file) {
  const form = new FormData();
  form.append("file", file);
  form.append("upload_preset", CLOUDINARY_PRESET);
  const res = await fetch(
    `https://api.cloudinary.com/v1_1/${CLOUDINARY_CLOUD}/image/upload`,
    { method: "POST", body: form }
  );
  const data = await res.json();
  if (!res.ok) throw new Error(data.error?.message || "Image upload failed");
  return data.secure_url;
}

// ---------- Geolocation ----------
function getPosition() {
  return new Promise((resolve) =>
    navigator.geolocation
      ? navigator.geolocation.getCurrentPosition(
          (p) => resolve({ lat: p.coords.latitude, lng: p.coords.longitude }),
          () => resolve(null), { timeout: 8000 })
      : resolve(null));
}
