// LAN SSH Manager SPA — vanilla JS, no build step
const $ = (s) => document.querySelector(s);
const state = { token: localStorage.getItem("lsm_token") || "", user: "", machines: [], groups: [], cur: null, curTab: "overview" };

function toast(msg, err = false) {
  const t = $("#toast"); t.textContent = msg; t.classList.remove("hidden", "error");
  if (err) t.classList.add("error");
  setTimeout(() => t.classList.add("hidden"), 2600);
}
async function api(path, opts = {}) {
  const r = await fetch(path, { ...opts, headers: { "Content-Type": "application/json", ...(state.token ? { Authorization: "Bearer " + state.token } : {}), ...(opts.headers || {}) } });
  let j = null;
  try { j = await r.json(); } catch { throw new Error("HTTP " + r.status); }
  if (!r.ok) throw new Error((j && (j.detail || j.message)) || ("HTTP " + r.status));
  return j.success !== undefined ? j.data : j;
}
function esc(s) { return (s ?? "").toString().replace(/[&<>"'`]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#x27;", "`": "&#x60;" }[c])); }

// ---------- auth ----------
async function boot() {
  if (!state.token) return showLogin();
  try {
    const me = await api("/api/auth/me");
    state.user = me.username; enterApp();
  } catch { showLogin(); }
}
function showLogin() { $("#login-view").classList.remove("hidden"); $("#app").classList.add("hidden"); }
function enterApp() {
  $("#login-view").classList.add("hidden"); $("#app").classList.remove("hidden");
  $("#who").textContent = state.user || "";
  document.querySelectorAll(".nav button").forEach(b => b.onclick = () => show(b.dataset.view));
  loadSidebar(); show("dashboard");
}
$("#login-btn").onclick = async () => {
  $("#login-err").textContent = "";
  try {
    const d = await api("/api/auth/login", { method: "POST", body: JSON.stringify({ username: $("#login-user").value.trim(), password: $("#login-pass").value }) });
    state.token = d.token; localStorage.setItem("lsm_token", d.token); state.user = d.username; enterApp();
  } catch (e) { $("#login-err").textContent = e.message; }
};
$("#login-pass").addEventListener("keydown", e => { if (e.key === "Enter") $("#login-btn").click(); });
$("#logout-btn").onclick = async () => { try { if (typeof closeAllTerms === "function") closeAllTerms(); } catch {} try { if (typeof closeAllConsoles === "function") closeAllConsoles(); } catch {} try { await api("/api/auth/logout", { method: "POST" }); } catch {} state.token = ""; localStorage.removeItem("lsm_token"); location.reload(); };

// ---------- sidebar ----------
async function loadSidebar() {
  try {
    state.machines = await api("/api/machines");
    state.groups = await api("/api/groups");
  } catch (e) { state.machines = []; }
  $("#side-machines").innerHTML = state.machines.map(m =>
    `<div class="side-item" data-id="${m.id}"><span>🖥️ ${esc(m.name)}</span><span class="dot unknown" id="dot-${m.id}"></span></div>`).join("") || '<p class="muted">Chưa có máy. Vào Máy → Thêm.</p>';
  document.querySelectorAll(".side-item").forEach(el => el.onclick = () => openMachine(+el.dataset.id));
}

// ---------- views ----------
async function show(view) {
  document.querySelectorAll(".nav button").forEach(b => b.classList.toggle("active", b.dataset.view === view));
  try { $("#content").classList.remove("wide"); } catch {}
  const c = $("#content");
  if (view === "dashboard") return viewDashboard(c);
  if (view === "machines") return viewMachines(c);
  if (view === "commands") return viewBatch(c);
  if (view === "consoles") return viewConsoles(c);
  if (view === "audit") return viewAudit(c);
  if (view === "groups") return viewGroups(c);
  if (view === "fun") return (typeof viewFun === "function" ? viewFun(c) : (c.innerHTML = "<h2>🎬 Giải trí</h2><p class='err'>Không tải được entertainment.js</p>"));
}

async function viewDashboard(c) {
  c.innerHTML = "<h2>Tổng quan</h2><p class='muted'>Đang kiểm tra trạng thái SSH...</p>";
  try {
    const d = await api("/api/dashboard");
    d.machines.forEach(m => { const dot = $("#dot-" + m.id); if (dot) dot.className = "dot " + (m.status === "online" ? "online" : m.status === "offline" ? "offline" : "unknown"); });
    const pct = d.total ? Math.round(d.online / d.total * 100) : 0;
    const offPct = d.total ? Math.round(d.offline / d.total * 100) : 0;
    const pill = (s) => s === "online" ? `<span class="pill ok">● Trực tuyến</span>`
      : s === "offline" ? `<span class="pill bad">● Ngoại tuyến</span>`
      : `<span class="pill mute">● Không rõ</span>`;
    c.innerHTML = `<h2>📊 Tổng quan</h2>
      <div class="dash-top">
        <div class="stats">
          <div class="stat total"><div class="s-label">🖥️ Tổng số máy</div><div class="num">${d.total}</div></div>
          <div class="stat online"><div class="s-label">🟢 Trực tuyến</div><div class="num">${d.online}</div></div>
          <div class="stat offline"><div class="s-label">🔴 Ngoại tuyến</div><div class="num">${d.offline}</div></div>
          <div class="stat disabled"><div class="s-label">⚪ Tắt/Không rõ</div><div class="num">${d.disabled}</div></div>
        </div>
        <div class="health card">
          <div class="donut" style="background:conic-gradient(#22c55e 0 ${pct}%, #334155 ${pct}% 100%)"><span>${pct}%</span></div>
          <div class="muted">tỷ lệ trực tuyến</div>
          <div class="healthbar"><span class="hb-ok" style="width:${pct}%"></span><span class="hb-bad" style="width:${offPct}%"></span></div>
        </div>
      </div>
      <table class="mach-table"><tr><th>Máy</th><th>Địa chỉ</th><th>Trạng thái</th><th></th></tr>
      ${d.machines.map(m => `<tr><td>🖥️ <b>${esc(m.name)}</b>${m.enabled ? "" : ' <span class="pill mute">tắt</span>'}</td><td class="mono">${esc(m.hostname)}</td><td>${pill(m.status)}</td><td><button class="btn small" onclick="openMachine(${m.id})">Mở</button></td></tr>`).join("") || `<tr><td colspan="4" class="muted">Chưa có máy. Vào Máy → Thêm.</td></tr>`}
      </table>
      <p class="muted">Tự động kiểm tra kết nối SSH (timeout ngắn). Chi tiết CPU/RAM/ổ đĩa xem trong từng máy → Tổng quan.</p>`;
  } catch (e) { c.innerHTML = `<h2>Tổng quan</h2><p class="err">${esc(e.message)}</p>`; }
}

