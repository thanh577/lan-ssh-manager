"""Proxy YouTube không cần API key (dùng chung cấu trúc dữ liệu như Dailymotion).

Scrape trực tiếp trang YouTube (search / trending / watch / channel / playlist)
rồi chuẩn hoá về đúng shape mà frontend/entertainment.js đang dùng:
  video: { id, title, description, thumbnail_480_url, duration, views_total,
           created_time, "owner.screenname", "owner.id", url, embed_url, tags }
  list:  { list, has_more, total }
"""
import json
import re
import time
import urllib.parse
import urllib.request
from html import unescape

from fastapi import APIRouter, Depends

from ..models.user import User
from .deps import ok, current_user

router = APIRouter(prefix="/api/youtube", tags=["youtube"])

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
TTL = 180
_CACHE: dict = {}


def _cache_get(key):
    it = _CACHE.get(key)
    if it and time.time() - it[0] < TTL:
        return it[1]
    return None


def _cache_set(key, val):
    if len(_CACHE) > 300:
        _CACHE.clear()
    _CACHE[key] = (time.time(), val)


def yt_get(url: str) -> str:
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
        "Accept": "text/html,application/xhtml+xml",
        "Cookie": "CONSENT=YES+cb.20210328-17-p0.vi+FX+123; SOCS=CAESEwgDEgk0ODE3Nzk3MjQaAmVuIAEaBgiA_LyaBg;",
    })
    with urllib.request.urlopen(req, timeout=20) as r:
        raw = r.read()
    try:
        return raw.decode("utf-8")
    except Exception:
        return raw.decode("utf-8", errors="ignore")


def extract_json_var(html: str, var: str):
    """Lấy object JSON sau `var ... = ` bằng cách đếm ngoặc (chịu được HTML 1-2MB)."""
    i = html.find(var)
    if i < 0:
        return None
    j = html.find("{", i)
    if j < 0:
        return None
    depth = 0
    in_str = False
    esc = False
    for k in range(j, min(len(html), j + 8_000_000)):
        c = html[k]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        else:
            if c == '"':
                in_str = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(html[j:k + 1])
                    except Exception:
                        return None
    return None


def collect(node, key: str, out: list):
    """Thu thập mọi dict con có khóa `key` (đệ quy)."""
    if isinstance(node, dict):
        if key in node and isinstance(node[key], dict):
            out.append(node[key])
        for v in node.values():
            collect(v, key, out)
    elif isinstance(node, list):
        for v in node:
            collect(v, key, out)
    return out


def runs_text(node) -> str:
    if not node:
        return ""
    if isinstance(node, str):
        return node
    runs = node.get("runs") if isinstance(node, dict) else None
    if runs:
        return "".join(r.get("text", "") for r in runs)
    return node.get("simpleText", "") if isinstance(node, dict) else ""


def parse_duration(s: str):
    if not s:
        return None
    s = s.strip()
    if not re.fullmatch(r"[\d:]+", s):
        return None
    parts = [int(x) for x in s.split(":")]
    total = 0
    for p in parts:
        total = total * 60 + p
    return total


MILLION_UNITS = {"tr", "triệu", "trieuph", "m", "million", "mil", "tri"}
THOUSAND_UNITS = {"n", "k", "nghìn", "nghin", "thousand"}


def parse_views(s: str):
    if not s:
        return None
    s = unescape(s)
    m = re.search(r"([\d.,\s]+)\s*([A-Za-zÀ-ỹ]*)", s)
    if not m:
        return None
    num = m.group(1).strip().replace(" ", "")
    unit = (m.group(2) or "").lower()
    try:
        if unit in MILLION_UNITS:
            return int(float(num.replace(",", ".")) * 1_000_000)
        if unit in THOUSAND_UNITS:
            return int(float(num.replace(",", ".")) * 1_000)
        # Số thường: dấu . , chỉ là phân tách hàng nghìn (vd "12.345", "1,234")
        return int(re.sub(r"[.,\s]", "", num) or 0)
    except Exception:
        return None


