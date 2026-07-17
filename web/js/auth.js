(async function () {
  await renderNav("auth.html");

  // Farmer signup: Leaflet location picker (no Google, no geocoding needed).
  let pickMap, pin;
  function showFarmerFields(show) {
    document.getElementById("farmerFields").style.display = show ? "" : "none";
    if (show && !pickMap) {
      pickMap = L.map("pickMap").setView([20.5937, 78.9629], 5); // India
      L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "&copy; OpenStreetMap contributors",
      }).addTo(pickMap);
      pickMap.on("click", (e) => {
        if (pin) pin.remove();
        pin = L.marker(e.latlng).addTo(pickMap);
        document.getElementById("suLat").value = e.latlng.lat;
        document.getElementById("suLng").value = e.latlng.lng;
      });
      getPosition().then((pos) => pos && pickMap.setView([pos.lat, pos.lng], 12));
      setTimeout(() => pickMap.invalidateSize(), 300);
    }
  }
  document.querySelectorAll('input[name="role"]').forEach((r) =>
    r.addEventListener("change", () => showFarmerFields(r.value === "farmer" && r.checked)));

  document.getElementById("loginForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      await fbAuth.signInWithEmailAndPassword(
        document.getElementById("loginEmail").value,
        document.getElementById("loginPassword").value);
      location.href = "index.html";
    } catch (err) { toast(err.message, "danger"); }
  });

  document.getElementById("signupForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = document.getElementById("signupBtn");
    const role = document.querySelector('input[name="role"]:checked').value;
    const body = {
      role,
      name: document.getElementById("suName").value.trim(),
      phone: document.getElementById("suPhone").value.trim(),
    };
    if (role === "farmer") {
      body.lat = document.getElementById("suLat").value;
      body.lng = document.getElementById("suLng").value;
      body.address = document.getElementById("suAddress").value.trim();
      if (!body.lat) return toast("Click the map to set your farm location", "warning");
    }
    btn.disabled = true;
    try {
      await fbAuth.createUserWithEmailAndPassword(
        document.getElementById("suEmail").value,
        document.getElementById("suPassword").value);

      if (role === "farmer") {
        const idFile = document.getElementById("suIdDoc").files[0];
        const landFile = document.getElementById("suLandDoc").files[0];
        if (idFile) body.id_doc_url = await uploadImage(idFile);
        if (landFile) body.land_doc_url = await uploadImage(landFile);
      }
      await api("/auth/register-profile", { method: "POST", body });
      await fbAuth.currentUser.getIdToken(true); // refresh: pick up the role custom claim
      toast("Welcome to FarmConnect!");
      location.href = role === "farmer" ? "farmer.html" : "browse.html";
    } catch (err) {
      toast(err.message, "danger");
      btn.disabled = false;
    }
  });
})();