async function viewMachines(c) {
  const ms = await api("/api/machines");
  c.innerHTML = `<h2>Máy <button class="btn ok small" onclick="machineModal()">+ Thêm máy</button></h2>
    <table><tr><th>Tên</th><th>Địa chỉ</th><th>Người dùng</th><th>Xác thực</th><th>Nhóm</th><th>Kiểm tra</th><th>Thao tác</th></tr>
    ${ms.map(m => `<tr><td><b>${esc(m.name)}</b><br><span class="muted">${esc(m.description || "")}</span></td>
      <td>${esc(m.hostname)}:${m.port}</td><td>${esc(m.username)}</td><td><span class="badge">${m.auth_type}</span></td>
      <td>${esc(groupName(m.group_id))}</td>
      <td><button class="btn small" onclick="testSSH(${m.id},this)">Kiểm tra</button> <span id="t${m.id}"></span></td>
      <td><button class="btn small" onclick="openMachine(${m.id})">Mở</button>
      <button class="btn small" onclick='machineModal(${m.id})'>Sửa</button>
      <button class="btn small danger" onclick="delMachine(${m.id})">Xóa</button></td></tr>`).join("")}</table>`;
}
function groupName(gid) { const g = state.groups.find(g => g.id === gid); return g ? g.name : "—"; }

window.machineModal = async (id) => {
  const gs = await api("/api/groups").catch(() => []);
  let m = null;
  if (id) m = await api("/api/machines/" + id);
  const gopts = `<option value="">— không nhóm —</option>` + gs.map(g => `<option value="${g.id}" ${m && m.group_id === g.id ? "selected" : ""}>${esc(g.name)}</option>`).join("");
  openModal(`<h3>${m ? "Sửa" : "Thêm"} máy</h3>
    <input id="f-name" placeholder="Tên (server01)" value="${esc(m?.name || "")}">
    <input id="f-host" placeholder="Hostname/IP (192.168.1.10)" value="${esc(m?.hostname || "")}">
    <div class="grid2"><input id="f-port" type="number" value="${m?.port || 22}"><input id="f-user" placeholder="Người dùng SSH" value="${esc(m?.username || "")}"></div>
    <div class="grid2"><select id="f-auth"><option value="password" ${m?.auth_type !== "key" ? "selected" : ""}>Mật khẩu</option><option value="key" ${m?.auth_type === "key" ? "selected" : ""}>Khóa SSH</option></select>
    <select id="f-group">${gopts}</select></div>
    <input id="f-cred" type="password" placeholder="${m ? "(để trống = giữ thông tin cũ)" : "Mật khẩu hoặc nội dung private key"}">
    <input id="f-desc" placeholder="Mô tả" value="${esc(m?.description || "")}">
    <div class="row"><button class="btn" onclick="closeModal()">Hủy</button><button class="btn primary" style="width:auto" onclick="saveMachine(${id || 0})">Lưu</button></div>`);
};
window.saveMachine = async (id) => {
  const body = { name: $("#f-name").value.trim(), hostname: $("#f-host").value.trim(), port: +$("#f-port").value || 22, username: $("#f-user").value.trim(), auth_type: $("#f-auth").value, credential: $("#f-cred").value, group_id: $("#f-group").value ? +$("#f-group").value : null, description: $("#f-desc").value };
  try {
    if (id) await api("/api/machines/" + id, { method: "PUT", body: JSON.stringify(body) });
    else await api("/api/machines", { method: "POST", body: JSON.stringify(body) });
    closeModal(); toast("Đã lưu"); loadSidebar(); show("machines");
  } catch (e) { toast(e.message, true); }
};
window.delMachine = async (id) => { if (!confirm("Xóa máy này?")) return; await api("/api/machines/" + id, { method: "DELETE" }); toast("Đã xóa"); loadSidebar(); show("machines"); };
window.testSSH = async (id, btn) => {
  const sp = $("#t" + id); if (sp) sp.textContent = "⏳...";
  try { const d = await api(`/api/machines/${id}/test`, { method: "POST" }); if (sp) sp.textContent = "✅ OK"; toast(d.message || "SSH OK"); }
  catch (e) { if (sp) sp.textContent = "❌ Lỗi"; toast(e.message, true); }
};