def thumb_of(vid: str) -> str:
    return f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg" if vid else ""


def norm_search_item(r: dict):
    vid = r.get("videoId")
    if not vid:
        return None
    thumbs = (((r.get("thumbnail") or {}).get("thumbnails")) or [])
    thumb = (thumbs[-1].get("url") if thumbs else None) or thumb_of(vid)
    if isinstance(thumb, str) and thumb.startswith("//"):
        thumb = "https:" + thumb
    owner = runs_text(r.get("ownerText")) or runs_text(r.get("longBylineText")) or ""
    return {
        "id": vid,
        "title": runs_text(r.get("title")) or "(Không tiêu đề)",
        "description": runs_text(r.get("descriptionSnippet")) or "",
        "thumbnail_480_url": thumb,
        "thumbnail_720_url": thumb,
        "duration": parse_duration(runs_text(r.get("lengthText"))),
        "views_total": parse_views(runs_text(r.get("viewCountText")) or runs_text(r.get("shortViewCountText"))),
        "likes_total": None,
        "created_time": None,
        "owner.id": None,
        "owner.screenname": owner or "—",
        "embed_url": f"https://www.youtube.com/embed/{vid}",
        "url": f"https://www.youtube.com/watch?v={vid}",
        "channel": None,
        "tags": [],
    }


def norm_lockup(lk: dict, owner: str = ""):
    """Chuẩn hoá lockupViewModel (định dạng web mới của YouTube) -> shape DM."""
    if not isinstance(lk, dict):
        return None
    ct = lk.get("contentType") or ""
    if ct and ct not in ("LOCKUP_CONTENT_TYPE_VIDEO", "LOCKUP_CONTENT_TYPE_SHORTS", ""):
        return None
    vid = lk.get("contentId")
    if not vid or not isinstance(vid, str) or len(vid) > 16 or "/" in vid:
        tap = ((lk.get("rendererContext") or {}).get("commandContext", {})
               .get("onTap", {}).get("innertubeCommand", {}))
        we = tap.get("watchEndpoint") or {}
        vid = we.get("videoId")
    if not vid:
        return None
    meta = ((lk.get("metadata") or {}).get("lockupMetadataViewModel")) or {}
    title = ((meta.get("title") or {}).get("content")) or "(Không tiêu đề)"
    views = None
    try:
        rows = (((meta.get("metadata") or {}).get("contentMetadataViewModel") or {})
                .get("metadataRows")) or []
        parts = (rows[0].get("metadataParts") or []) if rows else []
        if parts:
            views = parse_views(((parts[0].get("text") or {}).get("content")) or "")
    except Exception:
        views = None
    dur = None
    try:
        for b in collect(lk, "thumbnailBadgeViewModel", []):
            t = b.get("text")
            if isinstance(t, str) and re.fullmatch(r"[\d:]+", t.strip()):
                dur = parse_duration(t.strip())
                if dur is not None:
                    break
    except Exception:
        pass
    thumb = thumb_of(vid)
    try:
        srcs = ((((lk.get("contentImage") or {}).get("thumbnailViewModel") or {})
                 .get("image") or {}).get("sources")) or []
        if srcs:
            best = max(srcs, key=lambda s: (s.get("width") or 0))
            u = best.get("url") or ""
            if u.startswith("//"):
                u = "https:" + u
            if u.startswith("http"):
                thumb = u
    except Exception:
        pass
    return {
        "id": vid,
        "title": title,
        "description": "",
        "thumbnail_480_url": thumb,
        "thumbnail_720_url": thumb,
        "duration": dur,
        "views_total": views,
        "likes_total": None,
        "created_time": None,
        "owner.id": None,
        "owner.screenname": owner or "—",
        "embed_url": f"https://www.youtube.com/embed/{vid}",
        "url": f"https://www.youtube.com/watch?v={vid}",
        "channel": None,
        "tags": [],
    }


