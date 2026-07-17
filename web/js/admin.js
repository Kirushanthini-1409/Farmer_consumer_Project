(async function () {
  const profile = await requireRole("admin");
  if (!profile) return;
  await renderNav("admin.html");

  async function loadKyc() {
    const queue = await api("/admin/kyc");
    document.getElementById("kycQueue").innerHTML = queue.length ? queue.map((r) => `
      <div class="border rounded p-2 mb-2">
        <strong>${esc(r.farmer_name || r.farmer_id)}</strong>
        <div class="my-1">
          ${r.id_doc_url ? `<a href="${esc(r.id_doc_url)}" target="_blank" rel="noopener" class="btn btn-sm btn-outline-secondary me-1">ID doc</a>` : '<span class="badge text-bg-secondary me-1">no ID doc</span>'}
          ${r.land_doc_url ? `<a href="${esc(r.land_doc_url)}" target="_blank" rel="noopener" class="btn btn-sm btn-outline-secondary">Land/FPO doc</a>` : '<span class="badge text-bg-secondary">no land doc</span>'}
        </div>
        <button class="btn btn-sm btn-success me-1" data-kyc="${r.id}" data-decision="approved">Approve ✔</button>
        <button class="btn btn-sm btn-outline-danger" data-kyc="${r.id}" data-decision="rejected">Reject</button>
      </div>`).join("") : '<div class="text-muted">No pending verifications 🎉</div>';
    document.querySelectorAll("[data-kyc]").forEach((b) =>
      b.addEventListener("click", async () => {
        try {
          await api(`/admin/kyc/${b.dataset.kyc}/decide`,
            { method: "POST", body: { decision: b.dataset.decision } });
          toast(`KYC ${b.dataset.decision}`);
          loadKyc();
        } catch (err) { toast(err.message, "danger"); }
      }));
  }

  async function loadReports() {
    const queue = await api("/admin/reports");
    document.getElementById("reportQueue").innerHTML = queue.length ? queue.map((r) => `
      <div class="border rounded p-2 mb-2">
        <span class="badge text-bg-secondary">${esc(r.target_type)}</span>
        <small class="text-muted">${esc(r.target_id)}</small>
        <div class="small my-1">"${esc(r.reason)}"</div>
        <button class="btn btn-sm btn-danger me-1" data-report="${r.id}" data-decision="hide">Hide content</button>
        <button class="btn btn-sm btn-outline-secondary" data-report="${r.id}" data-decision="dismiss">Dismiss</button>
      </div>`).join("") : '<div class="text-muted">No pending reports 🎉</div>';
    document.querySelectorAll("[data-report]").forEach((b) =>
      b.addEventListener("click", async () => {
        try {
          await api(`/admin/reports/${b.dataset.report}/decide`,
            { method: "POST", body: { decision: b.dataset.decision } });
          toast(`Report ${b.dataset.decision === "hide" ? "actioned — content hidden" : "dismissed"}`);
          loadReports();
        } catch (err) { toast(err.message, "danger"); }
      }));
  }

  loadKyc();
  loadReports();
})();
