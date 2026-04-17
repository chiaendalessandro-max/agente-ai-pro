const App = {
  token: localStorage.getItem("access_token") || "",
  refresh: localStorage.getItem("refresh_token") || "",
  rememberedEmail: localStorage.getItem("remember_email") || "",
  rememberMe: localStorage.getItem("remember_me") === "1",
};

function setSession(access, refresh) {
  App.token = access || "";
  App.refresh = refresh || "";
  if (App.token) localStorage.setItem("access_token", App.token);
  if (App.refresh) localStorage.setItem("refresh_token", App.refresh);
}

function clearSession() {
  App.token = "";
  App.refresh = "";
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
}

function saveRemember(email, remember) {
  if (remember) {
    localStorage.setItem("remember_email", email || "");
    localStorage.setItem("remember_me", "1");
  } else {
    localStorage.removeItem("remember_email");
    localStorage.removeItem("remember_me");
  }
}

function requireAuth() {
  if (!App.token) {
    window.location.href = "/app/login";
    return false;
  }
  return true;
}

function navTo(path) {
  window.location.href = path;
}

async function tryRefreshToken() {
  if (!App.refresh) return false;
  try {
    const res = await fetch("/auth/refresh", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: App.refresh }),
    });
    if (!res.ok) return false;
    const data = await res.json();
    setSession(data.access_token, data.refresh_token);
    return true;
  } catch {
    return false;
  }
}

async function api(path, options = {}) {
  const headers = options.headers || {};
  if (!headers["Content-Type"] && options.body !== undefined) headers["Content-Type"] = "application/json";
  if (App.token) headers["Authorization"] = `Bearer ${App.token}`;
  let res = await fetch(path, { ...options, headers });
  let data = await res.json().catch(() => ({}));
  if (res.status === 401) {
    const refreshed = await tryRefreshToken();
    if (refreshed) {
      headers["Authorization"] = `Bearer ${App.token}`;
      res = await fetch(path, { ...options, headers });
      data = await res.json().catch(() => ({}));
    }
  }
  if (!res.ok) throw new Error(data.detail || "Errore API");
  return data;
}

function temperatureBadge(temp) {
  const t = (temp || "").toUpperCase();
  if (t === "HOT") return "badge-hot";
  if (t === "WARM") return "badge-warm";
  return "badge-cold";
}

function appLayout(active, contentHtml) {
  return `
  <div class="page-shell">
    <header class="border-b border-slate-800 bg-slate-950/70 backdrop-blur">
      <div class="max-w-7xl mx-auto px-4 py-4 flex flex-wrap items-center gap-3 justify-between">
        <div>
          <h1 class="text-2xl font-bold">Agente AI Pro</h1>
          <p class="text-xs text-slate-400">AI Lead Generation CRM</p>
        </div>
        <div class="flex gap-2">
          <button class="btn btn-ghost" onclick="clearSession();navTo('/app/login')">Logout</button>
        </div>
      </div>
      <nav class="max-w-7xl mx-auto px-4 pb-4 flex flex-wrap gap-2 text-sm">
        ${[
          ["dashboard","Dashboard"],["search","Ricerca"],["leads","Lead"],["emails","Email"],["settings","Impostazioni"]
        ].map(([key,label]) =>
          `<a href="/app/${key}" class="px-3 py-2 rounded-lg border ${active===key?'bg-blue-600 border-blue-600':'border-slate-700 hover:bg-slate-800'}">${label}</a>`
        ).join("")}
      </nav>
    </header>
    <main class="max-w-7xl mx-auto px-4 py-6">${contentHtml}</main>
  </div>`;
}
