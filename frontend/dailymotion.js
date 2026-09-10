// Dailymotion public API helpers (vanilla port từ app React xem_daylymotion/src/lib/dailymotion.js)
// Không cần API key: dùng endpoint công khai api.dailymotion.com + player nhúng geo.dailymotion.com
(function () {
  const API_BASE = "https://api.dailymotion.com";
  const VIDEO_FIELDS = [
    "id", "title", "description", "thumbnail_480_url", "thumbnail_720_url",
    "duration", "views_total", "likes_total", "created_time",
    "owner.id", "owner.screenname", "owner.avatar_80_url",
    "embed_url", "url", "channel", "tags",
  ].join(",");

  async function fetchJson(url) {
    const res = await fetch(url);
    if (!res.ok) {
      let msg = "Lỗi HTTP " + res.status;
      try { const d = await res.json(); if (d?.error?.message) msg = d.error.message; } catch {}
      throw new Error(msg);
    }
    return res.json();
  }

  function parseVideoId(input) {
    if (!input) return null;
    const s = String(input).trim();
    if (/^[A-Za-z0-9]{6,}$/.test(s) && !s.includes("/") && !s.includes(" ")) return s;
    const m = s.match(/dailymotion\.com\/(?:video|embed\/video)\/([A-Za-z0-9]+)/i)
      || s.match(/dai\.ly\/([A-Za-z0-9]+)/i)
      || s.match(/[?&]video=([A-Za-z0-9]+)/i)
      || s.match(/\/video\/([A-Za-z0-9]+)/i);
    return m ? m[1] : null;
  }

  function parsePlaylistId(input) {
    if (!input) return null;
    const s = String(input).trim();
    if (/^x[a-z0-9]+$/i.test(s) && !s.includes("/")) return s;
    const m = s.match(/playlist\/([A-Za-z0-9]+)/i) || s.match(/[?&]playlist=([A-Za-z0-9]+)/i);
    return m ? m[1] : null;
  }

  function parseOwner(input) {
    if (!input) return null;
    const s = String(input).trim();
    if (/^[A-Za-z0-9_.-]+$/.test(s) && !s.includes("/")) return s;
    const m = s.match(/dailymotion\.com\/([^/?#]+)/i);
    if (m && !["video", "playlist", "embed", "search"].includes(m[1].toLowerCase())) return m[1];
    return null;
  }

  function parseVideoAndPlaylist(input) {
    if (!input) return { videoId: null, playlistId: null };
    const s = String(input).trim();
    const videoId = parseVideoId(s);
    const playlistId = parsePlaylistId(s);
    if (videoId && playlistId && videoId === playlistId) {
      const parts = s.split(/[\s,;|]+/).filter(Boolean);
      if (parts.length > 1) return { videoId: parseVideoId(parts[0]), playlistId: parsePlaylistId(parts[1]) };
    }
    if (!videoId || !playlistId) {
      const parts = s.split(/[\s,;|]+/).filter(Boolean);
      if (parts.length > 1) {
        const v = parseVideoId(parts[0]);
        let p = null;
        for (const part of parts.slice(1)) { p = parsePlaylistId(part); if (p) break; }
        if (v || p) return { videoId: v, playlistId: p };
      }
    }
    return { videoId, playlistId };
  }

  function embedUrl(videoId, autoplayOrOpts = true, playlistIdArg = null) {
    let autoplay = true, playlistId = playlistIdArg, controls = true;
    if (typeof autoplayOrOpts === "object" && autoplayOrOpts !== null) {
      autoplay = autoplayOrOpts.autoplay ?? true;
      playlistId = autoplayOrOpts.playlistId ?? null;
      controls = autoplayOrOpts.controls ?? true;
    } else autoplay = autoplayOrOpts ?? true;
    let url = `https://geo.dailymotion.com/player.html?video=${videoId}${autoplay ? "&autoplay=1" : ""}`;
    if (playlistId) url += `&playlist=${playlistId}`;
    if (controls === false) url += `&controls=false`;
    return url;
  }

  function parsePlayerEvent(data) {
    let d = data;
    if (typeof d === "string") { try { d = JSON.parse(d); } catch { return { event: "", time: null, duration: null }; } }
    if (!d || typeof d !== "object") return { event: "", time: null, duration: null };
    const event = String(d.event ?? d.type ?? "");
    const num = (v) => { const n = Number(v); return Number.isFinite(n) && n >= 0 ? n : null; };
    return { event, time: num(d.time ?? d.videoTime ?? d.currentTime ?? d.position ?? d.video_time), duration: num(d.duration ?? d.videoDuration ?? d.totalTime ?? d.video_duration) };
  }

  async function searchVideos({ query, page = 1, limit = 12, sort = "relevance" }) {
    const params = new URLSearchParams({ fields: VIDEO_FIELDS, limit: String(limit), page: String(page), sort, private: "false", password_protected: "false", family_filter: "false" });
    if (query) params.set("search", query);
    return fetchJson(`${API_BASE}/videos?${params}`);
  }
  const trendingVideos = ({ page = 1, limit = 12 } = {}) => searchVideos({ page, limit, sort: "trending" });
  const videoDetail = (id) => fetchJson(`${API_BASE}/video/${id}?fields=${encodeURIComponent(VIDEO_FIELDS)}`);
  const relatedVideos = (id, { page = 1, limit = 8 } = {}) =>
    fetchJson(`${API_BASE}/video/${id}/related?fields=${encodeURIComponent(VIDEO_FIELDS)}&limit=${limit}&page=${page}`);
  const userVideos = (owner, { page = 1, limit = 12, sort = "recent" } = {}) =>
    fetchJson(`${API_BASE}/user/${encodeURIComponent(owner)}/videos?fields=${encodeURIComponent(VIDEO_FIELDS)}&limit=${limit}&page=${page}&sort=${sort}`);
  const playlistInfo = (id) =>
    fetchJson(`${API_BASE}/playlist/${id}?fields=id,name,description,thumbnail_480_url,videos_total,owner.screenname,owner.username`);
  const playlistVideos = (id, { page = 1, limit = 12 } = {}) =>
    fetchJson(`${API_BASE}/playlist/${id}/videos?fields=${encodeURIComponent(VIDEO_FIELDS)}&limit=${limit}&page=${page}`);

  async function fetchAllPlaylistVideos(id, { limitPerPage = 30, maxTotal = 100 } = {}) {
    const all = [];
    let page = 1;
    for (;;) {
      const data = await playlistVideos(id, { page, limit: limitPerPage });
      const list = data?.list ?? [];
      all.push(...list);
      if (!data?.has_more || !list.length || all.length >= maxTotal) break;
      page += 1;
      if (page > 10) break;
    }
    return all.slice(0, maxTotal);
  }

  function formatDuration(sec) {
    if (sec == null) return "";
    sec = Math.floor(Number(sec));
    const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60;
    if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
    return `${m}:${String(s).padStart(2, "0")}`;
  }
  function formatViews(n) {
    if (n == null) return "—";
    if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)} Tr`;
    if (n >= 1_000) return `${(n / 1_000).toFixed(1)} N`;
    return String(n);
  }
  function formatDate(ts) {
    if (!ts) return "";
    return new Date(ts * 1000).toLocaleDateString("vi-VN");
  }

  // Playlist đã lưu (localStorage)
  const SAVED_KEY = "dmxem.savedPlaylists.v1";
  const MAX_SAVED = 50;
  function toSavedPlaylist(input) {
    if (!input) return null;
    const id = input.id ?? input.playlistId ?? null;
    if (!id) return null;
    return { id: String(id), name: input.name ?? `Playlist ${id}`, thumbnail: input.thumbnail_480_url ?? input.thumbnail ?? null, owner: input["owner.screenname"] ?? input.owner ?? null, videos_total: input.videos_total ?? null, savedAt: Date.now() };
  }
  function loadSaved() {
    try { const raw = localStorage.getItem(SAVED_KEY); if (!raw) return []; const a = JSON.parse(raw); return Array.isArray(a) ? a.filter(x => x?.id) : []; }
    catch { return []; }
  }
  function persistSaved(list) { try { localStorage.setItem(SAVED_KEY, JSON.stringify(list ?? [])); } catch {} }
  function upsertSaved(list, meta) {
    const rec = toSavedPlaylist(meta);
    if (!rec) return list ?? [];
    return [rec, ...(list ?? []).filter(x => String(x?.id) !== rec.id)].slice(0, MAX_SAVED);
  }
  const removeSaved = (list, id) => (list ?? []).filter(x => String(x?.id) !== String(id));

  window.DM = {
    searchVideos, trendingVideos, videoDetail, relatedVideos, userVideos,
    playlistInfo, playlistVideos, fetchAllPlaylistVideos,
    parseVideoId, parsePlaylistId, parseOwner, parseVideoAndPlaylist,
    embedUrl, parsePlayerEvent, formatDuration, formatViews, formatDate,
    loadSaved, persistSaved, upsertSaved, removeSaved, toSavedPlaylist,
  };
})();
