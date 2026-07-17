(async function () {
  const profile = await renderNav("orders.html");
  if (!profile) { location.href = "auth.html"; return; }
  const isFarmer = profile.role === "farmer";
  document.getElementById("title").textContent = isFarmer ? "Incoming Orders" : "My Orders";

  // Which buttons each role sees per state (driven by the backend state machine).
  const ACTIONS = {
    farmer: {
      PLACED: [["accept", "Accept", "success"], ["reject", "Reject", "outline-danger"]],
      CONFIRMED: [["pack", "Mark packed", "success"]],
      PACKED: [["out_for_delivery", "Out for delivery", "success"],
               ["ready_for_pickup", "Ready for pickup", "outline-success"]],
      OUT_FOR_DELIVERY: [["delivered", "Mark delivered", "success"]],
      READY_FOR_PICKUP: [["delivered", "Mark picked up", "success"]],
    },
    consumer: {
      PLACED: [["cancel", "Cancel order", "outline-danger"]],
      CONFIRMED: [["cancel", "Cancel order", "outline-danger"]],
      DELIVERED: [["complete", "Confirm received", "success"], ["dispute", "Raise dispute", "outline-danger"]],
    },
  };
  const STATUS_BADGE = {
    PLACED: "secondary", CONFIRMED: "info", PACKED: "primary", OUT_FOR_DELIVERY: "primary",
    READY_FOR_PICKUP: "primary", DELIVERED: "warning", COMPLETED: "success",
    CANCELLED: "dark", REJECTED: "dark", DISPUTED: "danger",
  };

  async function load() {
    let orders;
    try { orders = await api("/orders"); }
    catch (err) { return toast(err.message, "danger"); }
    document.getElementById("emptyState").style.display = orders.length ? "none" : "";
    document.getElementById("orders").innerHTML = orders.map((o) => {
      const actions = (ACTIONS[isFarmer ? "farmer" : "consumer"][o.status] || [])
        .map(([a, label, cls]) =>
          `<button class="btn btn-sm btn-${cls} me-1" data-act="${a}" data-id="${o.id}">${label}</button>`)
        .join("");
      const review = (!isFarmer && o.status === "COMPLETED")
        ? o.items.map((i) =>
            `<button class="btn btn-sm btn-outline-success me-1" data-review="${o.id}"
               data-product="${i.product_id}">★ Review ${esc(i.product_name)}</button>`).join("")
        : "";
      return `<div class="card mb-3"><div class="card-body">
        <div class="d-flex justify-content-between flex-wrap">
          <div>
            <span class="badge text-bg-${STATUS_BADGE[o.status] || "secondary"}">${o.status.replaceAll("_", " ")}</span>
            <strong class="ms-2">₹${o.total}</strong>
            <small class="text-muted ms-2">${esc((o.created_at || "").slice(0, 16))}</small>
            <small class="text-muted ms-2">${o.delivery_type === "pickup" ? "🧺 pickup" : "🚚 delivery"}</small>
          </div>
          <button class="btn btn-sm btn-link" data-timeline="${o.id}">Timeline</button>
        </div>
        <div class="small mt-1">${o.items.map((i) =>
          `${esc(i.product_name)} × ${i.qty} ${esc(i.unit)} @ ₹${i.unit_price}
           ${i.is_ugly ? '<span class="badge text-bg-danger">ugly</span>' : ""}`).join(" · ")}</div>
        <div class="mt-2">${actions} ${review}</div>
      </div></div>`;
    }).join("");

    document.querySelectorAll("[data-act]").forEach((b) =>
      b.addEventListener("click", async () => {
        b.disabled = true;
        try {
          await api(`/orders/${b.dataset.id}/transition`,
            { method: "POST", body: { action: b.dataset.act } });
          toast("Order updated");
          load();
        } catch (err) { toast(err.message, "danger"); b.disabled = false; }
      }));
    document.querySelectorAll("[data-timeline]").forEach((b) =>
      b.addEventListener("click", async () => {
        const events = await api(`/orders/${b.dataset.timeline}/events`);
        document.getElementById("timeline").innerHTML = events.map((e) => `
          <div class="step"><strong>${esc(e.to_status)}</strong>
            <small class="text-muted d-block">${esc((e.at || "").slice(0, 16))}
              ${e.note ? "· " + esc(e.note) : ""}</small></div>`).join("")
          || '<div class="text-muted">No events</div>';
        new bootstrap.Modal("#timelineModal").show();
      }));
    document.querySelectorAll("[data-review]").forEach((b) =>
      b.addEventListener("click", () => {
        document.getElementById("rvOrder").value = b.dataset.review;
        document.getElementById("rvProduct").value = b.dataset.product;
        new bootstrap.Modal("#reviewModal").show();
      }));
  }

  document.getElementById("rvSubmit").addEventListener("click", async () => {
    try {
      await api("/reviews", { method: "POST", body: {
        order_id: document.getElementById("rvOrder").value,
        product_id: document.getElementById("rvProduct").value,
        stars: parseInt(document.getElementById("rvStars").value),
        text: document.getElementById("rvText").value,
      }});
      bootstrap.Modal.getInstance(document.getElementById("reviewModal")).hide();
      toast("Thanks for your review!");
    } catch (err) { toast(err.message, "danger"); }
  });

  load();
  // Live-ish updates on the order page only (plan: no polling loops elsewhere).
  setInterval(load, 20000);
})();
