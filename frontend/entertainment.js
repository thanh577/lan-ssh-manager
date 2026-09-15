// View Giải trí — xem Dailymotion + YouTube trực tuyến (port vanilla từ app React xem_daylymotion)
// Dùng API công khai qua window.DM (frontend/dailymotion.js) và window.YT (frontend/youtube.js).
// Hai provider cùng API surface nên logic list/watch/channel/playlist tái sử dụng nguyên.
(function () {
  const PAGE = 12;
  const SRC_KEY = "fun.source.v1";
  const S = window._fun = window._fun || {
    source: (() => { try { return localStorage.getItem(SRC_KEY) === "yt" ? "yt" : "dm"; } catch { return "dm"; } })(),
    tab: "home", query: "", sort: "relevance",
    videos: [], page: 1, hasMore: false, total: 0, loading: false, error: "",
    urlInput: "", currentId: null, detail: null, related: [], relatedSource: "",
    relatedPlaylistId: null, relatedFilter: "", detailError: "", relLoading: false,
    wq: "", wqList: [], wqPage: 1, wqHasMore: false, wqLoading: false, wqError: "", wqSearched: false,
    queue: [], queueIndex: -1, queueMeta: null, queueLoading: false,
    autoNext: true, loopList: true,
    channelInput: "", channel: "", playlistInput: "", playlistMeta: null,
    saved: [],
  };
  try { S.saved = (S.source === "yt" && window.YT ? YT.loadSaved() : DM.loadSaved()); } catch { S.saved = []; }

  // Provider hiện tại — cùng shape nên gọi P().searchVideos(...) như nhau
  const P = () => (S.source === "yt" && window.YT ? window.YT : window.DM);
  const SRC_LABEL = () => (S.source === "yt" ? "YouTube" : "Dailymotion");

  function switchSource(src) {
    if (S.source === src) return;
    stopMini();
    S.source = src;
    try { localStorage.setItem(SRC_KEY, src); } catch {}
    S.tab = "home"; S.query = ""; S.videos = []; S.page = 1; S.hasMore = false; S.total = 0; S.error = "";
    S.currentId = null; S.detail = null; S.related = []; S.relatedSource = ""; S.relatedPlaylistId = null;
    S.wq = ""; S.wqList = []; S.wqPage = 1; S.wqHasMore = false; S.wqError = ""; S.wqSearched = false;
    S.queue = []; S.queueIndex = -1; S.queueMeta = null;
    S.channel = ""; S.channelInput = ""; S.playlistMeta = null; S.playlistInput = ""; S.urlInput = "";
    try { S.saved = P().loadSaved(); } catch { S.saved = []; }
    render();
    loadList(1, undefined);
  }

  const escH = (s) => (window.esc
    ? window.esc(s)
    : String(s ?? "").replace(/[&<>"'`]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#x27;", "`": "&#x60;" }[c])));
  const fmtDur = (s) => P().formatDuration(s);
  const fmtViews = (n) => P().formatViews(n);
  const fmtDate = (t) => P().formatDate(t);

  // ---- data loaders ----
  async function loadList(nextPage, mode, reset = true) {
    const api = P();
    S.loading = true; S.error = ""; rerender();
    try {
      let data;
      if (mode?.type === "channel") data = await api.userVideos(mode.owner, { page: nextPage, limit: PAGE, sort: "recent" });
      else if (mode?.type === "playlist") data = await api.playlistVideos(mode.id, { page: nextPage, limit: PAGE });
      else if (mode?.type === "search") data = await api.searchVideos({ query: mode.query, page: nextPage, limit: PAGE, sort: S.sort });
      else data = await api.trendingVideos({ page: nextPage, limit: PAGE });
      S.videos = reset ? (data.list ?? []) : [...S.videos, ...(data.list ?? [])];
      S.hasMore = Boolean(data.has_more);
      S.total = data.total ?? 0;
      S.page = nextPage;
    } catch (e) { S.error = e.message || "Không tải được dữ liệu."; }
    finally { S.loading = false; rerender(); }
  }

  async function openVideo(id, opts = {}) {
    const api = P();
    const vid = api.parseVideoId(id) || id;
    if (!vid) return;
    const playlistId = opts.playlistId ?? null;
    const keepQueue = opts.keepQueue ?? false;
    S.tab = "watch"; S.currentId = vid; S.detail = null; S.related = [];
    S.relatedSource = ""; S.relatedFilter = ""; S.detailError = ""; S.relLoading = true;
    if (!keepQueue && !playlistId) { S.queue = []; S.queueIndex = -1; S.queueMeta = null; S.relatedPlaylistId = null; }
    if (playlistId) S.relatedPlaylistId = playlistId;
    rerender();
    if (inFunView()) { try { document.querySelector("#content")?.scrollTo?.({ top: 0 }); } catch {} }
    try {
      const [d, r, p, meta] = await Promise.all([
        api.videoDetail(vid),
        api.relatedVideos(vid, { limit: 12 }).catch(() => ({ list: [] })),
        playlistId ? api.playlistVideos(playlistId, { page: 1, limit: 30 }).catch(() => null) : Promise.resolve(null),
        playlistId ? api.playlistInfo(playlistId).catch(() => null) : Promise.resolve(null),
      ]);
      S.detail = d;
      if (p?.list?.length) {
        S.related = p.list; S.relatedSource = "playlist";
        if (!keepQueue || !S.queue.length) {
          S.queue = p.list;
          const ix = p.list.findIndex((v) => v.id === vid);
          S.queueIndex = ix >= 0 ? ix : 0;
        } else { const ix = S.queue.findIndex((v) => v.id === vid); if (ix >= 0) S.queueIndex = ix; }
        if (meta) S.queueMeta = meta;
      } else if (r?.list?.length) {
        S.related = r.list; S.relatedSource = "related";
      } else {
        const owner = d?.["owner.id"] ?? d?.owner?.id ?? d?.["owner.screenname"];
        let done = false;
        if (owner) {
          try {
            const ch = await api.userVideos(owner, { limit: 12, sort: "recent" });
            if (ch?.list?.length) { S.related = ch.list.filter((v) => v.id !== vid); S.relatedSource = "channel"; done = true; }
          } catch {}
        }
        if (!done) {
          const kw = (Array.isArray(d?.tags) && d.tags[0]) || (d?.title ?? "").split(/\s+/).slice(0, 3).join(" ");
          if (kw) {
            try {
              const s = await api.searchVideos({ query: String(kw), limit: 12 });
              const list = (s?.list ?? []).filter((v) => v.id !== vid);
              if (list.length) { S.related = list; S.relatedSource = "search"; }
            } catch {}
          }
        }
      }
    } catch (e) { S.detailError = e.message || "Không tải được thông tin video."; }
    finally { S.relLoading = false; rerender(); }
  }

  async function playPlaylist(pid, startVid = null) {
    const api = P();
    const id = api.parsePlaylistId(pid) ?? pid;
    if (!id) return;
    S.tab = "watch"; S.queueLoading = true; S.detailError = ""; S.playlistInput = id;
    rerender();
    try {
      const [meta, all] = await Promise.all([
        api.playlistInfo(id).catch(() => null),
        api.fetchAllPlaylistVideos(id, { limitPerPage: 30, maxTotal: 100 }),
      ]);
      if (!all.length) throw new Error("Playlist trống hoặc không đọc được.");
      S.queue = all;
      S.queueMeta = meta ?? { id, name: `Playlist ${id}` };
      S.relatedPlaylistId = id;
      const si = startVid ? all.findIndex((v) => v.id === startVid) : 0;
      S.queueIndex = si >= 0 ? si : 0;
      S.queueLoading = false; rerender();
      await openVideo(all[S.queueIndex].id, { playlistId: id, keepQueue: true });
      S.queue = all; S.related = all; S.relatedSource = "playlist";
      if (meta) S.queueMeta = meta;
      rerender();
    } catch (e) { S.detailError = e.message || "Không tải được playlist."; }
    finally { S.queueLoading = false; rerender(); }
  }

  function playAt(idx) {
    if (idx < 0 || idx >= S.queue.length) return;
    S.queueIndex = idx;
    openVideo(S.queue[idx].id, { playlistId: S.relatedPlaylistId, keepQueue: true });
  }
  function playNext() {
    if (!S.queue.length) return;
    let n = S.queueIndex + 1;
    if (n >= S.queue.length) { if (!S.loopList) return; n = 0; }
    playAt(n);
  }
  function playPrev() {
    if (!S.queue.length) return;
    let p = S.queueIndex - 1;
    if (p < 0) { if (!S.loopList) return; p = S.queue.length - 1; }
    playAt(p);
  }

  // Tìm kiếm toàn cục trong tab Xem video (cả DM lẫn YT)
  async function doWatchSearch(page, reset = true) {
    const api = P();
    S.wqLoading = true; S.wqError = ""; S.wqSearched = true; rerender();
    try {
      const data = await api.searchVideos({ query: S.wq, page, limit: PAGE, sort: "relevance" });
      const list = data.list ?? [];
      S.wqList = reset ? list : [...S.wqList, ...list];
      S.wqHasMore = Boolean(data.has_more);
      S.wqPage = page;
    } catch (e) { S.wqError = e.message || "Không tìm kiếm được."; }
    finally { S.wqLoading = false; rerender(); }
  }

  // Tự phát tiếp khi player báo hết video (DM + YouTube)
  if (!window._funMsgHook) {
    window._funMsgHook = true;
    window.addEventListener("message", (e) => {
      try {
        const origin = String(e.origin ?? "");
        const isDM = origin.includes("dailymotion.com");
        const isYT = origin.includes("youtube");
        if (!isDM && !isYT) return;
        let ev = "";
        try { ev = DM.parsePlayerEvent(e.data).event || ""; } catch {}
        if (!ev || /^(state|info)/i.test(ev)) {
          try { ev = (window.YT ? YT.parsePlayerEvent(e.data).event : "") || ev; } catch {}
        }
        if (/^(end|video_end)$/i.test(ev || "")) {
          if (S.autoNext && S.queue.length > 1) playNext();
        }
      } catch {}
    });
  }

  function toggleSave(meta) {
    const api = P();
    const id = meta?.id ?? meta?.playlistId;
    if (!id) return;
    S.saved = S.saved.some((x) => String(x.id) === String(id))
      ? api.removeSaved(S.saved, id)
      : api.upsertSaved(S.saved, meta);
    api.persistSaved(S.saved);
    rerender();
  }
  const isSaved = (id) => (id != null) && S.saved.some((x) => String(x.id) === String(id));

  // ---- phát nền: giữ player sống khi rời view ----
  // iframe nằm trong #content nên chuyển tab là bị hủy. Khi rời đi, tách iframe
  // ra khung mini ngoài #content (cùng document nên không reload, phát tiếp);
  // quay lại tab Xem thì gắn trở vào. Tự chuyển bài (autoNext) vẫn chạy ở nền.
  const inFunView = () => !!document.querySelector("#fun-body");
  function rerender() { if (inFunView()) render(); else syncMini(); }
  function miniEl() {
    let h = document.querySelector("#fun-mini");
    if (!h) {
      h = document.createElement("div");
      h.id = "fun-mini";
      h.style.display = "none";
      h.innerHTML = `<div class="fun-mini-head"><b id="fun-mini-title">Đang phát</b>
        <span><button class="btn small" id="fun-mini-open">Mở lại</button>
        <button class="btn small danger" id="fun-mini-close">Tắt</button></span></div>
        <div id="fun-mini-slot"></div>`;
      document.body.appendChild(h);
      h.querySelector("#fun-mini-open").onclick = () => { S.tab = "watch"; try { show("fun"); } catch {} };
      h.querySelector("#fun-mini-close").onclick = () => { stopMini(); if (inFunView()) render(); };
    }
    return h;
  }
  function stopMini() {
    const h = document.querySelector("#fun-mini");
    if (h) { h.querySelector("#fun-mini-slot").innerHTML = ""; h.style.display = "none"; }
    S.currentId = null; S.detail = null;
  }
  function syncMini() {
    const h = miniEl();
    if (!S.currentId) { const f0 = h.querySelector("#fun-mini-slot iframe"); if (f0) f0.remove(); h.style.display = "none"; return; }
    const api = P();
    let f = h.querySelector("#fun-mini-slot iframe[data-fun-player]");
    if (!(f && f.dataset.funPlayer === String(S.currentId))) {
      if (f) f.remove();
      f = document.createElement("iframe");
      f.dataset.funPlayer = String(S.currentId);
      f.src = api.embedUrl(S.currentId, { autoplay: true, playlistId: S.queue.length > 1 ? S.relatedPlaylistId : null });
      f.setAttribute("allow", "autoplay; fullscreen; picture-in-picture; web-share");
      f.setAttribute("allowfullscreen", "");
      f.setAttribute("frameborder", "0");
      h.querySelector("#fun-mini-slot").appendChild(f);
    }
    h.querySelector("#fun-mini-title").textContent = S.detail?.title || ("Đang phát • " + SRC_LABEL());
    h.style.display = "block";
  }
  // app.js gọi trước khi thay #content (show/openMachine): tách player ra mini
  window._funDetach = function () {
    try {
      if (!S.currentId) return;
      const f = document.querySelector("#fun-body iframe[data-fun-player]");
      const h = miniEl();
      if (f) h.querySelector("#fun-mini-slot").appendChild(f);
      h.querySelector("#fun-mini-title").textContent = S.detail?.title || ("Đang phát • " + SRC_LABEL());
      if (h.querySelector("#fun-mini-slot iframe")) h.style.display = "block";
    } catch {}
  };

  // ---- render ----
  function cardHtml(v) {
    return `<button class="fun-card" data-fun-open="${escH(v.id)}" title="${escH(v.title)}">
      <div class="fun-thumb"><img loading="lazy" src="${escH(v.thumbnail_480_url || "")}" alt="">
      <span class="fun-dur">${escH(fmtDur(v.duration))}</span></div>
      <div class="fun-card-body"><p class="fun-card-title">${escH(v.title)}</p>
      <p class="fun-card-meta">${escH(v["owner.screenname"] ?? "—")} • ${escH(fmtViews(v.views_total))} lượt xem</p></div>
    </button>`;
  }

  function render() {
    const c = document.querySelector("#content");
    if (!c) return;
    try { c.classList.add("wide"); } catch {}
    const tabs = [["home", "🔥 Thịnh hành"], ["watch", "▶ Xem video"], ["channel", "📺 Kênh"], ["playlist", "📃 Playlist"]];
    const srcName = SRC_LABEL();
    const srcHint = S.source === "yt" ? "không cần key" : "không cần key";
    let h = `<h2>🎬 Giải trí <span class="muted" style="font-size:13px">— xem ${srcName} trực tuyến (${srcHint})</span></h2>
    <div class="tabs" style="margin-bottom:8px">
      <button data-funsrc="dm" class="${S.source === "dm" ? "active" : ""}">📺 Dailymotion</button>
      <button data-funsrc="yt" class="${S.source === "yt" ? "active" : ""}">▶️ YouTube</button>
    </div>
    <div class="tabs">${tabs.map(([t, l]) => `<button data-funtab="${t}" class="${S.tab === t ? "active" : ""}">${l}</button>`).join("")}</div>
    <div id="fun-body"></div>
    <p class="muted">Nguồn video: ${S.source === "yt" ? "YouTube qua API công khai Invidious + trình phát nhúng chính thức" : "Dailymotion Data API công khai + trình phát nhúng chính thức"} — chỉ xem (embed), không tải/lưu trữ.</p>`;
    c.innerHTML = h;
    c.querySelectorAll("[data-funsrc]").forEach(b => b.onclick = () => switchSource(b.dataset.funsrc));
    c.querySelectorAll("[data-funtab]").forEach(b => b.onclick = () => {
      if (S.tab === "watch" && b.dataset.funtab !== "watch") window._funDetach();
      S.tab = b.dataset.funtab;
      if (S.tab === "home" && !S.videos.length && !S.query) loadList(1, undefined);
      render();
    });
    const body = c.querySelector("#fun-body");
    if (S.tab === "home") renderHome(body);
    else if (S.tab === "watch") renderWatch(body);
    else if (S.tab === "channel") renderChannel(body);
    else if (S.tab === "playlist") renderPlaylist(body);
  }

  function renderHome(body) {
    body.innerHTML = `
      <div class="fun-search">
        <input id="fun-q" placeholder="Tìm kiếm video… (vd: bóng đá, nhạc, phim)" value="${escH(S.query)}">
        <select id="fun-sort" title="Sắp xếp">
          ${[["relevance", "Liên quan nhất"], ["recent", "Mới nhất"], ["visited", "Xem nhiều nhất"], ["trending", "Thịnh hành"]].map(([v, l]) => `<option value="${v}"${S.sort === v ? " selected" : ""}>${l}</option>`).join("")}
        </select>
        <button class="btn primary" style="width:auto" id="fun-go">Tìm</button>
        <button class="btn small" id="fun-trend">Thịnh hành</button>
      </div>
      <h3>${S.query ? `Kết quả cho “${escH(S.query)}”` : "Video thịnh hành"} ${S.total ? `<span class="muted">(${S.total} video)</span>` : ""}</h3>
      ${S.error ? `<p class="err">${escH(S.error)}</p>` : ""}
      <div class="fun-grid">${S.videos.map(cardHtml).join("") || `<p class="muted">Không có video nào.</p>`}</div>
      <div class="fun-more">${S.loading ? `<p class="muted">Đang tải…</p>` : (S.hasMore ? `<button class="btn" id="fun-more">Xem thêm</button>` : "")}</div>`;
    body.querySelector("#fun-go").onclick = () => {
      S.query = body.querySelector("#fun-q").value.trim();
      S.sort = body.querySelector("#fun-sort").value;
      S.tab = "home"; S.channel = ""; S.playlistMeta = null;
      loadList(1, S.query ? { type: "search", query: S.query } : undefined);
    };
    body.querySelector("#fun-q").addEventListener("keydown", (e) => { if (e.key === "Enter") body.querySelector("#fun-go").click(); });
    body.querySelector("#fun-sort").onchange = (e) => { S.sort = e.target.value; if (S.query) loadList(1, { type: "search", query: S.query }); };
    body.querySelector("#fun-trend").onclick = () => { S.query = ""; S.channel = ""; S.playlistMeta = null; loadList(1, undefined); };
    const mb = body.querySelector("#fun-more");
    if (mb) mb.onclick = () => loadList(S.page + 1, S.query ? { type: "search", query: S.query } : undefined, false);
    bindOpen(body);
  }

  function renderWatch(body) {
    const api = P();
    const SRC = { playlist: "Cùng playlist", related: "Liên quan", channel: "Cùng kênh", search: "Tìm theo chủ đề" };
    const q = S.queue, qi = S.queueIndex;
    const filtered = S.relatedFilter.trim()
      ? S.related.filter((v) => ((v.title ?? "") + " " + (v["owner.screenname"] ?? "")).toLowerCase().includes(S.relatedFilter.trim().toLowerCase()))
      : S.related;
    const urlPh = S.source === "yt"
      ? "Dán link YouTube (watch / youtu.be / shorts) HOẶC playlist (?list=…) là xem được ngay…"
      : "Dán link video HOẶC playlist là xem được ngay…";
    body.innerHTML = `
      <div class="fun-search">
        <input id="fun-url" placeholder="${urlPh}" value="${escH(S.urlInput)}">
        <button class="btn primary" style="width:auto" id="fun-view">Xem</button>
      </div>
      <div class="fun-search">
        <input id="fun-wq" placeholder="Tìm kiếm video ${SRC_LABEL()}… (vd: bóng đá, nhạc, phim)" value="${escH(S.wq)}">
        <button class="btn primary" style="width:auto" id="fun-wgo">Tìm kiếm</button>
      </div>
      ${S.wqError ? `<p class="err">${escH(S.wqError)}</p>` : ""}
      ${S.wqLoading ? `<p class="muted">Đang tìm…</p>`
      : S.wqSearched ? (S.wqList.length
        ? `<h3>Kết quả cho “${escH(S.wq)}”</h3><div class="fun-grid">${S.wqList.map(cardHtml).join("")}</div>
           <div class="fun-more">${S.wqHasMore ? `<button class="btn" id="fun-wmore">Xem thêm</button>` : ""}</div>`
        : `<p class="muted">Không tìm thấy video nào.</p>`) : ""}
      ${S.detailError ? `<p class="err">${escH(S.detailError)}</p>` : ""}
      ${S.queueLoading ? `<p class="muted">Đang tải playlist…</p>` : ""}
      ${q.length > 1 ? `<div class="fun-queue"><b>${escH(S.queueMeta?.name ?? ("Playlist " + (S.relatedPlaylistId ?? "")))}</b>
        <span class="muted"> • Đang phát ${qi + 1}/${q.length}${q[qi]?.title ? " — " + escH(q[qi].title) : ""}</span>
        <div class="fun-qctl">
          <button class="btn small" id="fun-prev">⏮ Trước</button>
          <button class="btn small" id="fun-next">Tiếp ⏭</button>
          <label><input type="checkbox" id="fun-auto"${S.autoNext ? " checked" : ""}> Tự phát tiếp</label>
          <label><input type="checkbox" id="fun-loop"${S.loopList ? " checked" : ""}> Lặp</label>
          <button class="btn small" id="fun-saveq">${isSaved(S.relatedPlaylistId) ? "★ Đã lưu" : "☆ Lưu playlist"}</button>
          <button class="btn small" id="fun-exitq">Thoát playlist</button>
        </div></div>` : ""}
      ${S.currentId ? `<div class="fun-player" id="fun-player-slot"><iframe data-fun-player="${escH(S.currentId)}" src="${escH(api.embedUrl(S.currentId, { autoplay: true, playlistId: q.length > 1 ? S.relatedPlaylistId : null }))}"
        allow="autoplay; fullscreen; picture-in-picture; web-share" allowfullscreen frameborder="0" title="${SRC_LABEL()} player"></iframe></div>
        ${S.detail ? `<div class="card" style="margin-top:10px"><h3 style="margin:0 0 6px">${escH(S.detail.title)}</h3>
          <p class="muted">${escH(S.detail["owner.screenname"] ?? "")} • ${escH(fmtViews(S.detail.views_total))} lượt xem • ${escH(fmtDate(S.detail.created_time))} • ${escH(fmtDur(S.detail.duration))}</p>
          <p class="muted">${escH((S.detail.description || "Không có mô tả.").slice(0, 600))}</p>
          <a href="${escH(S.detail.url || "")}" target="_blank" rel="noreferrer">Mở trên ${SRC_LABEL()} ↗</a></div>`
        : (!S.detailError ? `<p class="muted">Đang tải thông tin video…</p>` : "")}`
      : `<p class="muted">Dán link video ${SRC_LABEL()} vào ô trên rồi bấm <b>Xem</b>, hoặc bấm vào bất kỳ video nào ở tab Thịnh hành.</p>`}
      <div class="fun-watch2">
        <h3>Video liên quan ${S.relatedSource ? `<span class="badge">${escH(SRC[S.relatedSource] ?? S.relatedSource)}</span>` : ""}</h3>
        ${S.related.length ? `<div class="fun-search"><input id="fun-relf" placeholder="Lọc trong danh sách…" value="${escH(S.relatedFilter)}"></div>` : ""}
        ${S.relLoading ? `<p class="muted">Đang tải video liên quan…</p>`
        : !S.related.length ? `<p class="muted">Chưa có gợi ý. Hãy mở một video trước.</p>`
        : !filtered.length ? `<p class="muted">Không khớp bộ lọc.</p>`
        : `<div class="fun-rellist">${filtered.map((v) => `
            <button class="fun-rel${v.id === S.currentId ? " active" : ""}" data-fun-open="${escH(v.id)}">
              <img src="${escH(v.thumbnail_480_url || "")}" alt="">
              <div><p>${q.length > 1 ? `<b class="fun-qnum">${q.findIndex((x) => x.id === v.id) + 1}. </b>` : ""}${v.id === S.currentId ? `<b>Đang xem • </b>` : ""}${escH(v.title)}</p>
              <span>${escH(v["owner.screenname"] ?? "")} • ${escH(fmtViews(v.views_total))} • ${escH(fmtDur(v.duration))}</span></div>
            </button>`).join("")}</div>`}
      </div>`;
    body.querySelector("#fun-view").onclick = async () => {
      S.urlInput = body.querySelector("#fun-url").value;
      const { videoId: vid, playlistId: pid } = api.parseVideoAndPlaylist(S.urlInput);
      if (vid && pid && vid !== pid) { S.playlistInput = pid; await playPlaylist(pid, vid); return; }
      if (vid && !pid) { openVideo(vid); return; }
      if (pid && !vid) { await playPlaylist(pid); return; }
      if (vid && pid && vid === pid) {
        try { await api.videoDetail(vid); openVideo(vid); } catch { await playPlaylist(pid); }
        return;
      }
      S.detailError = `Không nhận diện được link ${SRC_LABEL()}. Hãy dán link video hoặc playlist.`;
      render();
    };
    body.querySelector("#fun-url").addEventListener("keydown", (e) => { if (e.key === "Enter") body.querySelector("#fun-view").click(); });
    // Đang phát ở mini (đi tab khác về): gắn iframe cũ vào lại, không reload
    try {
      const slot = body.querySelector("#fun-player-slot");
      const stashed = document.querySelector("#fun-mini-slot iframe[data-fun-player]");
      if (slot && S.currentId) {
        if (stashed && stashed.dataset.funPlayer === String(S.currentId)) {
          slot.innerHTML = ""; slot.appendChild(stashed);
          const mh = document.querySelector("#fun-mini"); if (mh) mh.style.display = "none";
        } else if (stashed) { stashed.remove(); }
      }
    } catch {}
    body.querySelector("#fun-wgo").onclick = () => {
      S.wq = body.querySelector("#fun-wq").value.trim();
      if (!S.wq) return;
      doWatchSearch(1, true);
    };
    body.querySelector("#fun-wq").addEventListener("keydown", (e) => { if (e.key === "Enter") body.querySelector("#fun-wgo").click(); });
    const wm = body.querySelector("#fun-wmore");
    if (wm) wm.onclick = () => doWatchSearch(S.wqPage + 1, false);
    const pv = body.querySelector("#fun-prev"), nx = body.querySelector("#fun-next");
    if (pv) pv.onclick = playPrev;
    if (nx) nx.onclick = playNext;
    const au = body.querySelector("#fun-auto"), lp = body.querySelector("#fun-loop");
    if (au) au.onchange = (e) => { S.autoNext = e.target.checked; };
    if (lp) lp.onchange = (e) => { S.loopList = e.target.checked; };
    const sq = body.querySelector("#fun-saveq");
    if (sq) sq.onclick = () => toggleSave(S.queueMeta ?? { id: S.relatedPlaylistId });
    const eq = body.querySelector("#fun-exitq");
    if (eq) eq.onclick = () => { S.queue = []; S.queueIndex = -1; S.queueMeta = null; S.relatedPlaylistId = null; render(); };
    const rf = body.querySelector("#fun-relf");
    if (rf) rf.oninput = (e) => {
      S.relatedFilter = e.target.value;
      // render lại list mà không mất focus: cập nhật thủ công
      const pos = e.target.selectionStart;
      render();
      const nrf = document.querySelector("#fun-relf");
      if (nrf) { nrf.focus(); try { nrf.setSelectionRange(pos, pos); } catch {} }
    };
    bindOpen(body);
  }

  function renderChannel(body) {
    const api = P();
    const chPh = S.source === "yt"
      ? "Nhập channel ID / @handle / URL kênh (vd: UC… hoặc @tenkenh)"
      : "Nhập tên kênh hoặc URL kênh (vd: LEQUIPE)";
    const chEx = S.source === "yt" ? "UC_x5XG1OV2P6uZZ5FSM9Ttw hoặc @tenkenh" : "LEQUIPE";
    body.innerHTML = `
      <div class="fun-search">
        <input id="fun-ch" placeholder="${chPh}" value="${escH(S.channelInput)}">
        <button class="btn primary" style="width:auto" id="fun-chgo">Tải kênh</button>
      </div>
      ${S.channel ? `<p class="muted">Đang xem kênh: <b>${escH(S.channel)}</b></p>` : ""}
      ${S.error ? `<p class="err">${escH(S.error)}</p>` : ""}
      ${S.channel ? `<div class="fun-grid">${S.videos.map(cardHtml).join("")}</div>
      <div class="fun-more">${S.loading ? `<p class="muted">Đang tải…</p>` : (S.hasMore ? `<button class="btn" id="fun-more">Xem thêm</button>` : "")}</div>` : ""}`;
    body.querySelector("#fun-chgo").onclick = () => {
      S.channelInput = body.querySelector("#fun-ch").value;
      const owner = api.parseOwner(S.channelInput);
      if (!owner) { S.error = `Tên kênh/URL chưa đúng. Ví dụ: ${chEx}`; render(); return; }
      S.channel = owner; S.tab = "channel";
      loadList(1, { type: "channel", owner });
    };
    body.querySelector("#fun-ch").addEventListener("keydown", (e) => { if (e.key === "Enter") body.querySelector("#fun-chgo").click(); });
    const mb = body.querySelector("#fun-more");
    if (mb) mb.onclick = () => loadList(S.page + 1, { type: "channel", owner: S.channel }, false);
    bindOpen(body);
  }

  function renderPlaylist(body) {
    const api = P();
    const plPh = S.source === "yt"
      ? "Nhập playlist id hoặc URL (vd: PL… hoặc link ?list=…)"
      : "Nhập playlist id hoặc URL (vd: x85ce2)";
    body.innerHTML = `
      <div class="fun-search">
        <input id="fun-pl" placeholder="${plPh}" value="${escH(S.playlistInput)}">
        <button class="btn primary" style="width:auto" id="fun-plgo">Tải playlist</button>
      </div>
      ${S.playlistMeta ? `<div class="card"><h3 style="margin:0 0 4px">${escH(S.playlistMeta.name)}</h3>
        <p class="muted">${escH(S.playlistMeta["owner.screenname"] ?? "")} • ${S.playlistMeta.videos_total ?? S.videos.length} video</p>
        ${S.playlistMeta.description ? `<p class="muted">${escH(S.playlistMeta.description.slice(0, 400))}</p>` : ""}
        <div class="fun-qctl">
          <button class="btn small ok" id="fun-playall">▶ Phát toàn bộ</button>
          <button class="btn small" id="fun-savepl">${isSaved(S.playlistMeta.id) ? "★ Đã lưu" : "☆ Lưu xem sau"}</button>
        </div></div>
        ${S.error ? `<p class="err">${escH(S.error)}</p>` : ""}
        <div class="fun-grid">${S.videos.map(cardHtml).join("")}</div>
        <div class="fun-more">${S.loading ? `<p class="muted">Đang tải…</p>` : (S.hasMore ? `<button class="btn" id="fun-more">Xem thêm</button>` : "")}</div>`
      : `<h3>Playlist đã lưu <span class="muted">(${S.saved.length})</span></h3>
        ${S.saved.length ? `<div class="fun-rellist">${S.saved.map((s) => `
          <div class="fun-rel"><img src="${escH(s.thumbnail || "")}" alt="">
            <div style="flex:1"><p>${escH(s.name)}</p>
            <span>${escH(s.owner ?? "")} ${s.videos_total != null ? "• " + s.videos_total + " video" : ""} • ${escH(s.id)}</span>
            <div class="fun-qctl">
              <button class="btn small ok" data-fun-play="${escH(s.id)}">▶ Phát</button>
              <button class="btn small" data-fun-openpl="${escH(s.id)}">Mở danh sách</button>
              <button class="btn small danger" data-fun-unsave="${escH(s.id)}">Bỏ lưu</button>
            </div></div></div>`).join("")}</div>`
        : `<p class="muted">Dán link/ID playlist rồi bấm <b>Tải playlist</b> (hoặc <b>☆ Lưu xem sau</b>) để lưu lại xem dần.</p>`}
        ${S.error ? `<p class="err">${escH(S.error)}</p>` : ""}`}`;
    body.querySelector("#fun-plgo").onclick = async () => {
      S.playlistInput = body.querySelector("#fun-pl").value;
      const id = api.parsePlaylistId(S.playlistInput) ?? S.playlistInput.trim();
      if (!id) return;
      S.tab = "playlist"; S.loading = true; S.error = ""; render();
      const box = document.querySelector("#fun-body");
      try {
        const meta = await api.playlistInfo(id).catch(() => null);
        S.playlistMeta = meta ?? { id, name: `Playlist ${id}` };
        S.playlistInput = id;
        const data = await api.playlistVideos(id, { page: 1, limit: PAGE });
        S.videos = data.list ?? []; S.hasMore = Boolean(data.has_more); S.page = 1;
      } catch (e) { S.error = e.message || "Không tải được playlist."; }
      finally { S.loading = false; render(); }
      void box;
    };
    body.querySelector("#fun-pl").addEventListener("keydown", (e) => { if (e.key === "Enter") body.querySelector("#fun-plgo").click(); });
    const pa = body.querySelector("#fun-playall");
    if (pa) pa.onclick = () => playPlaylist(S.playlistMeta.id ?? S.playlistInput);
    const sp = body.querySelector("#fun-savepl");
    if (sp) sp.onclick = () => toggleSave(S.playlistMeta);
    const mb = body.querySelector("#fun-more");
    if (mb) mb.onclick = () => loadList(S.page + 1, { type: "playlist", id: S.playlistMeta.id }, false);
    body.querySelectorAll("[data-fun-play]").forEach(b => b.onclick = () => playPlaylist(b.dataset.funPlay));
    body.querySelectorAll("[data-fun-openpl]").forEach(b => b.onclick = () => {
      S.playlistInput = b.dataset.funOpenpl; S.playlistMeta = null;
      render(); document.querySelector("#fun-plgo")?.click();
    });
    body.querySelectorAll("[data-fun-unsave]").forEach(b => b.onclick = () => toggleSave({ id: b.dataset.funUnsave }));
    // bấm video trong playlist → phát theo hàng đợi
    body.querySelectorAll("[data-fun-open]").forEach(b => b.onclick = () => {
      if (S.playlistMeta) playPlaylist(S.playlistMeta.id ?? S.playlistInput, api.parseVideoId(b.dataset.funOpen) || b.dataset.funOpen);
      else openVideo(b.dataset.funOpen);
    });
  }

  function bindOpen(root) {
    const api = P();
    // Gắn handler mở video cho các card chưa được gắn riêng (home/channel/watch-related)
    root.querySelectorAll("[data-fun-open]").forEach((b) => {
      if (b.onclick) return;
      b.onclick = () => {
        const id = b.dataset.funOpen;
        if (S.tab === "playlist" && S.playlistMeta) {
          playPlaylist(S.playlistMeta.id ?? S.playlistInput, api.parseVideoId(id) || id);
        } else if (S.queue.length > 1) {
          const ix = S.queue.findIndex((x) => x.id === id);
          if (ix >= 0) { playAt(ix); return; }
          openVideo(id, { playlistId: S.relatedSource === "playlist" ? S.relatedPlaylistId : null });
        } else {
          openVideo(id, { playlistId: S.relatedSource === "playlist" ? S.relatedPlaylistId : null });
        }
      };
    });
  }

  // Entry cho app.js: show("fun") → viewFun(contentEl)
  window.viewFun = async function (c) {
    render();
    if (!S.videos.length && S.tab === "home") loadList(1, undefined);
  };
  // expose để debug / dùng từ console
  window._funOpen = openVideo;
  window._funPlayPlaylist = playPlaylist;
})();
