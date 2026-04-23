const PremiumApp = {
  token: localStorage.getItem("access_token") || "",
  refresh: localStorage.getItem("refresh_token") || "",
};

function requireAuthPremium() {
  if (!PremiumApp.token) {
    window.location.href = "/app/login";
    return false;
  }
  return true;
}

function logoutPremium() {
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
  PremiumApp.token = "";
  PremiumApp.refresh = "";
  window.location.href = "/app/login";
}

async function apiPremium(path, options = {}) {
  const headers = options.headers || {};
  if (!headers["Content-Type"] && options.body !== undefined) headers["Content-Type"] = "application/json";
  if (PremiumApp.token) headers["Authorization"] = `Bearer ${PremiumApp.token}`;
  const res = await fetch(path, { ...options, headers });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || "Operazione non riuscita");
  return data;
}

function topbar(active) {
  const items = [
    ["dashboard", "Dashboard"],
    ["search", "Ricerca"],
    ["leads", "Lead"],
    ["emails", "Email"],
    ["settings", "Impostazioni"],
  ];
  return `
  <header class="topbar">
    <div class="wrap">
      <div class="row" style="padding-top:14px;">
        <div class="brand"><span class="dot"></span> JetLead Suite</div>
        <button class="btn btn-secondary" onclick="logoutPremium()">Account</button>
      </div>
      <nav class="nav">
        ${items.map(([k, label]) => `<a class="${active === k ? "active" : ""}" href="/app/${k}">${label}</a>`).join("")}
      </nav>
    </div>
  </header>`;
}

function classBadge(classification) {
  const c = (classification || "").toUpperCase();
  if (c === "HIGH VALUE") return "high";
  if (c === "MEDIUM") return "med";
  return "low";
}
