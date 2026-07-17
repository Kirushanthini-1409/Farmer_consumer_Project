(async function () {
  const profile = await renderNav("groups.html");
  const isConsumer = profile?.role === "consumer";
  let myPos = null;

  async function load() {
    const params = new URLSearchParams();
    if (myPos) { params.set("lat", myPos.lat); params.set("lng", myPos.lng); }
    let groups;
    try { groups = await api("/group-orders?" + params, { auth: false }); }
    catch (err) { return toast(err.message, "danger"); }

    document.getElementById("emptyState").style.display = groups.length ? "none" : "";
    document.getElementById("groups").innerHTML = groups.map((grp) => {
      const pct = Math.min(100, Math.round((grp.joined_qty / grp.target_qty) * 100));
      return `<div class="col-md-6 col-lg-4"><div class="card h-100 p-3">
        <h6>${esc(grp.product_name)} <small class="text-muted">by ${esc(grp.farmer_name)}
          ${grp.distance_km != null ? `· ${grp.distance_km} km` : ""}</small></h6>
        <div class="text-success fw-bold fs-5">₹${grp.discounted_price}/unit
          <small class="text-muted">group price</small></div>
        <div class="progress my-2" style="height: 1.2rem">
          <div class="progress-bar bg-success" style="width:${pct}%">${grp.joined_qty}/${grp.target_qty}</div>
        </div>
        <small class="text-muted">Closes: ${esc(grp.deadline.slice(0, 16))} · ${grp.member_count} joined
          ${pct >= 80 ? '· <span class="text-danger">leaving locked (≥80%)</span>' : ""}</small>
        <div class="input-group input-group-sm mt-2">
          <input type="number" class="form-control" min="0.5" step="0.5" value="1" id="join-${grp.id}">
          <button class="btn btn-success" data-join="${grp.id}">Join</button>
          <button class="btn btn-outline-secondary" data-leave="${grp.id}">Leave</button>
        </div>
      </div></div>`;
    }).join("");

    document.querySelectorAll("[data-join]").forEach((b) =>
      b.addEventListener("click", async () => {
        if (!isConsumer) return toast("Login as a consumer to join", "warning");
        try {
          const res = await api(`/group-orders/${b.dataset.join}/join`, {
            method: "POST",
            body: { qty: parseFloat(document.getElementById("join-" + b.dataset.join).value || "1") },
          });
          toast(res.capped
            ? `Joined with ${res.joined_qty} (capped — group almost full)` : "Joined the group buy!");
          load();
        } catch (err) { toast(err.message, "danger"); }
      }));
    document.querySelectorAll("[data-leave]").forEach((b) =>
      b.addEventListener("click", async () => {
        if (!isConsumer) return toast("Login as a consumer first", "warning");
        try {
          await api(`/group-orders/${b.dataset.leave}/leave`, { method: "POST" });
          toast("You left the group");
          load();
        } catch (err) { toast(err.message, "danger"); }
      }));
  }

  document.getElementById("useLocation").addEventListener("click", async () => {
    myPos = await getPosition();
    if (!myPos) toast("Could not get your location", "warning");
    load();
  });

  load();
})();
