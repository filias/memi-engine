"""Generic image fetching utilities for memi.

These functions fetch images from Wikipedia, Wikimedia Commons, TMDB,
Fandom, and other sources. They are used by CategoryProviders to
resolve item names to image URLs.
"""

from __future__ import annotations

import os
import time

import requests

HEADERS = {"User-Agent": "Memi/1.0 (https://memi.click; memi@memi.click)"}
TMDB_API_KEY = os.environ.get("TMDB_API_KEY", "")
BONES_API_URL = os.environ.get("BONES_API_URL", "http://127.0.0.1:8081")

# Simple in-memory cache: {key: (result, timestamp)}
_cache: dict = {}
_CACHE_TTL = 3600  # 1 hour


def _cached(key: str, fn):
    """Return cached result or call fn() and cache it."""
    now = time.time()
    if key in _cache:
        result, ts = _cache[key]
        if now - ts < _CACHE_TTL:
            return dict(result) if isinstance(result, dict) else result
    result = fn()
    _cache[key] = (result, now)
    if len(_cache) > 5000:
        cutoff = now - _CACHE_TTL
        to_delete = [k for k, (_, ts) in _cache.items() if ts < cutoff]
        for k in to_delete:
            del _cache[k]
    return result


# --- Wikipedia ---


def get_wikipedia_image(title: str) -> dict | None:
    """Get the main image from a Wikipedia article."""
    return _cached(f"wp_img:{title}", lambda: _fetch_wikipedia_image(title))


def _fetch_wikipedia_image(title):
    try:
        resp = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "titles": title,
                "prop": "pageimages",
                "pithumbsize": 800,
                "format": "json",
            },
            headers=HEADERS,
            timeout=10,
        )
        if resp.status_code != 200:
            return None
        pages = resp.json().get("query", {}).get("pages", {})
        for page in pages.values():
            thumb = page.get("thumbnail", {}).get("source")
            if thumb:
                return {"name": page.get("title", title), "image": thumb}
    except Exception:
        pass
    return None


def get_wikipedia_file_image(filename: str) -> dict | None:
    """Get a thumbnail URL for a file hosted on English Wikipedia."""
    return _cached(
        f"wp_file:{filename}", lambda: _fetch_wikipedia_file_image(filename)
    )


def _fetch_wikipedia_file_image(filename):
    try:
        resp = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "titles": f"File:{filename}",
                "prop": "imageinfo",
                "iiprop": "url",
                "iiurlwidth": 500,
                "format": "json",
            },
            headers=HEADERS,
            timeout=10,
        )
        if resp.status_code != 200:
            return None
        pages = resp.json().get("query", {}).get("pages", {})
        for page in pages.values():
            if "imageinfo" in page:
                info = page["imageinfo"][0]
                thumb = info.get("thumburl") or info.get("url")
                if thumb:
                    return {"name": filename, "image": thumb}
    except Exception:
        pass
    return None


def get_wikipedia_description(title: str) -> str:
    """Get the short description of a Wikipedia article."""
    return _cached(
        f"wp_desc:{title}", lambda: _fetch_wikipedia_description(title)
    )


def _fetch_wikipedia_description(title):
    try:
        resp = requests.get(
            "https://en.wikipedia.org/api/rest_v1/page/summary/" + title,
            headers=HEADERS,
            timeout=5,
        )
        if resp.status_code == 200:
            return resp.json().get("description", "")
    except Exception:
        pass
    return ""


# --- Wikimedia Commons ---


def get_commons_file_image(filename: str) -> dict | None:
    """Get a thumbnail URL for a Wikimedia Commons file."""
    return _cached(
        f"commons:{filename}", lambda: _fetch_commons_file_image(filename)
    )


def _fetch_commons_file_image(filename):
    try:
        resp = requests.get(
            "https://commons.wikimedia.org/w/api.php",
            params={
                "action": "query",
                "titles": f"File:{filename}",
                "prop": "imageinfo",
                "iiprop": "url",
                "iiurlwidth": 400,
                "format": "json",
            },
            headers=HEADERS,
            timeout=10,
        )
        if resp.status_code != 200:
            return None
        pages = resp.json().get("query", {}).get("pages", {})
        for page in pages.values():
            if "imageinfo" in page:
                info = page["imageinfo"][0]
                thumb = info.get("thumburl") or info.get("url")
                if thumb:
                    return {"name": filename, "image": thumb}
    except Exception:
        pass
    return None


# --- TMDB ---


def get_tmdb_image(title: str, image_type: str = "backdrop") -> dict | None:
    """Search TMDB for a movie and return its backdrop or poster."""
    return _cached(
        f"tmdb:{title}:{image_type}",
        lambda: _fetch_tmdb_image(title, image_type),
    )


