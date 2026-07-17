(async function () {
  const profile = await renderNav("index.html");

  // Platform-wide impact counter (public read via backend).
  try {
    const stats = await api("/stats", { auth: false });
    const target = Number(stats.kg_saved || 0);
    const el = document.getElementById("kgSaved");
    let n = 0;
    const step = Math.max(1, Math.round(target / 60));
    const timer = setInterval(() => {
      n = Math.min(target, n + step);
      el.textContent = n.toLocaleString();
      if (n >= target) clearInterval(timer);
    }, 20);
  } catch (_) {}

  // Personalised rail for signed-in consumers.
  if (profile?.role === "consumer") {
    try {
      const pos = await getPosition();
      const q = pos ? `?lat=${pos.lat}&lng=${pos.lng}` : "";
      const recs = await api("/ai/recommendations" + q);
      if (recs.length) {
        document.getElementById("recsSection").style.display = "";
        document.getElementById("recs").innerHTML = recs.map((r) => `
          <div class="col-6 col-md-3">
            <div class="card card-product h-100">
              ${r.image_url
                ? `<img class="card-img-top" src="${esc(r.image_url)}">`
                : `<div class="card-img-top">🥬</div>`}
              <div class="card-body">
                <h6>${esc(r.name)} ${uglyBadge(r)}</h6>
                <div class="text-success fw-bold">₹${r.price}/${esc(r.unit)}</div>
                <small class="text-muted">${esc(r.farmer_name)} · ${esc(r.freshness)}</small><br>
                <a class="btn btn-sm btn-outline-success mt-2" href="browse.html">View</a>
              </div>
            </div>
          </div>`).join("");
      }
    } catch (_) {}
  }
})();