// ---------- machine detail ----------
window.openMachine = async (id) => {
  state.cur = id; state.curTab = "overview";
  document.querySelectorAll(".side-item").forEach(el => el.classList.toggle("active", +el.dataset.id === id));
  renderMachineShell();
};
function renderMachineShell() {
  const m = state.machines.find(x => x.id === state.cur);
  const name = m ? m.name : ("#" + state.cur);
  const TAB_VI = { overview: "Tổng quan", terminal: "Terminal", command: "Lệnh", files: "Tệp tin", users: "Người dùng", services: "Dịch vụ", logs: "Nhật ký" };
  $("#content").innerHTML = `<h2>🖥️ ${esc(name)}</h2>
    <div class="tabs">${["overview", "terminal", "command", "files", "users", "services", "logs"].map(t => `<button data-t="${t}" class="${state.curTab === t ? "active" : ""}" onclick="setTab('${t}')">${TAB_VI[t] || t}</button>`).join("")}</div>
    <div id="tab-body"><p class="muted">Đang tải...</p></div>`;
  renderTab();
}
window.setTab = (t) => { state.curTab = t; renderMachineShell(); };
async function renderTab() {
  const id = state.cur, el = $("#tab-body");
  try { $("#content").classList.remove("wide"); } catch {}
  try {
    if (state.curTab === "overview") {
      el.innerHTML = "<p class='muted'>Đang thu thập thông tin hệ thống qua SSH...</p>";
      const info = await api(`/api/machines/${id}/system`);
      el.innerHTML = `<div class="grid2"><div class="card"><h4>Tóm tắt</h4><pre class="out">Uptime: ${esc(info.summary?.uptime || "")}\nLoad: ${esc((info.summary?.load || []).join(" "))}\n${esc(info.summary?.mem || "")}\n${esc(info.summary?.disk || "")}</pre></div>
      <div class="card"><h4>OS / Kernel</h4><pre class="out">${esc(info.os || "")}\nKernel: ${esc(info.kernel || "")}\nHost: ${esc(info.hostname || "")}</pre></div></div>
      <h4>CPU / Tải</h4><pre class="out">${esc(info.cpu || "")}</pre>
      <h4>Bộ nhớ</h4><pre class="out">${esc(info.memory || "")}</pre>
      <h4>Ổ đĩa</h4><pre class="out">${esc(info.disk || "")}</pre>
      <h4>Mạng</h4><pre class="out">${esc(info.network || "")}</pre>`;
    }
    if (state.curTab === "terminal") {
      try { $("#content").classList.add("wide"); } catch {}
      el.innerHTML = `<p class="muted">Web terminal realtime (xterm.js ↔ WebSocket ↔ SSH). Session được giữ khi chuyển tab — chỉ mất khi bấm "Đóng session", mất mạng hoặc token hết hạn. Bấm vào khung đen nếu mất con trỏ.</p><div id="term-slot"></div>
      <div id="term-status" class="muted" style="margin-top:4px"></div>
      <div class="row" style="justify-content:flex-start"><button class="btn small" onclick="termZoom(-2)" title="Thu nhỏ chữ terminal">A−</button><span id="term-zoom-label" class="muted"></span><button class="btn small" onclick="termZoom(2)" title="Phóng to chữ terminal">A+</button><button class="btn small" onclick="reconnectTerm()">Kết nối lại</button><button class="btn small danger" onclick="closeTerm()">Đóng session</button></div>`;
      termZoomLabel();
      attachTerm(id);
    }
    if (state.curTab === "command") {
      el.innerHTML = `<div class="grid2"><input id="cmd-in" placeholder="vd: uptime"><input id="cmd-to" type="number" value="30" title="Thời gian chờ (giây)"></div>
      <div class="row" style="justify-content:flex-start"><button class="btn primary" style="width:auto" onclick="runCmd(${id})">Chạy (ghi audit + timeout)</button></div><pre class="out" id="cmd-out">Chưa chạy.</pre>`;
    }
    if (state.curTab === "files") {
      const m = state.machines.find(x => x.id === id);
      const home = m ? (m.username === "root" ? "/root" : `/home/${m.username}`) : "/tmp";
      el.innerHTML = `<p class="muted">Đang dùng người dùng SSH <b>${esc(m?.username || "")}</b> — mặc định mở <b>${esc(home)}</b> (người dùng thường không có quyền đọc /root).</p><div class="row" style="justify-content:flex-start"><input id="f-path" value="${esc(home)}" style="flex:1"><button class="btn small" onclick="listFiles()">Xem</button>
      <button class="btn small" onclick="mkDir()">+ Thư mục</button></div><div id="f-list"></div>
      <h4>Soạn thảo (tệp text ≤512KB)</h4><input id="f-edit-path" placeholder="${esc(home)}/app.conf"><textarea id="f-edit" rows="10"></textarea>
      <div class="row" style="justify-content:flex-start"><button class="btn small" onclick="readFile()">Đọc</button><button class="btn small ok" onclick="writeFile()">Lưu</button></div>
      <h4>Tải lên (giữ nguyên tên tệp, đích = thư mục đang xem; tệp lớn tự chia chunk 8MB, có resume)</h4><div class="row" style="justify-content:flex-start"><input type="file" id="f-up" multiple><input id="f-up-dest" placeholder="thư mục đích (trống = thư mục đang xem)"><button class="btn small" onclick="pickDestDir()">Chọn...</button><button class="btn small" onclick="uploadFile()">Tải lên</button><button class="btn small danger" onclick="cancelUpload()">Hủy</button></div><div id="up-prog"></div>`;
      listFiles();
    }
    if (state.curTab === "users") {
      const m = state.machines.find(x => x.id === id);
      el.innerHTML = `<p class="muted">Quản lý người dùng Linux trên máy (useradd/userdel/passwd). Thao tác cần quyền root — SSH đang dùng người dùng <b>${esc(m?.username || "")}</b>${m?.username === "root" ? "" : " (sẽ dùng sudo -n, cần sudo NOPASSWD)"}.</p>
      <div class="row" style="justify-content:flex-start"><input id="u-name" placeholder="tên người dùng mới" style="max-width:200px"><input id="u-pass" type="password" placeholder="mật khẩu (≥4 ký tự)" style="max-width:200px"><button class="btn small ok" onclick="addOSUser()">+ Thêm người dùng</button>
      <button class="btn small" onclick="renderTab()">↻ Tải lại</button></div><div id="u-list"><p class="muted">Đang tải...</p></div>`;
      loadOSUsers();
    }
    if (state.curTab === "services") {
      el.innerHTML = `<p class="muted">Hành động cho phép: start/stop/restart/status/enable/disable. Tên dịch vụ được kiểm tra.</p>
      <div class="row" style="justify-content:flex-start"><input id="svc-name" placeholder="nginx"><button class="btn small" onclick="svcAct('status')">Trạng thái</button>
      <button class="btn small ok" onclick="svcAct('start')">Khởi động</button><button class="btn small danger" onclick="svcAct('stop')">Dừng</button>
      <button class="btn small" onclick="svcAct('restart')">Khởi động lại</button></div><pre class="out" id="svc-out"></pre><h4>Dịch vụ đang chạy</h4><pre class="out" id="svc-list">Đang tải...</pre>`;
      try { const d = await api(`/api/machines/${id}/services`); $("#svc-list").textContent = d.running; } catch (e) { $("#svc-list").textContent = e.message; }
    }
    if (state.curTab === "logs") {
      el.innerHTML = `<div class="row" style="justify-content:flex-start"><input id="log-svc" placeholder="dịch vụ (trống = hệ thống)"><input id="log-n" type="number" value="100"><button class="btn small" onclick="viewLogs()">Xem nhật ký</button></div><pre class="out" id="log-out"></pre>`;
    }
  } catch (e) { el.innerHTML = `<p class="err">${esc(e.message)}</p>`; }
}
window.runCmd = async (id) => {
  const cmd = $("#cmd-in").value, to = +$("#cmd-to").value || 30;
  $("#cmd-out").textContent = "⏳ đang chạy...";
  try { const r = await api(`/api/machines/${id}/command`, { method: "POST", body: JSON.stringify({ command: cmd, timeout: to }) }); $("#cmd-out").textContent = `$ ${cmd}\nexit=${r.exit_code} (${r.duration_ms}ms)\n--- stdout ---\n${r.stdout}\n--- stderr ---\n${r.stderr}`; }
  catch (e) { $("#cmd-out").textContent = "LỖI: " + e.message; }
};
const SVC_VI = { status: "Trạng thái", start: "Khởi động", stop: "Dừng", restart: "Khởi động lại" };
window.svcAct = async (a) => {
  const n = $("#svc-name").value.trim(); if (!n) return toast("Nhập tên dịch vụ", true);
  if (["stop", "restart"].includes(a) && !confirm(`${SVC_VI[a] || a} ${n} trên máy này?`)) return;
  $("#svc-out").textContent = "⏳...";
  try { const r = await api(`/api/machines/${state.cur}/services/${encodeURIComponent(n)}/${a}`, { method: "POST" }); $("#svc-out").textContent = r.stdout || JSON.stringify(r); }
  catch (e) { $("#svc-out").textContent = "LỖI: " + e.message; }
};
window.viewLogs = async () => {
  const svc = $("#log-svc").value.trim(), n = +$("#log-n").value || 100;
  $("#log-out").textContent = "⏳...";
  try { const r = await api(`/api/machines/${state.cur}/logs`, { method: "POST", body: JSON.stringify({ service: svc, lines: n }) }); $("#log-out").textContent = r.output || "(trống)"; }
  catch (e) { $("#log-out").textContent = "LỖI: " + e.message; }
};
// files
window.listFiles = async () => {
  const m = state.machines.find(x => x.id === state.cur);
  const home = m ? (m.username === "root" ? "/root" : `/home/${m.username}`) : "/tmp";
  const p = $("#f-path").value || home;
  $("#f-list").innerHTML = "⏳...";
  try {
    const d = await api(`/api/machines/${state.cur}/files?path=${encodeURIComponent(p)}`);
    window._flist = d.entries; window._fbase = p;
    $("#f-list").innerHTML = d.entries.map((e, i) => `<div class="file-row"><span>${e.is_dir ? "📁" : "📄"} ${esc(e.name)} <span class="muted">${e.is_dir ? "" : (e.size + "B")} ${esc(e.permissions || "")}</span></span>
      <span><button class="btn small" data-fact="open" data-i="${i}">Mở</button>
      <button class="btn small" data-fact="rename" data-i="${i}">Đổi tên</button>
      <button class="btn small danger" data-fact="del" data-i="${i}">Xóa</button></span></div>`).join("") || "(trống)";
    $("#f-list").querySelectorAll("button[data-fact]").forEach(b => b.onclick = () => {
      const e = (window._flist || [])[+b.dataset.i]; if (!e) return;
      const base = window._fbase || p;
      const full = base.replace(/\/$/, "") + "/" + e.name;
      if (b.dataset.fact === "open") fileGo(base, e.name, e.is_dir);
      else if (b.dataset.fact === "rename") fileRename(full);
      else if (b.dataset.fact === "del") fileDel(full);
    });
  } catch (e) { $("#f-list").innerHTML = `<span class="err">${esc(e.message)}</span>`; }
};
window.fileGo = (base, name, isDir) => { const p = base.replace(/\/$/, "") + "/" + name; if (isDir) { $("#f-path").value = p; listFiles(); } else { $("#f-edit-path").value = p; readFile(); } };
window.fileDel = async (p) => { if (!confirm("Xóa " + p + "?")) return; await api(`/api/machines/${state.cur}/files/action`, { method: "POST", body: JSON.stringify({ action: "delete", path: p }) }); toast("Đã xóa"); listFiles(); };
window.fileRename = async (p) => { const np = prompt("Tên mới (đường dẫn đầy đủ):", p); if (!np) return; await api(`/api/machines/${state.cur}/files/action`, { method: "POST", body: JSON.stringify({ action: "rename", path: p, new_path: np }) }); toast("Đã đổi tên"); listFiles(); };
window.mkDir = async () => { const m = state.machines.find(x => x.id === state.cur); const home = m ? (m.username === "root" ? "/root" : `/home/${m.username}`) : "/tmp"; const n = prompt("Đường dẫn thư mục mới:", ($("#f-path").value || home) + "/newdir"); if (!n) return; await api(`/api/machines/${state.cur}/files/action`, { method: "POST", body: JSON.stringify({ action: "mkdir", path: n }) }); toast("Đã tạo"); listFiles(); };
window.readFile = async () => { const p = $("#f-edit-path").value; try { const d = await api(`/api/machines/${state.cur}/files/read?path=${encodeURIComponent(p)}`); $("#f-edit").value = d.content; } catch (e) { toast(e.message, true); } };
window.writeFile = async () => { try { await api(`/api/machines/${state.cur}/files/write`, { method: "POST", body: JSON.stringify({ path: $("#f-edit-path").value, content: $("#f-edit").value }) }); toast("Đã lưu"); } catch (e) { toast(e.message, true); } };
const CHUNK = 8 * 1024 * 1024; // 8MB/chunk — RAM-safe cho tệp nhiều GB
window._upCancel = false;
window.cancelUpload = () => { window._upCancel = true; toast("Đã yêu cầu hủy (chunk tiếp theo sẽ dừng)"); };
function upProg(html) { const e = $("#up-prog"); if (e) e.innerHTML = html; }
function fmtMB(n) { return (n / 1048576).toFixed(1) + "MB"; }
async function upStatus(dest) {
  return await api(`/api/machines/${state.cur}/files/upload/status?remote_path=${encodeURIComponent(dest)}`);
}
async function upOneChunk(dest, offset, blob) {
  const fd = new FormData(); fd.append("f", blob, "chunk");
  const r = await fetch(`/api/machines/${state.cur}/files/upload/chunk?remote_path=${encodeURIComponent(dest)}&offset=${offset}`,
    { method: "POST", headers: { Authorization: "Bearer " + state.token }, body: fd });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) {
    const msg = j.detail || j.message || ("HTTP " + r.status);
    const err = new Error(msg); err.status = r.status; err.serverSize = null;
    try {
      const m = /đang có (\d+) bytes/.exec(msg);
      if (r.status === 409 && m) err.serverSize = +m[1];
    } catch {}
    throw err;
  }
  const data = j.success !== undefined ? j.data : j;
  return data.size;
}
window.uploadFile = async () => {
  const files = $("#f-up").files;
  if (!files.length) return toast("Chọn tệp cần tải lên", true);
  const dir = (($("#f-up-dest").value || $("#f-path").value || "/tmp")).replace(/\/+$/, "") || "/";
  if (dir.includes("..")) return toast("Thư mục đích không hợp lệ", true);
  $("#f-up-dest").value = dir;
  window._upCancel = false;
  let done = 0;
  for (const f of files) {
    if (window._upCancel) break;
    if (!f.name || f.name.includes("/") || f.name.includes("\\") || f.name.includes("..")) {
      toast(`Tên tệp không hợp lệ: ${f.name}`, true); continue;
    }
    const dest = `${dir === "/" ? "" : dir}/${f.name}`;
    try {
      if (f.size <= 16 * 1024 * 1024) {
        // tệp nhỏ: 1 request như cũ
        upProg(`<p class="muted">${esc(f.name)} (${fmtMB(f.size)}) — đang tải lên...</p>`);
        const fd = new FormData(); fd.append("f", f);
        const r = await fetch(`/api/machines/${state.cur}/files/upload?remote_path=${encodeURIComponent(dest)}`,
          { method: "POST", headers: { Authorization: "Bearer " + state.token }, body: fd });
        const j = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(j.detail || j.message || ("HTTP " + r.status));
        done++;
      } else {
        // tệp lớn: resume từ server rồi gửi từng chunk, retry 3 lần/chunk
        let off = (await upStatus(dest)).size;
        if (off > f.size) throw new Error(`Tệp đích lớn hơn tệp nguồn (${fmtMB(off)} > ${fmtMB(f.size)}) — xóa đích rồi tải lại`);
        if (off === f.size && f.size > 0) {
          await api(`/api/machines/${state.cur}/files/upload/complete`,
            { method: "POST", body: JSON.stringify({ remote_path: dest, total_size: f.size }) });
          done++; continue;
        }
        while (off < f.size) {
          if (window._upCancel) throw new Error("Đã hủy bởi người dùng");
          const end = Math.min(off + CHUNK, f.size);
          upProg(`<p class="muted">${esc(f.name)} — ${fmtMB(off)}/${fmtMB(f.size)} (${Math.round(off / f.size * 100)}%)</p><progress value="${off}" max="${f.size}" style="width:100%"></progress>`);
          let ok = false, lastErr = null;
          for (let t = 0; t < 3 && !ok; t++) {
            try { off = await upOneChunk(dest, off, f.slice(off, end)); ok = true; }
            catch (e) {
              lastErr = e;
              if (e.status === 409 && e.serverSize !== null && e.serverSize !== undefined) { off = e.serverSize; ok = true; }
              else await new Promise(r => setTimeout(r, 1500));
            }
          }
          if (!ok) throw lastErr;
        }
        await api(`/api/machines/${state.cur}/files/upload/complete`,
          { method: "POST", body: JSON.stringify({ remote_path: dest, total_size: f.size }) });
        done++;
        upProg(`<p class="muted">✅ ${esc(f.name)} (${fmtMB(f.size)}) xong</p>`);
      }
    } catch (e) { upProg(`<p class="err">${esc(f.name)}: ${esc(e.message)} (đã tải được 1 phần — bấm Tải lên lại để resume)</p>`); }
  }
  if (done) { toast(`Đã tải lên ${done}/${files.length} tệp vào ${dir}`); $("#f-path").value = dir; listFiles(); }
};