def _fetch_tmdb_image(title, image_type="backdrop"):
    if not TMDB_API_KEY:
        return None
    search_term = title.split("(")[0].strip()
    try:
        resp = requests.get(
            "https://api.themoviedb.org/3/search/movie",
            params={"query": search_term},
            headers={"Authorization": f"Bearer {TMDB_API_KEY}"},
            timeout=10,
        )
        if resp.status_code != 200:
            return None
        results = resp.json().get("results", [])
        if not results:
            return None
        movie = results[0]
        path = (
            movie.get("backdrop_path")
            if image_type == "backdrop"
            else movie.get("poster_path")
        )
        if not path:
            path = movie.get("poster_path") or movie.get("backdrop_path")
        if not path:
            return None
        size = "w780" if image_type == "backdrop" else "w500"
        return {"name": title, "image": f"https://image.tmdb.org/t/p/{size}{path}"}
    except Exception:
        return None


def get_tmdb_tv_image(title: str, image_type: str = "backdrop") -> dict | None:
    """Search TMDB for a TV show and return its backdrop or poster."""
    return _cached(
        f"tmdb_tv:{title}:{image_type}",
        lambda: _fetch_tmdb_tv_image(title, image_type),
    )


def _fetch_tmdb_tv_image(title, image_type="backdrop"):
    if not TMDB_API_KEY:
        return None
    search_term = title.split("(")[0].strip()
    try:
        resp = requests.get(
            "https://api.themoviedb.org/3/search/tv",
            params={"query": search_term},
            headers={"Authorization": f"Bearer {TMDB_API_KEY}"},
            timeout=10,
        )
        if resp.status_code != 200:
            return None
        results = resp.json().get("results", [])
        if not results:
            return None
        show = results[0]
        path = (
            show.get("backdrop_path")
            if image_type == "backdrop"
            else show.get("poster_path")
        )
        if not path:
            path = show.get("poster_path") or show.get("backdrop_path")
        if not path:
            return None
        size = "w780" if image_type == "backdrop" else "w500"
        return {"name": title, "image": f"https://image.tmdb.org/t/p/{size}{path}"}
    except Exception:
        return None


# --- Fandom ---


def get_fandom_image(title: str, wiki: str) -> dict | None:
    """Get an image from a Fandom wiki."""
    return _cached(
        f"fandom:{wiki}:{title}", lambda: _fetch_fandom_image(title, wiki)
    )


def _fetch_fandom_image(title, wiki):
    clean = title.split("(")[0].strip().replace(" ", "_")
    try:
        resp = requests.get(
            f"https://{wiki}.fandom.com/api.php",
            params={"action": "imageserving", "wisTitle": clean, "format": "json"},
            headers=HEADERS,
            timeout=10,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        image_url = data.get("image", {}).get("imageserving")
        if image_url:
            image_url = image_url.split("/revision/")[0]
            return {"name": title, "image": image_url}
    except Exception:
        pass
    return None


# --- Specialized fetchers ---


def get_dino_image(name: str) -> dict | None:
    """Search Wikimedia Commons for a dinosaur life restoration."""
    return _cached(f"dino:{name}", lambda: _fetch_dino_image(name))


def _fetch_dino_image(name):
    try:
        resp = requests.get(
            "https://commons.wikimedia.org/w/api.php",
            params={
                "action": "query",
                "list": "search",
                "srnamespace": 6,
                "srsearch": f"{name} restoration OR reconstruction OR paleoart",
                "srlimit": 10,
                "format": "json",
            },
            headers=HEADERS,
            timeout=10,
        )
        if resp.status_code != 200:
            return None
        results = resp.json().get("query", {}).get("search", [])
        name_lower = name.lower().split()[0]
        skip = ["skeleton", "skull", "fossil", "bone", "tooth", "mount", "cast"]
        chosen = None
        for r in results:
            title = r["title"].lower()
            if name_lower in title and not any(bad in title for bad in skip):
                chosen = r["title"]
                break
        if not chosen:
            return None
        result = get_commons_file_image(chosen.replace("File:", ""))
        if result:
            result["name"] = name
        return result
    except Exception:
        return None


def get_river_map(title: str) -> dict | None:
    """Find a river map/basin image from Wikipedia."""
    try:
        resp = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "titles": title,
                "prop": "images",
                "imlimit": 100,
                "format": "json",
            },
            headers=HEADERS,
            timeout=10,
        )
        if resp.status_code != 200:
            return None
        pages = resp.json().get("query", {}).get("pages", {})
        map_keywords = ["map", "basin", "watershed", "course", "locator"]
        map_files = []
        river_name = (
            title.split("(")[0].replace("River", "").replace("river", "").strip().lower()
        )
        for page in pages.values():
            for img in page.get("images", []):
                fname = img["title"].lower()
                if any(kw in fname for kw in map_keywords) and "commons-logo" not in fname:
                    map_files.append(img["title"])
        if not map_files:
            return None
        chosen = None
        for f in map_files:
            if any(word in f.lower() for word in river_name.split() if len(word) > 2):
                chosen = f
                break
        if not chosen:
            chosen = map_files[0]
        resp2 = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "titles": chosen,
                "prop": "imageinfo",
                "iiprop": "url",
                "iiurlwidth": 500,
                "format": "json",
            },
            headers=HEADERS,
            timeout=10,
        )
        if resp2.status_code != 200:
            return None
        pages2 = resp2.json().get("query", {}).get("pages", {})
        for page in pages2.values():
            if "imageinfo" in page:
                thumb = page["imageinfo"][0].get("thumburl")
                if thumb:
                    return {"name": title, "image": thumb}
    except Exception:
        pass
    return None