def dedupe(videos: list) -> list:
    seen = set()
    out = []
    for v in videos:
        if not v or v.get("id") in seen:
            continue
        seen.add(v.get("id"))
        out.append(v)
    return out


def norm_mixed(data, owner: str = "") -> list:
    """Thu thập cả định dạng cũ (videoRenderer) lẫn mới (lockupViewModel)."""
    if not data:
        return []
    old = [v for v in (norm_search_item(r) for r in collect(data, "videoRenderer", [])) if v]
    new = [v for v in (norm_lockup(l, owner) for l in collect(data, "lockupViewModel", [])) if v]
    return dedupe([*old, *new])


def paginate(items: list, page: int, limit: int):
    page = max(1, page or 1)
    limit = max(1, min(50, limit or 12))
    start = (page - 1) * limit
    sl = items[start:start + limit]
    return {"list": sl, "has_more": start + limit < len(items), "total": len(items)}


SEARCH_SORT_SP = {"relevance": "", "recent": "CAISAhAB", "visited": "CAMSAhAB", "trending": "CAMSAhAB"}
CHANNEL_SORT = {"relevance": "dd", "recent": "dd", "visited": "p", "trending": "p"}


def fetch_search(query: str, sort: str):
    key = f"search:{sort}:{query}"
    hit = _cache_get(key)
    if hit is not None:
        return hit
    sp = SEARCH_SORT_SP.get(sort, "")
    url = ("https://www.youtube.com/results?search_query=" + urllib.parse.quote(query)
           + "&hl=vi&gl=VN" + (f"&sp={sp}" if sp else ""))
    html = yt_get(url)
    data = extract_json_var(html, "ytInitialData")
    videos = norm_mixed(data)
    _cache_set(key, videos)
    return videos


def fetch_trending():
    key = "trending"
    hit = _cache_get(key)
    if hit is not None:
        return hit
    # Feed trending thường trống với client ẩn danh -> fallback: tìm "thịnh hành" xếp theo lượt xem
    try:
        html = yt_get("https://www.youtube.com/feed/trending?hl=vi&gl=VN")
        data = extract_json_var(html, "ytInitialData")
        videos = norm_mixed(data)
    except Exception:
        videos = []
    if not videos:
        videos = fetch_search("thịnh hành", "visited")
    _cache_set(key, videos)
    return videos


def fetch_watch(vid: str):
    key = f"watch:{vid}"
    hit = _cache_get(key)
    if hit is not None:
        return hit
    html = yt_get(f"https://www.youtube.com/watch?v={urllib.parse.quote(vid)}&hl=vi&gl=VN")
    player = extract_json_var(html, "ytInitialPlayerResponse")
    data = extract_json_var(html, "ytInitialData")
    if data is None:
        # Thỉnh thoảng YouTube trả trang nhẹ thiếu ytInitialData -> tải lại 1 lần
        try:
            html = yt_get(f"https://www.youtube.com/watch?v={urllib.parse.quote(vid)}&hl=vi&gl=VN")
            player = extract_json_var(html, "ytInitialPlayerResponse") or player
            data = extract_json_var(html, "ytInitialData")
        except Exception:
            pass
    vd = (player or {}).get("videoDetails") or {}
    micro = {}
    lst = []
    collect(player, "playerMicroformatRenderer", lst)
    if lst:
        micro = lst[0]
    title = vd.get("title") or ""
    if not title:
        m = re.search(r"<title>(.*?)</title>", html, re.S)
        title = unescape(m.group(1)).replace(" - YouTube", "").strip() if m else vid
    author = vd.get("author") or ""
    channel_id = vd.get("channelId")
    if not channel_id:
        m = re.search(r'"channelId":"(UC[^"]+)"', html)
        channel_id = m.group(1) if m else None
    created = None
    pub = micro.get("publishDate") or micro.get("uploadDate")
    if pub:
        try:
            created = int(time.mktime(time.strptime(str(pub)[:10], "%Y-%m-%d")))
        except Exception:
            created = None
    try:
        views = int(vd.get("viewCount") or 0) or None
    except Exception:
        views = None
    try:
        dur = int(float(vd.get("lengthSeconds") or 0)) or None
    except Exception:
        dur = None
    detail = {
        "id": vid,
        "title": title or vid,
        "description": (vd.get("shortDescription") or "")[:2000],
        "thumbnail_480_url": thumb_of(vid),
        "thumbnail_720_url": thumb_of(vid),
        "duration": dur,
        "views_total": views,
        "likes_total": None,
        "created_time": created,
        "owner.id": channel_id,
        "owner.screenname": author or "—",
        "embed_url": f"https://www.youtube.com/embed/{vid}",
        "url": f"https://www.youtube.com/watch?v={vid}",
        "channel": channel_id,
        "tags": list(vd.get("keywords") or [])[:20],
    }
    related = []
    for n in norm_mixed(data):
        if n["id"] != vid:
            related.append(n)
    res = (detail, related)
    _cache_set(key, res)
    return res