// ---------- remote dir picker (upload đích) ----------
window._pickCur = "/";
window.pickDestDir = async (start) => {
  const m = state.machines.find(x => x.id === state.cur);
  const home = m ? (m.username === "root" ? "/root" : `/home/${m.username}`) : "/tmp";
  window._pickCur = start || $("#f-up-dest").value || $("#f-path").value || home;
  openModal(`<h3>Chọn thư mục đích trên máy SSH</h3>
    <p class="muted" id="pick-cur"></p><div id="pick-list"></div>
    <div class="row"><button class="btn" onclick="closeModal()">Hủy</button>
    <button class="btn primary" style="width:auto" onclick="setDestDir()">Dùng thư mục này</button></div>`);
  await renderPickDir();
};
async function renderPickDir() {
  const cur = window._pickCur;
  $("#pick-cur").textContent = cur;
  const box = $("#pick-list"); box.innerHTML = "⏳...";
  try {
    const d = await api(`/api/machines/${state.cur}/files?path=${encodeURIComponent(cur)}`);
    const dirs = d.entries.filter(e => e.is_dir);
    box.innerHTML = (cur !== "/" ? `<div class="file-row"><span>📁 ..</span><span><button class="btn small" data-pick="up">Mở</button></span></div>` : "")
      + dirs.map(e => `<div class="file-row"><span>📁 ${esc(e.name)}</span><span><button class="btn small" data-pick="${esc(e.name)}">Mở</button></span></div>`).join("")
      || "(không có thư mục con)";
    box.querySelectorAll("[data-pick]").forEach(b => b.onclick = () => {
      const v = b.dataset.pick;
      window._pickCur = v === "up"
        ? (window._pickCur.replace(/\/[^/]+\/?$/, "") || "/")
        : (window._pickCur.replace(/\/$/, "") + "/" + v);
      renderPickDir();
    });
  } catch (e) { box.innerHTML = `<span class="err">${esc(e.message)}</span>`; }
}
window.setDestDir = () => {
  const inp = $("#f-up-dest"); if (inp) inp.value = window._pickCur;
  closeModal(); toast("Đích tải lên: " + window._pickCur);
};

