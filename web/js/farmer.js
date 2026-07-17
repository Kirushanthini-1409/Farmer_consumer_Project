(async function () {
  const profile = await requireRole("farmer");
  if (!profile) return;
  await renderNav("farmer.html");

  document.getElementById("kgSaved").textContent = (profile.kg_saved || 0).toLocaleString();
  document.getElementById("kycStatus").innerHTML = profile.verified
    ? '<span class="badge text-bg-success">✔ Verified Farmer</span>'
    : profile.kyc_pending
      ? '<span class="badge text-bg-warning">Verification pending admin review</span>'
      : '<span class="badge text-bg-secondary">Not verified — submit KYC docs at signup</span>';

  // Demand chips.
  try {
    const demand = await api("/ai/demand");
    document.getElementById("demandNote").textContent = "— " + demand.note;
    document.getElementById("demandChips").innerHTML = demand.chips.map((c) =>
      `<span class="chip ${c.direction === "up" ? "up" : ""}" title="${esc(c.why)}">
         ${c.direction === "up" ? "▲" : "▬"} ${esc(c.category)}</span>`).join("");
  } catch (_) {}

  let products = [];
  async function loadProducts() {
    products = await api("/products/mine");
    document.getElementById("bProduct").innerHTML =
      '<option value="">Choose product…</option>' +
      products.map((p) => `<option value="${p.id}" data-name="${esc(p.name)}"
        data-cat="${p.category}">${esc(p.name)} (${p.category})</option>`).join("");
  }

  async function loadBatches() {
    const batches = await api("/batches/mine");
    document.getElementById("batchRows").innerHTML = batches.map((b) => `
      <tr>
        <td>${esc(b.product_name)} ${b.is_ugly ? '<span class="badge text-bg-danger">ugly</span>' : ""}</td>
        <td>${b.qty_available} ${esc(b.unit)}</td>
        <td>₹${b.effective_price}${b.applied_discount_pct ? ` <small class="text-muted">(−${b.applied_discount_pct}%)</small>` : ""}</td>
        <td>${freshBadge(b.freshness)}</td>
        <td><button class="btn btn-sm btn-outline-secondary" data-restock="${b.id}">+ stock</button></td>
      </tr>`).join("") || '<tr><td colspan="5" class="text-muted">No batches yet</td></tr>';
    document.getElementById("gBatch").innerHTML =
      '<option value="">Choose batch…</option>' +
      batches.map((b) => `<option value="${b.id}">${esc(b.product_name)} — ${b.qty_available} ${esc(b.unit)} @ ₹${b.price}</option>`).join("");
    document.querySelectorAll("[data-restock]").forEach((btn) =>
      btn.addEventListener("click", async () => {
        const add = parseFloat(prompt("Add how much stock?") || "0");
        if (add > 0) {
          const b = batches.find((x) => x.id === btn.dataset.restock);
          await api(`/batches/${b.id}`, { method: "PATCH",
            body: { qty_available: b.qty_available + add } });
          loadBatches();
        }
      }));
  }

  // AI price band, refreshed as the batch form changes; drops when "ugly" is toggled.
  async function refreshBand() {
    const opt = document.getElementById("bProduct").selectedOptions[0];
    const el = document.getElementById("priceBand");
    if (!opt || !opt.value) { el.style.display = "none"; return; }
    const params = new URLSearchParams({
      product: opt.dataset.name, category: opt.dataset.cat,
      is_ugly: document.getElementById("bUgly").checked ? "1" : "0",
    });
    const harvest = document.getElementById("bHarvest").value;
    if (harvest) params.set("harvest_date", harvest);
    try {
      const band = await api("/ai/price-suggest?" + params);
      el.style.display = "";
      el.innerHTML = `🤖 <strong>AI fair price:</strong> ₹${band.low} – ₹${band.high}
        <small class="text-muted">(centre ₹${band.base}, source: ${esc(band.source)}
        ${band.adjustments.length ? "· " + band.adjustments.map(esc).join(", ") : ""})</small>`;
    } catch (_) { el.style.display = "none"; }
  }
  ["bProduct", "bUgly", "bHarvest"].forEach((id) =>
    document.getElementById(id).addEventListener("change", refreshBand));
  document.getElementById("bUgly").addEventListener("change", (e) => {
    document.getElementById("uglyDiscountRow").style.display = e.target.checked ? "" : "none";
  });
  document.getElementById("bDiscount").addEventListener("input", (e) => {
    document.getElementById("bDiscountVal").textContent = e.target.value;
  });

  document.getElementById("productForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      let image_url = "";
      const file = document.getElementById("pImage").files[0];
      if (file) image_url = await uploadImage(file);
      await api("/products", { method: "POST", body: {
        name: document.getElementById("pName").value,
        category: document.getElementById("pCategory").value,
        base_price: parseFloat(document.getElementById("pPrice").value),
        unit: document.getElementById("pUnit").value || "kg",
        description: document.getElementById("pDesc").value,
        image_url,
      }});
      toast("Product added");
      e.target.reset();
      loadProducts();
    } catch (err) { toast(err.message, "danger"); }
  });

  document.getElementById("batchForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const isUgly = document.getElementById("bUgly").checked;
    try {
      const res = await api("/batches", { method: "POST", body: {
        product_id: document.getElementById("bProduct").value,
        qty_available: parseFloat(document.getElementById("bQty").value),
        price: parseFloat(document.getElementById("bPrice").value),
        harvest_date: document.getElementById("bHarvest").value,
        is_ugly: isUgly,
        discount_pct: isUgly ? parseInt(document.getElementById("bDiscount").value) : 0,
      }});
      toast(res.warning ? res.warning : "Batch added", res.warning ? "warning" : "success");
      e.target.reset();
      document.getElementById("uglyDiscountRow").style.display = "none";
      loadBatches();
    } catch (err) { toast(err.message, "danger"); }
  });

  document.getElementById("groupForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      await api("/group-orders", { method: "POST", body: {
        batch_id: document.getElementById("gBatch").value,
        target_qty: parseFloat(document.getElementById("gTarget").value),
        discounted_price: parseFloat(document.getElementById("gPrice").value),
        deadline: document.getElementById("gDeadline").value,
        radius_km: parseFloat(document.getElementById("gRadius").value || "10"),
      }});
      toast("Group buy opened — consumers can now join");
      e.target.reset();
    } catch (err) { toast(err.message, "danger"); }
  });

  loadProducts();
  loadBatches();
})();