def resolve_channel_id(owner: str) -> str:
    """UC... giữ nguyên; @handle / tên custom -> fetch trang kênh để lấy channelId."""
    o = (owner or "").strip().lstrip("@")
    if re.fullmatch(r"UC[A-Za-z0-9_-]{20,}", o):
        return o
    key = f"resolve:{o.lower()}"
    hit = _cache_get(key)
    if hit:
        return hit
    q = urllib.parse.quote(o)
    cands = [f"https://www.youtube.com/@{q}",
             f"https://www.youtube.com/c/{q}",
             f"https://www.youtube.com/user/{q}"]
    for url in cands:
        try:
            html = yt_get(url + "?hl=vi&gl=VN")
        except Exception:
            continue
        m = re.search(r'"channelId":"(UC[^"]+)"', html)
        if not m:
            m = re.search(r'/(?:channel/)(UC[A-Za-z0-9_-]{20,})', html)
        if m:
            _cache_set(key, m.group(1))
            return m.group(1)
    raise ValueError("Không tìm thấy kênh.")


def fetch_channel(owner: str, sort: str):
    key = f"channel:{sort}:{owner}"
    hit = _cache_get(key)
    if hit is not None:
        return hit
    sort_q = CHANNEL_SORT.get(sort, "dd")
    cid = resolve_channel_id(owner)
    url = (f"https://www.youtube.com/channel/{cid}/videos"
           f"?view=0&sort={sort_q}&hl=vi&gl=VN")
    html = yt_get(url)
    data = extract_json_var(html, "ytInitialData")
    # Tên kênh để gắn owner cho từng video
    author = ""
    try:
        m = re.search(r"<title>(.*?)</title>", html, re.S)
        if m:
            author = unescape(m.group(1)).replace(" - YouTube", "").strip()
    except Exception:
        pass
    videos = norm_mixed(data, author)
    _cache_set(key, videos)
    return videos