// ---------- OS users ----------
window.loadOSUsers = async () => {
  const box = $("#u-list"); if (!box) return;
  box.innerHTML = "<p class='muted'>Đang tải...</p>";
  try {
    const d = await api(`/api/machines/${state.cur}/users`);
    window._ulist = d;
    box.innerHTML = `<table><tr><th>Người dùng</th><th>UID</th><th>Thư mục home</th><th>Shell</th><th>Trạng thái</th><th>Thao tác</th></tr>
    ${d.map((u, i) => `<tr><td><b>${esc(u.name)}</b></td><td>${u.uid}</td><td>${esc(u.home)}</td><td>${esc(u.shell)}</td>
      <td><span class="badge">${esc(u.status)}</span></td>
      <td><button class="btn small" data-uact="passwd" data-i="${i}">Đổi mật khẩu</button>
      ${u.status === "locked"
        ? `<button class="btn small ok" data-uact="unlock" data-i="${i}">Mở khóa</button>`
        : `<button class="btn small" data-uact="lock" data-i="${i}">Khóa</button>`}
      <button class="btn small danger" data-uact="del" data-i="${i}">Xóa</button></td></tr>`).join("")}</table>`;
    box.querySelectorAll("button[data-uact]").forEach(b => b.onclick = () => {
      const u = (window._ulist || [])[+b.dataset.i]; if (!u) return;
      if (b.dataset.uact === "passwd") passwdOSUser(u.name);
      else if (b.dataset.uact === "lock") lockOSUser(u.name, "lock");
      else if (b.dataset.uact === "unlock") lockOSUser(u.name, "unlock");
      else if (b.dataset.uact === "del") delOSUser(u.name);
    });
  } catch (e) { box.innerHTML = `<span class="err">${esc(e.message)}</span>`; }
};
window.addOSUser = async () => {
  const n = $("#u-name").value.trim(), p = $("#u-pass").value;
  if (!n) return toast("Nhập tên người dùng", true);
  if (!confirm(`Tạo người dùng Linux '${n}' trên máy này?`)) return;
  try {
    const d = await api(`/api/machines/${state.cur}/users`, { method: "POST", body: JSON.stringify({ username: n, password: p }) });
    toast(d?.name ? `Đã tạo người dùng ${d.name}` : "Đã tạo"); $("#u-name").value = ""; $("#u-pass").value = ""; loadOSUsers();
  } catch (e) { toast(e.message, true); }
};
window.delOSUser = async (n) => {
  if (!confirm(`Xóa người dùng '${n}' trên máy này?`)) return;
  const remove_home = confirm(`Xóa CẢ thư mục home của '${n}'?\nOK = xóa cả home, Cancel = giữ home.`);
  try { await api(`/api/machines/${state.cur}/users/${encodeURIComponent(n)}?remove_home=${remove_home}`, { method: "DELETE" }); toast("Đã xóa"); loadOSUsers(); }
  catch (e) { toast(e.message, true); }
};
window.passwdOSUser = async (n) => {
  const p = prompt(`Mật khẩu mới cho '${n}' (≥4 ký tự):`);
  if (!p) return;
  try { await api(`/api/machines/${state.cur}/users/${encodeURIComponent(n)}/password`, { method: "POST", body: JSON.stringify({ password: p }) }); toast("Đã đổi mật khẩu"); }
  catch (e) { toast(e.message, true); }
};
window.lockOSUser = async (n, a) => {
  if (!confirm(`${a === "lock" ? "Khóa" : "Mở khóa"} người dùng '${n}'?`)) return;
  try { await api(`/api/machines/${state.cur}/users/${encodeURIComponent(n)}/${a}`, { method: "POST" }); toast(a === "lock" ? "Đã khóa" : "Đã mở khóa"); loadOSUsers(); }
  catch (e) { toast(e.message, true); }
};

