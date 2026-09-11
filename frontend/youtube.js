// YouTube helpers — cùng cấu trúc / API surface với frontend/dailymotion.js (window.DM).
// Không cần API key: dùng Invidious API công khai (nhiều instance fallback) + player nhúng youtube-nocookie.
// Chuẩn hoá dữ liệu về đúng shape DM đang dùng để entertainment.js tái sử dụng nguyên logic:
//   video: { id, title, description, thumbnail_480_url, duration, views_total, created_time,
//            "owner.screenname", "owner.id", url, embed_url, tags }
//   list:  { list, has_more, total }
(function () {
  const INSTANCES = [
    "https://inv.nadeko.net",
    "https://invidious.nerdvpn.de",
    "https://inv.tux.pizza",
    "https://iv.duti.dev",
    "https://invidious.jing.rocks",
  ];

  async function fetchJson(url) {
    const res = await fetch(url, { headers: { Accept: "application/json" } });
    if (!res.ok) throw new Error("Lỗi HTTP " + res.status);
    return res.json();
  }

  // Backend cùng origin (backend/app/api/youtube.py) — scrape YouTube, không cần key.
  // Ưu tiên đường này (tránh CORS/chặn), lỗi mới rơi xuống Invidious.
  function authHeaders() {
    try {
      const t = localStorage.getItem("lsm_token");
      return t ? { Authorization: "Bearer " + t } : {};
    } catch { return {}; }
  }

  async function backendGet(path) {
    const res = await fetch(path, { headers: { Accept: "application/json", ...authHeaders() } });
    const body = await res.json().catch(() => null);
    if (!res.ok || !body || body.success === false) {
      throw new Error((body && body.message) || ("Lỗi HTTP " + res.status));
    }
    return body.data;
  }

  // Thử lần lượt các instance cho tới khi thành công
  async function invGet(path) {
    let lastErr = null;
    for (const base of INSTANCES) {
      try {
        return await fetchJson(base + path);
      } catch (e) { lastErr = e; }
    }
    throw lastErr || new Error("Không kết nối được YouTube (các API phụ đều lỗi).");
  }

  const thumbOf = (id) => (id ? `https://i.ytimg.com/vi/${id}/hqdefault.jpg` : "");
  const watchUrl = (id) => (id ? `https://www.youtube.com/watch?v=${id}` : "");

  function num(v) {
    const n = Number(v);
    return Number.isFinite(n) && n >= 0 ? n : null;
  }

  // Chuẩn hoá 1 item invidious (search/trending/channel/playlist/detail/recommended) -> shape DM
  function normVideo(v) {
    if (!v || typeof v !== "object") return null;
    const id = v.videoId ?? v.video_id ?? v.id ?? null;
    if (id == null) return null;
    const vid = String(id);
    if (!vid || vid.length > 32) return null;
    const author = v.author ?? v.authorName ?? v.author_name ?? "";
    const authorId = v.authorId ?? v.author_id ?? v.authorid ?? null;
    const views = num(v.viewCount ?? v.view_count ?? v.views) ?? null;
    const dur = num(v.lengthSeconds ?? v.length_seconds ?? v.duration ?? v.length) ?? null;
    const thumbs = Array.isArray(v.videoThumbnails) ? v.videoThumbnails : [];
    let thumb = thumbOf(vid);
    // Ưu tiên thumbnail chất lượng cao từ API nếu có
    const hq = thumbs.find((t) => /maxres|high|medium/i.test(t?.quality ?? "")) || thumbs[thumbs.length - 1];
    if (hq?.url) thumb = String(hq.url).startsWith("http") ? hq.url : thumb;
    return {
      id: vid,
      title: v.title ?? "(Không tiêu đề)",
      description: v.description ?? v.descriptionHtml ?? "",
      thumbnail_480_url: thumb,
      thumbnail_720_url: thumb,
      duration: dur,
      views_total: views,
      likes_total: num(v.likeCount ?? v.like_count) ?? null,
      created_time: num(v.published ?? v.publishedAt) ?? null, // unix seconds (nếu có)
      "owner.id": authorId ? String(authorId) : null,
      "owner.screenname": author ? String(author) : "—",
      embed_url: `https://www.youtube.com/embed/${vid}`,
      url: watchUrl(vid),
      channel: authorId ? String(authorId) : null,
      tags: Array.isArray(v.keywords) ? v.keywords : (Array.isArray(v.keyWords) ? v.keyWords : []),
      _raw: v,
    };
  }

  const normList = (arr) => (Array.isArray(arr) ? arr.map(normVideo).filter(Boolean) : []);

  // ---- parsers (giống DM) ----
  const VID_RE = /^[A-Za-z0-9_-]{11}$/;

  function parseVideoId(input) {
    if (!input) return null;
    const s = String(input).trim();
    if (VID_RE.test(s)) return s;
    let m = s.match(/[?&]v=([A-Za-z0-9_-]{11})/i)
      || s.match(/youtu\.be\/([A-Za-z0-9_-]{11})/i)
      || s.match(/youtube\.com\/(?:embed|shorts|live|v)\/([A-Za-z0-9_-]{11})/i)
      || s.match(/\/video\/([A-Za-z0-9_-]{11})/i);
    if (m) return m[1];
    // bare id lẫn trong chuỗi dài
    m = s.match(/([A-Za-z0-9_-]{11})/);
    if (m && /youtube|youtu\.be/i.test(s)) return m[1];
    return null;
  }

  function parsePlaylistId(input) {
    if (!input) return null;
    const s = String(input).trim();
    const m = s.match(/[?&]list=([A-Za-z0-9_-]+)/i) || s.match(/playlist\/([A-Za-z0-9_-]+)/i);
    if (m) return m[1];
    if (/^(PL|UU|LL|FL|RD)[A-Za-z0-9_-]{10,}$/i.test(s) && !s.includes("/") && !s.includes(" ")) return s;
    return null;
  }

  function parseOwner(input) {
    if (!input) return null;
    const s = String(input).trim();
    let m = s.match(/youtube\.com\/channel\/([A-Za-z0-9_-]+)/i)
      || s.match(/youtube\.com\/(?:c|user)\/([A-Za-z0-9_.-]+)/i)
      || s.match(/youtube\.com\/@([A-Za-z0-9_.-]+)/i);
    if (m) return m[1];
    if (/^UC[A-Za-z0-9_-]{20,}$/.test(s)) return s; // channel id chuẩn
    if (/^@[A-Za-z0-9_.-]+$/.test(s)) return s.slice(1);
    if (/^[A-Za-z0-9_.-]+$/.test(s) && !s.includes("/") && !s.includes(" ") && s.length <= 60) return s;
    return null;
  }

  function parseVideoAndPlaylist(input) {
    if (!input) return { videoId: null, playlistId: null };
    const s = String(input).trim();
    const videoId = parseVideoId(s);
    const playlistId = parsePlaylistId(s);
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

  // ---- player ----
  function embedUrl(videoId, autoplayOrOpts = true, playlistIdArg = null) {
    let autoplay = true, playlistId = playlistIdArg;
    if (typeof autoplayOrOpts === "object" && autoplayOrOpts !== null) {
      autoplay = autoplayOrOpts.autoplay ?? true;
      playlistId = autoplayOrOpts.playlistId ?? null;
    } else autoplay = autoplayOrOpts ?? true;
    let url = `https://www.youtube-nocookie.com/embed/${videoId}?rel=0&enablejsapi=1${autoplay ? "&autoplay=1" : ""}`;
    if (playlistId) url += `&list=${encodeURIComponent(playlistId)}`;
    return url;
  }

  // YouTube IFrame API postMessage: {event:"onStateChange",info:0|1|2...} (0 = ended)
  // + tương thích message kiểu DM {event:"end"|...}
  function parsePlayerEvent(data) {
    let d = data;
    if (typeof d === "string") { try { d = JSON.parse(d); } catch { return { event: "", time: null, duration: null }; } }
    if (!d || typeof d !== "object") return { event: "", time: null, duration: null };
    const ev = String(d.event ?? d.type ?? "");
    if (ev === "onStateChange") {
      const info = Number(d.info ?? d.data);
      if (info === 0) return { event: "end", time: null, duration: null };
      return { event: "state" + info, time: null, duration: null };
    }
    if (ev === "infoDelivery" && d.info) {
      const t = num(d.info.currentTime), dur = num(d.info.duration);
      return { event: "info", time: t, duration: dur };
    }
    const numf = (v) => { const n = Number(v); return Number.isFinite(n) && n >= 0 ? n : null; };
    return { event: ev, time: numf(d.time ?? d.currentTime), duration: numf(d.duration) };
  }

  // ---- API ----
  const SORT_MAP = { relevance: "relevance", recent: "upload_date", visited: "view_count", trending: "view_count" };
  const CH_SORT_MAP = { relevance: "newest", recent: "newest", visited: "popular", trending: "popular" };

  async function searchVideos({ query, page = 1, limit = 12, sort = "relevance" } = {}) {
    try {
      return await backendGet(`/api/youtube/search?q=${encodeURIComponent(query || "")}&page=${page}&limit=${limit}&sort=${encodeURIComponent(sort)}`);
    } catch {}
    const sortBy = SORT_MAP[sort] ?? "relevance";
    const data = await invGet(`/api/v1/search?q=${encodeURIComponent(query || "")}&page=${page}&type=video&sort_by=${sortBy}`);
    const arr = Array.isArray(data) ? data : [];
    const videos = normList(arr.filter((x) => !x.type || x.type === "video"));
    return { list: videos.slice(0, limit), has_more: videos.length >= limit, total: videos.length };
  }

  async function trendingVideos({ page = 1, limit = 12 } = {}) {
    try {
      return await backendGet(`/api/youtube/trending?page=${page}&limit=${limit}`);
    } catch {}
    const data = await invGet(`/api/v1/trending?type=Default`);
    const videos = normList(Array.isArray(data) ? data : []);
    const start = (page - 1) * limit;
    const slice = videos.slice(start, start + limit);
    return { list: slice, has_more: start + limit < videos.length, total: videos.length };
  }

  async function videoDetail(id) {
    try {
      return await backendGet(`/api/youtube/videos/${encodeURIComponent(id)}`);
    } catch {}
    try {
      const v = await invGet(`/api/v1/videos/${encodeURIComponent(id)}`);
      const n = normVideo({ ...v, videoId: v.videoId ?? id });
      if (n) {
        // Gắn recommended để relatedVideos tái dùng khi có thể
        n._recommended = normList(v.recommendedVideos ?? v.recommendedvideos ?? []);
        return n;
      }
      throw new Error("Không đọc được video.");
    } catch (e) {
      // Fallback cuối: oEmbed (chỉ có title/author) để vẫn mở được player khi paste link
      try {
        const o = await fetchJson(`https://www.youtube.com/oembed?url=${encodeURIComponent(watchUrl(id))}&format=json`);
        return {
          id, title: o.title ?? id, description: "",
          thumbnail_480_url: thumbOf(id), thumbnail_720_url: thumbOf(id),
          duration: null, views_total: null, likes_total: null, created_time: null,
          "owner.id": null, "owner.screenname": o.author_name ?? "—",
          embed_url: `https://www.youtube.com/embed/${id}`, url: watchUrl(id),
          channel: null, tags: [], _recommended: [],
        };
      } catch { throw e; }
    }
  }

  async function relatedVideos(id, { limit = 12 } = {}) {
    try {
      return await backendGet(`/api/youtube/videos/${encodeURIComponent(id)}/related?limit=${limit}`);
    } catch {}
    const v = await invGet(`/api/v1/videos/${encodeURIComponent(id)}`);
    const list = normList(v.recommendedVideos ?? v.recommendedvideos ?? []).filter((x) => x.id !== id);
    return { list: list.slice(0, limit), has_more: false, total: list.length };
  }

  // Resolve @handle / tên custom -> channelId qua search type=channel
  async function resolveChannel(input) {
    const s = String(input).trim();
    if (/^UC[A-Za-z0-9_-]{20,}$/.test(s)) return s;
    const q = s.replace(/^@/, "");
    const data = await invGet(`/api/v1/search?q=${encodeURIComponent(q)}&type=channel`);
    const arr = Array.isArray(data) ? data : [];
    const ch = arr.find((x) => x.authorId) ?? arr[0];
    const cid = ch?.authorId ?? ch?.author_id ?? null;
    if (!cid) throw new Error("Không tìm thấy kênh.");
    return String(cid);
  }

  async function userVideos(owner, { page = 1, limit = 12, sort = "recent" } = {}) {
    try {
      return await backendGet(`/api/youtube/channels/${encodeURIComponent(owner)}/videos?page=${page}&limit=${limit}&sort=${encodeURIComponent(sort)}`);
    } catch {}
    const cid = await resolveChannel(owner);
    const sortBy = CH_SORT_MAP[sort] ?? "newest";
    const data = await invGet(`/api/v1/channels/${encodeURIComponent(cid)}/videos?page=${page}&sort_by=${sortBy}`);
    const videos = normList(Array.isArray(data) ? data : []);
    return { list: videos.slice(0, limit), has_more: videos.length >= limit, total: videos.length, _channelId: cid };
  }

  async function playlistInfo(id) {
    try {
      return await backendGet(`/api/youtube/playlists/${encodeURIComponent(id)}`);
    } catch {}
    const p = await invGet(`/api/v1/playlists/${encodeURIComponent(id)}`);
    const first = Array.isArray(p.videos) && p.videos[0] ? p.videos[0] : null;
    const fid = first?.videoId ?? first?.video_id ?? null;
    return {
      id, name: p.title ?? `Playlist ${id}`,
      description: p.description ?? "",
      thumbnail_480_url: fid ? thumbOf(String(fid)) : "",
      videos_total: p.videoCount ?? (Array.isArray(p.videos) ? p.videos.length : null),
      "owner.screenname": p.author ?? "",
      owner: p.author ?? "",
    };
  }

  async function playlistVideos(id, { page = 1, limit = 12 } = {}) {
    try {
      return await backendGet(`/api/youtube/playlists/${encodeURIComponent(id)}/videos?page=${page}&limit=${limit}`);
    } catch {}
    const p = await invGet(`/api/v1/playlists/${encodeURIComponent(id)}`);
    const videos = normList(Array.isArray(p.videos) ? p.videos : []);
    const start = (page - 1) * limit;
    const slice = videos.slice(start, start + limit);
    return { list: slice, has_more: start + limit < videos.length, total: videos.length };
  }

  async function fetchAllPlaylistVideos(id, { maxTotal = 100 } = {}) {
    // Qua backend: lật từng trang cho tới đủ
    try {
      const all = [];
      let page = 1;
      for (;;) {
        const data = await backendGet(`/api/youtube/playlists/${encodeURIComponent(id)}/videos?page=${page}&limit=30`);
        const list = data?.list ?? [];
        all.push(...list);
        if (!data?.has_more || !list.length || all.length >= maxTotal) break;
        page += 1;
        if (page > 10) break;
      }
      if (all.length) return all.slice(0, maxTotal);
    } catch {}
    const p = await invGet(`/api/v1/playlists/${encodeURIComponent(id)}`);
    return normList(Array.isArray(p.videos) ? p.videos : []).slice(0, maxTotal);
  }

  // ---- format (giống DM) ----
  function formatDuration(sec) {
    if (sec == null) return "";
    sec = Math.floor(Number(sec));
    if (!Number.isFinite(sec)) return "";
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
    // Invidious trả unix seconds; nếu là ms thì quy đổi
    const t = Number(ts) > 1e12 ? Math.floor(Number(ts) / 1000) : Number(ts);
    return new Date(t * 1000).toLocaleDateString("vi-VN");
  }

  // Playlist đã lưu (localStorage) — key riêng, không lẫn với DM
  const SAVED_KEY = "ytxem.savedPlaylists.v1";
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

  window.YT = {
    searchVideos, trendingVideos, videoDetail, relatedVideos, userVideos,
    playlistInfo, playlistVideos, fetchAllPlaylistVideos,
    parseVideoId, parsePlaylistId, parseOwner, parseVideoAndPlaylist,
    embedUrl, parsePlayerEvent, formatDuration, formatViews, formatDate,
    loadSaved, persistSaved, upsertSaved, removeSaved, toSavedPlaylist,
  };
})();