def get_country_shape(country: str) -> dict | None:
    """Fetch an orthographic projection map of a country."""
    return _cached(f"shape:{country}", lambda: _fetch_country_shape(country))


def _fetch_country_shape(country):
    filename = f"File:{country} (orthographic projection).svg"
    try:
        resp = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "titles": filename,
                "prop": "imageinfo",
                "iiprop": "url",
                "iiurlwidth": 500,
                "format": "json",
            },
            headers=HEADERS,
            timeout=10,
        )
        if resp.status_code != 200:
            return None
        pages = resp.json().get("query", {}).get("pages", {})
        for page in pages.values():
            if "imageinfo" in page:
                thumb = page["imageinfo"][0].get("thumburl")
                if thumb:
                    return {"name": country, "image": thumb}
    except Exception:
        pass
    return None


def get_grays_anatomy_image(title: str) -> dict | None:
    """Search Commons for a Gray's Anatomy illustration."""
    try:
        search_term = title.split("(")[0].strip()
        resp = requests.get(
            "https://commons.wikimedia.org/w/api.php",
            params={
                "action": "query",
                "list": "search",
                "srnamespace": 6,
                "srsearch": f'"Gray\'s Anatomy" {search_term} png',
                "srlimit": 5,
                "format": "json",
            },
            headers=HEADERS,
            timeout=10,
        )
        if resp.status_code != 200:
            return None
        results = resp.json().get("query", {}).get("search", [])
        if not results:
            return None
        chosen = results[0]["title"]
        for r in results:
            if search_term.lower().split()[0] in r["title"].lower():
                chosen = r["title"]
                break
        return get_commons_file_image(chosen.replace("File:", ""))
    except Exception:
        return None


def get_bone_image(bone_id: str) -> dict | None:
    """Fetch a bone image from the Bones API."""
    try:
        resp = requests.get(f"{BONES_API_URL}/bones/{bone_id}", timeout=10)
        if resp.status_code != 200:
            return None
        data = resp.json()
        if not data.get("has_image"):
            return None
        return {
            "name": data["name"],
            "image": f"/api/bones/image/{bone_id}",
            "tag": data.get("region", ""),
        }
    except Exception:
        return None


def get_album_cover(album_name: str, mbid: str | None) -> dict | None:
    """Get an album cover from Cover Art Archive using a MusicBrainz ID."""
    if not mbid:
        return None
    return {
        "name": album_name,
        "image": f"https://coverartarchive.org/release-group/{mbid}/front-500",
    }


def get_logo_image(title: str) -> dict | None:
    """Search a Wikipedia article for logo images."""
    try:
        resp = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "titles": title,
                "prop": "images",
                "imlimit": 50,
                "format": "json",
            },
            headers=HEADERS,
            timeout=10,
        )
        if resp.status_code != 200:
            return None
        pages = resp.json().get("query", {}).get("pages", {})
        logo_files = []
        name_lower = title.split("(")[0].strip().lower()
        for page in pages.values():
            for img in page.get("images", []):
                fname = img["title"].lower()
                if "logo" in fname and "commons-logo" not in fname:
                    logo_files.append(img["title"])
        if not logo_files:
            return None
        logo_file = None
        for f in logo_files:
            if any(
                word in f.lower() for word in name_lower.split() if len(word) > 2
            ):
                logo_file = f
                break
        if not logo_file:
            logo_file = logo_files[0]
        resp2 = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "titles": logo_file,
                "prop": "imageinfo",
                "iiprop": "url",
                "iiurlwidth": 500,
                "format": "json",
            },
            headers=HEADERS,
            timeout=10,
        )
        if resp2.status_code != 200:
            return None
        pages2 = resp2.json().get("query", {}).get("pages", {})
        for page in pages2.values():
            if "imageinfo" in page:
                thumb = page["imageinfo"][0].get("thumburl")
                if thumb:
                    return {"name": title, "image": thumb}
    except Exception:
        pass
    return None
