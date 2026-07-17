(async function () {
  const profile = await renderNav("browse.html");
  const isConsumer = profile?.role === "consumer";

  let myPos = null;
  let maxKm = "";
  let map, markersLayer;

  function initMap() {
    map = L.map("map").setView([20.5937, 78.9629], 5);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap contributors",
    }).addTo(map);
    markersLayer = L.layerGroup().addTo(map);
  }
  initMap();

  if (new URLSearchParams(location.search).get("ugly") === "1") {
    document.getElementById("fUgly").checked = true;
  }

  async function load() {
    const params = new URLSearchParams();
    const cat = document.getElementById("fCategory").value;
    const maxPrice = document.getElementById("fMaxPrice").value;
    if (cat) params.set("category", cat);
    if (maxPrice) params.set("max_price", maxPrice);
    if (document.getElementById("fUgly").checked) params.set("ugly_only", "1");
    if (myPos) { params.set("lat", myPos.lat); params.set("lng", myPos.lng); }
    if (maxKm && myPos) params.set("max_km", maxKm);

    document.getElementById("uglyBanner").style.display =
      document.getElementById("fUgly").checked ? "" : "none";

    let data;
    try { data = await api("/browse?" + params, { auth: false }); }
    catch (err) { return toast(err.message, "danger"); }

    // Map: one marker per farmer, verified badge in the popup.
    markersLayer.clearLayers();
    const bounds = [];
    data.farmers.forEach((f) => {
      if (f.lat == null) return;
      const m = L.marker([f.lat, f.lng]).addTo(markersLayer);
      m.bindPopup(`<strong>${esc(f.name)}</strong>
        ${f.verified ? '<span class="badge text-bg-success">✔ Verified Farmer</span>' : ""}<br>
        ⭐ ${f.rating_avg || "—"} (${f.rating_count || 0})
        ${f.distance_km != null ? `<br>${f.distance_km} km away` : ""}`);
      bounds.push([f.lat, f.lng]);
    });
    if (myPos) {
      L.circleMarker([myPos.lat, myPos.lng], { radius: 7, color: "#0d6efd" })
        .bindPopup("You are here").addTo(markersLayer);
      bounds.push([myPos.lat, myPos.lng]);
    }
    if (bounds.length) map.fitBounds(bounds, { padding: [30, 30], maxZoom: 13 });

    // Cards.
    const holder = document.getElementById("items");
    document.getElementById("emptyState").style.display = data.items.length ? "none" : "";
    holder.innerHTML = data.items.map((i) => `
      <div class="col-6 col-md-4">
        <div class="card card-product h-100">
          ${i.image_url ? `<img class="card-img-top" src="${esc(i.image_url)}">`
                        : `<div class="card-img-top">${{vegetable:"🥬",fruit:"🍎",dairy:"🥛",eggs:"🥚",grains:"🌾",homemade:"🍯"}[i.category] || "🧺"}</div>`}
          <div class="card-body">
            <h6 class="mb-1">${esc(i.name)}</h6>
            <div>${freshBadge(i.freshness)} ${uglyBadge(i)}</div>
            <div class="text-success fw-bold fs-5">₹${i.price}<small class="text-muted">/${esc(i.unit)}</small>
              ${i.discount_pct ? `<small class="text-decoration-line-through text-muted">₹${i.list_price}</small>` : ""}</div>
            <small class="text-muted">${esc(i.farmer.name)}
              ${i.farmer.verified ? "✔" : ""}${i.farmer.distance_km != null ? ` · ${i.farmer.distance_km} km` : ""}
              · ${i.qty_available} ${esc(i.unit)} left</small>
            <div class="input-group input-group-sm mt-2">
              <input type="number" class="form-control" value="1" min="0.5" step="0.5" id="qty-${i.batch_id}">
              <button class="btn btn-success" data-add="${i.batch_id}">Add</button>
              <button class="btn btn-outline-danger" title="Report listing" data-report="${i.product_id}">⚑</button>
            </div>
          </div>
        </div>
      </div>`).join("");

    holder.querySelectorAll("[data-add]").forEach((btn) =>
      btn.addEventListener("click", () => {
        const item = data.items.find((x) => x.batch_id === btn.dataset.add);
        const qty = parseFloat(document.getElementById("qty-" + item.batch_id).value || "1");
        if (!isConsumer) return toast("Login as a consumer to buy", "warning");
        Cart.add({ batch_id: item.batch_id, name: item.name, unit: item.unit,
                   price: item.price, qty, farmer_id: item.farmer.id });
        renderCart();
        // Browsing signal for the recommender (fire-and-forget).
        api("/ai/browse-event", { method: "POST",
          body: { category: item.category, product_id: item.product_id } }).catch(() => {});
      }));
    holder.querySelectorAll("[data-report]").forEach((btn) =>
      btn.addEventListener("click", async () => {
        if (!profile) return toast("Login to report content", "warning");
        const reason = prompt("Why are you reporting this listing?");
        if (!reason) return;
        try {
          await api("/reports", { method: "POST",
            body: { target_type: "product", target_id: btn.dataset.report, reason } });
          toast("Reported — an admin will review it");
        } catch (err) { toast(err.message, "danger"); }
      }));
  }

  function renderCart() {
    const items = Cart.read();
    document.getElementById("cartItems").innerHTML = items.length
      ? items.map((i) => `<div class="d-flex justify-content-between align-items-center small mb-1">
          <span>${esc(i.name)} × ${i.qty} ${esc(i.unit)}</span>
          <span>₹${(i.price * i.qty).toFixed(0)}
            <button class="btn btn-sm btn-link text-danger p-0" data-rm="${i.batch_id}">✕</button></span>
        </div>`).join("")
      : '<div class="text-muted small">Cart is empty</div>';
    document.getElementById("cartTotal").textContent =
      "₹" + items.reduce((s, i) => s + i.price * i.qty, 0).toFixed(0);
    document.querySelectorAll("[data-rm]").forEach((b) =>
      b.addEventListener("click", () => { Cart.remove(b.dataset.rm); renderCart(); }));
  }

  document.getElementById("useLocation").addEventListener("click", async () => {
    myPos = await getPosition();
    document.getElementById("locStatus").textContent = myPos
      ? "Location on — distance filters active" : "Could not get your location";
    load();
  });
  document.getElementById("distChips").querySelectorAll("button").forEach((b) =>
    b.addEventListener("click", () => {
      document.querySelectorAll("#distChips button").forEach((x) => x.classList.remove("active"));
      b.classList.add("active");
      maxKm = b.dataset.km;
      if (maxKm && !myPos) toast("Turn on 'Use my location' first", "warning");
      load();
    }));
  ["fCategory", "fMaxPrice", "fUgly"].forEach((id) =>
    document.getElementById(id).addEventListener("change", load));

  document.getElementById("checkoutBtn").addEventListener("click", async () => {
    if (!isConsumer) return toast("Login as a consumer to checkout", "warning");
    const items = Cart.read();
    if (!items.length) return toast("Cart is empty", "warning");
    const delivery_type = document.getElementById("deliveryType").value;
    const address = document.getElementById("address").value.trim();
    try {
      const order = await api("/orders", { method: "POST",
        body: { items: items.map((i) => ({ batch_id: i.batch_id, qty: i.qty })),
                delivery_type, address } });
      Cart.clear(); renderCart(); load();
      toast(`Order placed! Total ₹${order.total} (simulated payment). Track it in My Orders.`);
    } catch (err) { toast(err.message, "danger"); }
  });

  renderCart();
  load();
})();