def fetch_playlist(pid: str):
    key = f"playlist:{pid}"
    hit = _cache_get(key)
    if hit is not None:
        return hit
    html = yt_get(f"https://www.youtube.com/playlist?list={urllib.parse.quote(pid)}&hl=vi&gl=VN")
    data = extract_json_var(html, "ytInitialData")
    title = f"Playlist {pid}"
    m = re.search(r"<title>(.*?)</title>", html, re.S)
    if m:
        title = unescape(m.group(1)).replace(" - YouTube", "").strip() or title
    videos = norm_mixed(data)
    if not videos and data:
        # Fallback định dạng cũ
        items = collect(data, "playlistPanelVideoRenderer", [])
        for r in items:
            vid = r.get("videoId")
            if not vid:
                continue
            owner = runs_text(r.get("longBylineText")) or runs_text(r.get("shortBylineText")) or ""
            videos.append({
                "id": vid,
                "title": runs_text(r.get("title")) or "(Không tiêu đề)",
                "description": "",
                "thumbnail_480_url": thumb_of(vid),
                "thumbnail_720_url": thumb_of(vid),
                "duration": parse_duration(runs_text(r.get("lengthText"))),
                "views_total": None,
                "likes_total": None,
                "created_time": None,
                "owner.id": None,
                "owner.screenname": owner or "—",
                "embed_url": f"https://www.youtube.com/embed/{vid}",
                "url": f"https://www.youtube.com/watch?v={vid}&list={pid}",
                "channel": None,
                "tags": [],
            })
        if not videos:
            for r in collect(data, "videoRenderer", []):
                n = norm_search_item(r)
                if n:
                    videos.append(n)
    meta = {"id": pid, "name": title, "description": "",
            "thumbnail_480_url": thumb_of(videos[0]["id"]) if videos else "",
            "videos_total": len(videos), "owner.screenname": "", "owner": ""}
    res = (meta, videos)
    _cache_set(key, res)
    return res


@router.get("/search")
def yt_search(q: str = "", page: int = 1, limit: int = 12, sort: str = "relevance",
              user: User = Depends(current_user)):
    try:
        videos = fetch_search(q or "nhạc", sort or "relevance")
    except Exception as e:
        return {"success": False, "data": None, "message": f"Không tải được YouTube: {e}"}
    return ok(paginate(videos, page, limit))


@router.get("/trending")
def yt_trending(page: int = 1, limit: int = 12, user: User = Depends(current_user)):
    try:
        videos = fetch_trending()
    except Exception as e:
        return {"success": False, "data": None, "message": f"Không tải được YouTube: {e}"}
    return ok(paginate(videos, page, limit))


@router.get("/videos/{vid}")
def yt_video(vid: str, user: User = Depends(current_user)):
    try:
        detail, _ = fetch_watch(vid)
    except Exception as e:
        return {"success": False, "data": None, "message": f"Không tải được video: {e}"}
    return ok(detail)


@router.get("/videos/{vid}/related")
def yt_related(vid: str, limit: int = 12, user: User = Depends(current_user)):
    try:
        _, related = fetch_watch(vid)
    except Exception as e:
        return {"success": False, "data": None, "message": f"Không tải được gợi ý: {e}"}
    return ok({"list": related[: max(1, min(50, limit))], "has_more": False, "total": len(related)})


@router.get("/channels/{owner}/videos")
def yt_channel(owner: str, page: int = 1, limit: int = 12, sort: str = "recent",
               user: User = Depends(current_user)):
    try:
        videos = fetch_channel(owner, sort or "recent")
    except Exception as e:
        return {"success": False, "data": None, "message": f"Không tải được kênh: {e}"}
    if not videos:
        return {"success": False, "data": None, "message": "Không tìm thấy kênh hoặc kênh không có video."}
    return ok(paginate(videos, page, limit))


@router.get("/playlists/{pid}")
def yt_playlist_meta(pid: str, user: User = Depends(current_user)):
    try:
        meta, _ = fetch_playlist(pid)
    except Exception as e:
        return {"success": False, "data": None, "message": f"Không tải được playlist: {e}"}
    return ok(meta)


@router.get("/playlists/{pid}/videos")
def yt_playlist_videos(pid: str, page: int = 1, limit: int = 12, user: User = Depends(current_user)):
    try:
        _, videos = fetch_playlist(pid)
    except Exception as e:
        return {"success": False, "data": None, "message": f"Không tải được playlist: {e}"}
    if not videos:
        return {"success": False, "data": None, "message": "Playlist trống hoặc không đọc được."}
    return ok(paginate(videos, page, limit))