// ---------- terminal (giữ session sống khi chuyển tab) ----------
// Cache 1 session/máy: { box, term, fit, ws, id }. Chuyển tab chỉ di chuyển
// DOM node, không đóng WebSocket nên shell SSH + scrollback còn nguyên.
window._terms = window._terms || {};
window._termFont = Math.min(30, Math.max(12, parseInt(localStorage.getItem("lsm_term_font") || "18", 10) || 18));
function termZoomLabel() { try { const e = document.querySelector("#term-zoom-label"); if (e) e.textContent = window._termFont + "px"; } catch {} }
function termStatus(s) { try { const e = document.querySelector("#term-status"); if (e) e.textContent = s; } catch {} }
function getTerm(id) { return window._terms[id] || null; }
function attachTerm(id) {
  const slot = document.querySelector("#term-slot");
  if (!slot) return;
  const cur = getTerm(id);
  if (cur && cur.ws && (cur.ws.readyState === 0 || cur.ws.readyState === 1)) {
    // Session còn sống: gắn lại khung cũ, đo lại size, focus
    slot.appendChild(cur.box);
    try { if (cur.fit) cur.fit.fit(); } catch {}
    try {
      if (cur.ws.readyState === 1 && cur.term.cols > 0 && cur.term.rows > 0)
        cur.ws.send(JSON.stringify({ resize: [cur.term.cols, cur.term.rows] }));
    } catch {}
    termStatus(`terminal ${cur.term.cols}x${cur.term.rows} — đã kết nối (giữ nguyên session)`);
    cur.term.focus(); cur.term.scrollToBottom();
    return;
  }
  if (cur) { try { cur.ws.close(); } catch {} delete window._terms[id]; }
  openTerm(id);
}
function openTerm(id) {
  const slot = document.querySelector("#term-slot");
  if (!slot) return;
  if (typeof Terminal === "undefined") {
    slot.innerHTML = "<p class='err'>Không tải được xterm.js local (vendor/). Hãy Ctrl+F5 tải lại trang.</p>";
    return;
  }
  const box = document.createElement("div");
  box.className = "term-box";
  slot.appendChild(box);
  const term = new Terminal({ cursorBlink: true, cursorStyle: "block", fontSize: window._termFont, fontFamily: '"JetBrains Mono", Consolas, Menlo, "Courier New", monospace', lineHeight: 1.35, scrollback: 5000, convertEol: false, theme: { background: "#000" } });
  let fit = null;
  try { fit = new FitAddon.FitAddon(); term.loadAddon(fit); } catch (e) { fit = null; }
  term.open(box); try { if (fit) fit.fit(); } catch {} term.focus();
  // click vào khung terminal để hiện lại con trỏ (xterm ẩn cursor khi mất focus)
  try { box.addEventListener("click", () => term.focus()); } catch {}
  term.writeln("Đang kết nối SSH...");
  const cols = term.cols > 0 ? term.cols : 120, rows = term.rows > 0 ? term.rows : 32;
  termStatus(`terminal ${cols}x${rows} — đang kết nối...`);
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ws/terminal/${id}?token=${encodeURIComponent(state.token)}&cols=${cols}&rows=${rows}`);
  window._terms[id] = { box, term, fit, ws, id };
  window._termSock = ws; window._term = term; // giữ để tương thích nút Đóng cũ
  ws.onopen = () => {
    term.write("\r\n[đã kết nối]\r\n");
    // đo lại sau khi layout ổn định rồi báo server resize cho khớp pty (tránh lệch cursor)
    setTimeout(() => {
      try {
        if (fit) { fit.fit(); }
        if (ws.readyState === 1 && term.cols > 0 && term.rows > 0) {
          ws.send(JSON.stringify({ resize: [term.cols, term.rows] }));
        }
      } catch {}
      term.focus(); term.scrollToBottom();
    }, 300);
  };
  ws.onmessage = (ev) => {
    const d = ev.data;
    if (typeof d === "string") term.write(d);
    else if (d && typeof d.text === "function") d.text().then(t => term.write(t)).catch(() => {});
    else term.write(String(d));
  };
  ws.onerror = () => term.write("\r\n[lỗi WebSocket]\r\n");
  ws.onclose = (ev) => { termStatus(`đã ngắt kết nối code=${ev.code}`); term.write(`\r\n[ngắt kết nối code=${ev.code}${ev.reason ? " " + ev.reason : ""} — bấm "Kết nối lại" để mở session mới]\r\n`); };
  term.onData((d) => { if (ws.readyState === 1) ws.send(d); });
  term.onResize(({ cols, rows }) => { termStatus(`terminal ${cols}x${rows}`); if (ws.readyState === 1) ws.send(JSON.stringify({ resize: [cols, rows] })); });
  if (!window._termResizeHook) {
    window._termResizeHook = true;
    window.addEventListener("resize", () => { try { const t = getTerm(state.cur); if (t && t.fit && state.curTab === "terminal") t.fit.fit(); } catch {} });
  }
}
window.termZoom = (d) => {
  window._termFont = Math.min(30, Math.max(12, (window._termFont || 18) + (d || 0)));
  try { localStorage.setItem("lsm_term_font", String(window._termFont)); } catch {}
  termZoomLabel();
  try {
    const t = getTerm(state.cur);
    if (t && t.term) {
      t.term.setOption("fontSize", window._termFont);
      if (t.fit) t.fit.fit();
      // báo pty resize theo cols/rows mới để không lệch cursor
      try { if (t.ws && t.ws.readyState === 1 && t.term.cols > 0 && t.term.rows > 0) t.ws.send(JSON.stringify({ resize: [t.term.cols, t.term.rows] })); } catch {}
      t.term.focus();
    }
  } catch {}
  toast("Cỡ chữ terminal: " + window._termFont + "px");
};
window.reconnectTerm = () => { const id = state.cur; const cur = getTerm(id); if (cur) { try { cur.ws.close(); } catch {} delete window._terms[id]; } renderTab(); };
window.closeTerm = () => { const id = state.cur; const cur = getTerm(id); if (cur) { try { cur.ws.close(); } catch {} delete window._terms[id]; } window._termSock = null; toast("Đã đóng session"); renderTab(); };
function closeAllTerms() { Object.keys(window._terms || {}).forEach(id => { try { window._terms[id].ws.close(); } catch {} }); window._terms = {}; }

// ---------- batch ----------
async function viewBatch(c) {
  const ms = state.machines.length ? state.machines : await api("/api/machines");
  c.innerHTML = `<h2>Lệnh hàng loạt</h2><p class="muted">Chạy song song, giới hạn chạy đồng thời (concurrency=10, cấu hình MAX_CONCURRENT_SSH).</p>
  <div class="card">${ms.map(m => `<label style="display:block;margin:4px 0"><input type="checkbox" class="bchk" value="${m.id}" checked> ${esc(m.name)} <span class="muted">${esc(m.hostname)}</span></label>`).join("")}</div>
  <div class="grid2" style="margin-top:8px"><input id="b-cmd" placeholder="uptime"><input id="b-to" type="number" value="30"></div>
  <div class="row" style="justify-content:flex-start"><button class="btn primary" style="width:auto" onclick="runBatch()">Chạy hàng loạt</button></div><div id="b-out"></div>`;
}
window.runBatch = async () => {
  const ids = [...document.querySelectorAll(".bchk:checked")].map(x => +x.value);
  const cmd = $("#b-cmd").value, to = +$("#b-to").value || 30;
  if (!ids.length) return toast("Chọn ít nhất 1 máy", true);
  if (!confirm(`Chạy "${cmd}" trên ${ids.length} máy?`)) return;
  $("#b-out").innerHTML = "⏳ đang chạy...";
  try {
    const d = await api("/api/commands/batch", { method: "POST", body: JSON.stringify({ machine_ids: ids, command: cmd, timeout: to }) });
    $("#b-out").innerHTML = `<p>OK ${d.summary.ok}/${d.summary.total}</p>` + d.results.map(r => `<div class="card" style="margin-bottom:8px"><b>${r.success ? "✅" : "❌"} ${esc(r.machine_name)}</b> exit=${r.exit_code} ${r.duration_ms}ms<pre class="out">${esc((r.stdout || r.stderr || "").slice(0, 2000))}</pre></div>`).join("");
  } catch (e) { $("#b-out").innerHTML = `<span class="err">${esc(e.message)}</span>`; }
};

// ---------- audit / groups ----------
async function viewAudit(c) {
  const rows = await api("/api/audit?limit=200");
  c.innerHTML = `<h2>Nhật ký audit</h2><table><tr><th>Thời gian</th><th>Người dùng</th><th>Máy</th><th>Hành động</th><th>Trạng thái</th><th>Lệnh</th></tr>
  ${rows.map(r => `<tr><td>${esc((r.created_at || "").replace("T", " ").slice(0, 19))}</td><td>${r.user_id ?? ""}</td><td>${r.machine_id ?? ""}</td><td><span class="badge">${esc(r.action)}</span></td><td>${esc(r.status)}</td><td>${esc((r.command || "").slice(0, 80))}</td></tr>`).join("")}</table>`;
}
async function viewGroups(c) {
  const gs = await api("/api/groups");
  c.innerHTML = `<h2>Nhóm <button class="btn ok small" onclick="addGroup()">+ Thêm</button></h2>
  <table><tr><th>Tên</th><th>Mô tả</th><th></th></tr>${gs.map(g => `<tr><td>${esc(g.name)}</td><td>${esc(g.description || "")}</td><td><button class="btn small danger" onclick="delGroup(${g.id})">Xóa</button></td></tr>`).join("")}</table>`;
}
window.addGroup = async () => { const n = prompt("Tên nhóm:"); if (!n) return; try { await api("/api/groups", { method: "POST", body: JSON.stringify({ name: n }) }); toast("Đã tạo"); loadSidebar(); show("groups"); } catch (e) { toast(e.message, true); } };
window.delGroup = async (id) => { if (!confirm("Xóa nhóm?")) return; await api("/api/groups/" + id, { method: "DELETE" }); toast("Đã xóa"); loadSidebar(); show("groups"); };

// ---------- serial console (máy chưa có OS — cài đặt qua cổng console vật lý) ----------
// 1 cổng chỉ mở được bởi 1 session: web (xterm↔WS) hoặc CLI (polling).
window._consoles = window._consoles || {};
let _conCur = null, _conPorts = [];
function conStatus(s) { try { const e = document.querySelector("#con-status"); if (e) e.textContent = s; } catch {} }
async function viewConsoles(c) {
  let d;
  try { d = await api("/api/consoles"); }
  catch (e) { c.innerHTML = `<h2>🔌 Console</h2><p class="err">${esc(e.message)}</p>`; return; }
  _conPorts = d.system_ports || [];
  const rows = d.consoles || [];
  const badge = (r) => r.in_use ? `<span class="pill bad">● Đang dùng</span>`
    : r.enabled ? `<span class="pill ok">● Rảnh</span>` : `<span class="pill mute">tắt</span>`;
  c.innerHTML = `<h2>🔌 Console <button class="btn ok small" onclick="consoleModal()">+ Thêm cổng</button></h2>
  <p class="muted">Máy chủ app phải <b>cắm cáp serial</b> tới cổng console của máy đích (USB-RS232).
  Mở console để thao tác BIOS/bootloader/bộ cài OS như ngồi trực tiếp. 1 cổng chỉ 1 người dùng tại 1 thời điểm.</p>
  <table><tr><th>Tên</th><th>Cổng</th><th>Baud</th><th>Máy liên kết</th><th>Trạng thái</th><th></th></tr>
  ${rows.map(r => `<tr><td><b>${esc(r.name)}</b>${r.enabled ? "" : ' <span class="pill mute">tắt</span>'}</td>
    <td class="mono">${esc(r.device)}</td><td>${r.baudrate}</td><td>${esc(r.machine_name || "")}</td><td>${badge(r)}</td>
    <td><button class="btn small" onclick="openConsole(${r.id})">Mở</button>
    <button class="btn small" onclick="consoleModal(${r.id})">Sửa</button>
    <button class="btn small danger" onclick="delConsole(${r.id})">Xóa</button></td></tr>`).join("")
    || `<tr><td colspan="6" class="muted">Chưa khai báo cổng nào. Bấm + Thêm cổng.</td></tr>`}</table>
  <p class="muted">Cổng serial thấy trên máy chủ: ${(_conPorts.map(p => `<span class="mono">${esc(p.device)}</span>`).join(", ")) || "(không thấy cổng nào)"}</p>
  <h3 id="con-title">Phiên console${_conCur ? " #" + _conCur : ""}</h3><div id="con-slot"></div>
  <div class="row" style="justify-content:flex-start"><span id="con-status" class="muted"></span></div>
  <div class="row" style="justify-content:flex-start"><button class="btn small" onclick="reconnectConsole()">Kết nối lại</button>
  <button class="btn small" onclick="sendConBreak()">Gửi BREAK</button>
  <button class="btn small" onclick="closeConsole()">Ngắt kết nối</button>
  <button class="btn small danger" onclick="releaseConsole()">Giải phóng kẹt</button></div>`;
  if (_conCur) attachConsole(_conCur);
}
function getConsole(id) { return window._consoles[id] || null; }
function attachConsole(id) {
  const slot = document.querySelector("#con-slot");
  if (!slot) return;
  const cur = getConsole(id);
  if (cur && cur.ws && (cur.ws.readyState === 0 || cur.ws.readyState === 1)) {
    slot.appendChild(cur.box);
    try { if (cur.fit) cur.fit.fit(); } catch {}
    conStatus(`console ${cur.term.cols}x${cur.term.rows} — đã kết nối (giữ nguyên session)`);
    cur.term.focus(); cur.term.scrollToBottom();
    return;
  }
  if (cur) { try { cur.ws.close(); } catch {} delete window._consoles[id]; }
  openConsole(id);
}
function openConsole(id) {
  const slot = document.querySelector("#con-slot");
  if (!slot) { _conCur = id; show("consoles"); return; }
  _conCur = id;
  try { const t = document.querySelector("#con-title"); if (t) t.textContent = "Phiên console #" + id; } catch {}
  if (typeof Terminal === "undefined") {
    slot.innerHTML = "<p class='err'>Không tải được xterm.js local (vendor/). Hãy Ctrl+F5 tải lại trang.</p>";
    return;
  }
  slot.innerHTML = "";
  const box = document.createElement("div");
  box.className = "term-box";
  slot.appendChild(box);
  const term = new Terminal({ cursorBlink: true, cursorStyle: "block", fontSize: 18, fontFamily: '"JetBrains Mono", Consolas, Menlo, "Courier New", monospace', lineHeight: 1.35, scrollback: 10000, theme: { background: "#000" } });
  let fit = null;
  try { fit = new FitAddon.FitAddon(); term.loadAddon(fit); } catch (e) { fit = null; }
  term.open(box); try { if (fit) fit.fit(); } catch {} term.focus();
  try { box.addEventListener("click", () => term.focus()); } catch {}
  term.writeln("Đang nối cổng console...");
  conStatus("đang kết nối...");
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ws/console/${id}?token=${encodeURIComponent(state.token)}`);
  window._consoles[id] = { box, term, fit, ws, id };
  ws.onopen = () => { setTimeout(() => { try { if (fit) fit.fit(); } catch {} term.focus(); term.scrollToBottom(); }, 300); };
  ws.onmessage = (ev) => {
    const d = ev.data;
    if (typeof d === "string") term.write(d);
    else if (d && typeof d.text === "function") d.text().then(t => term.write(t)).catch(() => {});
    else term.write(String(d));
  };
  ws.onerror = () => term.write("\r\n[lỗi WebSocket]\r\n");
  ws.onclose = (ev) => { conStatus(`đã ngắt kết nối code=${ev.code}`); term.write(`\r\n[ngắt kết nối code=${ev.code} — bấm "Kết nối lại" để mở phiên mới]\r\n`); };
  term.onData((d) => { if (ws.readyState === 1) ws.send(d); });
}
window.openConsole = openConsole;
window.reconnectConsole = () => { if (!_conCur) return toast("Chưa chọn cổng nào", true); const cur = getConsole(_conCur); if (cur) { try { cur.ws.close(); } catch {} delete window._consoles[_conCur]; } show("consoles"); };
window.closeConsole = () => { if (!_conCur) return; const cur = getConsole(_conCur); if (cur) { try { cur.ws.close(); } catch {} delete window._consoles[_conCur]; } toast("Đã ngắt console"); show("consoles"); };
window.sendConBreak = async () => { if (!_conCur) return toast("Chưa chọn cổng nào", true); try { await api(`/api/consoles/${_conCur}/break`, { method: "POST" }); toast("Đã gửi BREAK"); } catch (e) { toast(e.message, true); } };
window.releaseConsole = async () => { if (!_conCur) return toast("Chưa chọn cổng nào", true); try { await api(`/api/consoles/${_conCur}/release`, { method: "POST" }); toast("Đã giải phóng"); show("consoles"); } catch (e) { toast(e.message, true); } };
function closeAllConsoles() { Object.keys(window._consoles || {}).forEach(id => { try { window._consoles[id].ws.close(); } catch {} }); window._consoles = {}; _conCur = null; }
window.consoleModal = async (id) => {
  let row = null, ms = state.machines || [];
  try { if (!ms.length) ms = await api("/api/machines"); } catch {}
  if (id) {
    try { const d = await api("/api/consoles"); row = (d.consoles || []).find(r => r.id === id) || null; }
    catch (e) { return toast(e.message, true); }
  }
  const ports = _conPorts.length ? _conPorts : [];
  openModal(`<h3>${id ? "Sửa" : "Thêm"} cổng console</h3>
  <label>Tên</label><input id="c-name" value="${esc(row?.name || "")}" placeholder="Máy 04 - console">
  <label>Thiết bị serial (trên máy chủ app)</label>
  <input id="c-dev" list="c-ports" value="${esc(row?.device || (ports[0]?.device || "/dev/ttyUSB0"))}" placeholder="/dev/ttyUSB0">
  <datalist id="c-ports">${ports.map(p => `<option value="${esc(p.device)}">${esc(p.description || "")}</option>`).join("")}</datalist>
  <label>Baudrate (mặc định BIOS/IPMI console: 115200)</label>
  <select id="c-baud">${[9600, 19200, 38400, 57600, 115200, 230400].map(b => `<option value="${b}"${(row?.baudrate || 115200) === b ? " selected" : ""}>${b}</option>`).join("")}</select>
  <label>Máy liên kết (tùy chọn)</label>
  <select id="c-mid"><option value="">— không liên kết —</option>${ms.map(m => `<option value="${m.id}"${row?.machine_id === m.id ? " selected" : ""}>${esc(m.name)}</option>`).join("")}</select>
  <label>Mô tả</label><input id="c-desc" value="${esc(row?.description || "")}">
  <div class="row"><button class="btn" onclick="closeModal()">Hủy</button><button class="btn primary" style="width:auto" onclick="saveConsole(${id || 0})">Lưu</button></div>`);
};
window.saveConsole = async (id) => {
  const mid = $("#c-mid").value;
  const body = { name: $("#c-name").value.trim(), device: $("#c-dev").value.trim(),
    baudrate: +$("#c-baud").value, machine_id: mid ? +mid : null, description: $("#c-desc").value.trim() };
  try {
    if (id) await api(`/api/consoles/${id}`, { method: "PUT", body: JSON.stringify(body) });
    else await api("/api/consoles", { method: "POST", body: JSON.stringify(body) });
    closeModal(); toast("Đã lưu"); show("consoles");
  } catch (e) { toast(e.message, true); }
};
window.delConsole = async (id) => {
  if (!confirm("Xóa cổng console này?")) return;
  try { await api("/api/consoles/" + id, { method: "DELETE" }); toast("Đã xóa"); if (_conCur === id) _conCur = null; show("consoles"); }
  catch (e) { toast(e.message, true); }
};

// ---------- modal ----------
function openModal(html) { $("#modal-card").innerHTML = html; $("#modal").classList.remove("hidden"); }
window.closeModal = () => $("#modal").classList.add("hidden");
$("#modal").addEventListener("click", (e) => { if (e.target.id === "modal") closeModal(); });

boot();
