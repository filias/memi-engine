"""Generic image fetching utilities for memi.

These functions fetch images from Wikipedia, Wikimedia Commons, TMDB,
Fandom, and other sources. They are used by CategoryProviders to
resolve item names to image URLs.
"""

from __future__ import annotations

import contextvars
import os
import re
import time
from importlib.metadata import version as _pkg_version
from urllib.parse import quote, unquote

import requests

_VERSION = _pkg_version("memi-engine")
HEADERS = {
    "User-Agent": f"memi-engine/{_VERSION} (https://memi.click; memi@memi.click)"
}
TMDB_API_KEY = os.environ.get("TMDB_API_KEY", "")
BONES_API_URL = os.environ.get("BONES_API_URL", "http://127.0.0.1:8081")

# Wikipedia language edition used by the default image/description helpers.
# Configurable via MemiConfig.wikipedia_lang or the MEMI_WIKIPEDIA_LANG env var.
_WIKIPEDIA_LANG = os.environ.get("MEMI_WIKIPEDIA_LANG", "en")


# Language the details panel is written in: the game's own (``html_lang``).
# An article found in another edition is swapped for its counterpart here
# when one exists. ``None`` keeps whatever edition the card links to.
_DETAILS_LANG: str | None = None


# The language of the request being served, when it isn't the game's own
# (a game played in a second language, see MemiConfig.languages).
_REQUEST_DETAILS_LANG: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "memi_details_lang", default=None
)


def details_lang() -> str | None:
    """The language the details panel should be written in right now."""
    return _REQUEST_DETAILS_LANG.get() or _DETAILS_LANG


def use_details_lang(lang: str | None):
    """Write the details panel in ``lang`` for the rest of this request.

    Returns a token for :func:`reset_details_lang`.
    """
    return _REQUEST_DETAILS_LANG.set(lang.split("-")[0].lower() if lang else None)


def reset_details_lang(token) -> None:
    _REQUEST_DETAILS_LANG.reset(token)


def set_details_lang(lang: str | None) -> None:
    """Set the language of the details panel (e.g. "pt"; "pt-PT" counts as "pt")."""
    global _DETAILS_LANG
    _DETAILS_LANG = lang.split("-")[0].lower() if lang else None


def set_wikipedia_lang(lang: str) -> None:
    """Set the Wikipedia language edition used by the default helpers (e.g. "pt")."""
    global _WIKIPEDIA_LANG
    if lang:
        _WIKIPEDIA_LANG = lang


def _wiki_api() -> str:
    """Return the Wikipedia action-API endpoint for the configured language."""
    return f"https://{_WIKIPEDIA_LANG}.wikipedia.org/w/api.php"


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
            _wiki_api(),
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
                page_title = page.get("title", title)
                slug = quote(page_title.replace(" ", "_"))
                return {
                    "name": page_title,
                    "image": thumb,
                    "url": f"https://{_WIKIPEDIA_LANG}.wikipedia.org/wiki/{slug}",
                }
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
            _wiki_api(),
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
            f"https://{_WIKIPEDIA_LANG}.wikipedia.org/api/rest_v1/page/summary/{title}",
            headers=HEADERS,
            timeout=5,
        )
        if resp.status_code == 200:
            return resp.json().get("description", "")
    except Exception:
        pass
    return ""


# --- Wikipedia articles (the enriched layout's details panel) ---

_WIKI_URL = re.compile(r"^https?://([a-z][a-z-]*)\.(?:m\.)?wikipedia\.org/wiki/([^?#]+)")


def wikipedia_title_from_url(url: str) -> tuple[str, str] | None:
    """``(lang, title)`` of a Wikipedia article URL, or ``None`` for any other URL.

    ``"https://pt.wikipedia.org/wiki/Torre_de_Bel%C3%A9m"`` ->
    ``("pt", "Torre de Belém")``.
    """
    match = _WIKI_URL.match(url or "")
    if not match:
        return None
    return match.group(1), unquote(match.group(2)).replace("_", " ")


# Successful lookups only: a failed request (a network blip, a rate limit)
# must not hide a card's details until the process restarts.
_article_cache: dict = {}
_ARTICLE_CACHE_MAX = 5000


def get_wikipedia_article(title: str, lang: str | None = None) -> dict | None:
    """The opening paragraph and coordinates of a Wikipedia article.

    Returns ``{"intro": str, "coords": (lat, lon) | None}``, or ``None`` when
    the lookup fails. ``lang`` defaults to the configured Wikipedia language.

    Coordinates come from the article's Wikidata item (P625) rather than from
    Wikipedia: the article's own are often only "secondary" (missing from the
    default API answer) and sometimes plainly wrong.
    """
    lang = lang or _WIKIPEDIA_LANG
    key = (title, lang)
    if key in _article_cache:
        return _article_cache[key]
    try:
        resp = requests.get(
            f"https://{lang}.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "format": "json",
                "prop": "extracts|pageprops",
                "exintro": 1,
                "explaintext": 1,
                "ppprop": "wikibase_item",
                "redirects": 1,
                "titles": title,
            },
            headers=HEADERS,
            timeout=5,
        )
        resp.raise_for_status()
        page = next(iter(resp.json()["query"]["pages"].values()))
        if "missing" in page:
            return None
        qid = page.get("pageprops", {}).get("wikibase_item")
        coords = None
        if qid:
            resp = requests.get(
                "https://www.wikidata.org/w/api.php",
                params={
                    "action": "wbgetclaims",
                    "format": "json",
                    "entity": qid,
                    "property": "P625",
                },
                headers=HEADERS,
                timeout=5,
            )
            resp.raise_for_status()
            claims = resp.json().get("claims", {}).get("P625", [])
            if claims:
                value = claims[0]["mainsnak"]["datavalue"]["value"]
                coords = (value["latitude"], value["longitude"])
    except Exception:
        return None
    article = {"intro": wikipedia_intro(page.get("extract", "")), "coords": coords}
    if len(_article_cache) >= _ARTICLE_CACHE_MAX:
        _article_cache.clear()
    _article_cache[key] = article
    return article


_langlink_cache: dict = {}


def wikipedia_langlink(title: str, from_lang: str, to_lang: str) -> str | None:
    """Title of the ``to_lang`` edition's article on the same subject, or ``None``.

    ``("Belém Tower", "en", "pt")`` -> ``"Torre de Belém"``. Found titles are
    cached; failed lookups are not, so a network blip isn't remembered.
    """
    if from_lang == to_lang:
        return title
    key = (title, from_lang, to_lang)
    if key in _langlink_cache:
        return _langlink_cache[key]
    try:
        resp = requests.get(
            f"https://{from_lang}.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "format": "json",
                "prop": "langlinks",
                "lllang": to_lang,
                "redirects": 1,
                "titles": title,
            },
            headers=HEADERS,
            timeout=5,
        )
        resp.raise_for_status()
        page = next(iter(resp.json()["query"]["pages"].values()))
    except Exception:
        return None
    links = page.get("langlinks") or []
    found = links[0].get("*") if links else None
    if len(_langlink_cache) >= _ARTICLE_CACHE_MAX:
        _langlink_cache.clear()
    _langlink_cache[key] = found
    return found


# Copulas that follow an article's subject, for the asides below ("The Cloth
# Hall (…), is a …", "A Torre de Belém (…) é uma …").
_VERB = r"(?:is|are|was|were|é|foi|são|era|eram|foram|fue|es|est|war|ist)"
# A parenthetical that is pronunciation or another language's name — "(Polish:
# Sukiennice, pronounced [sukʲɛˈɲːit͡sɛ])", "(in Polish. Kopiec Krakusa)",
# "(pronúncia: [ˈtoʁɨ])" — rather
# than content. A comma right after it belonged to the aside when the
# sentence carries on with its verb.
_ASIDE = re.compile(
    r"\s*\((?=[^()]*(?:\[|:|pronounc|pronúnc|pronunc|listen|ouvir|escutar"
    r"|\b(?:in|em|en) [^\W\d]+\.\s))[^()]*\)"
    rf"(?:,(?=\s+{_VERB}\b))?"
)
_IPA = re.compile(r"\s*\[[^\[\]]*\]")
# English pronunciation respellings ("NASH-vil", "kə-LIST-oh", "YUK-ə"), as
# the extract leaves them: right after an opening parenthesis and a space.
_RESPELL = r"(?:[A-Za-zə]+-)+[A-Za-zə]+|[A-Za-z]*ə[A-Za-zə]*"
_RESPELLING = re.compile(
    rf"\(\s+(?:{_RESPELL})(?:\s+or\s+(?:{_RESPELL}))*\s*(?:;\s*|(?=\)))"
)
_HONOURS = re.compile(r"(?:\s+[A-Z][A-Za-z]{0,6}\s+•)+\s+[A-Z][A-Za-z]{0,6}(?=[\s,(])")
# A full stop that ends a sentence, not an abbreviation ("St. Mary's", "Sr.
# Jesus", "séc. XVI", "ul. Lipowa") or an initial ("Jan A. Kowalski", "D.
# Manuel", "n. 1950").
_SENTENCE_END = re.compile(
    r"(?<!\bSt\.)(?<!\bSr\.)(?<!\bSt[oa]\.)(?<!\bMt\.)(?<!\bDr\.)"
    r"(?<!\bProf\.)(?<!\bséc\.)(?<!\bul\.)(?<!\blit\.)(?<!\b[A-Za-z]\.)"
    r"(?<=[.!?])\s+(?=[A-ZÀ-ÝŁŚŻŹĆŃ])"
)


def wikipedia_intro(extract: str, limit: int = 600) -> str:
    """First paragraph of a plain-text extract, minus pronunciation asides.

    Trimmed to whole sentences within ``limit`` characters (the first sentence
    is always kept).
    """
    para = next((p.strip() for p in extract.split("\n") if p.strip()), "")
    # Transcriptions go first: they can hold parentheses of their own
    # ("[ˈspɔɾtĩɡ(ɨ)]") that would stop the aside around them from matching.
    para = _IPA.sub("", para)
    # Respellings, and separators orphaned by what the extract already dropped:
    # "Nashville ( NASH-vil)", "Huston ( HEW-stən; August 5, 1906 – …)",
    # "Gamelan (;Javanese: …)".
    para = _RESPELLING.sub("(", para)
    para = re.sub(r"\(\s*[;,]\s*", "(", para)
    # Innermost asides first, so nested ones — "(Polish: […]; colloquially
    # kremówka (Polish: […]))" — peel away level by level.
    for _ in range(3):
        para = _ASIDE.sub("", para)
    # Honours after a name: "Sporting Clube de Portugal ComC • MHIH • OB".
    para = _HONOURS.sub("", para)
    # Whatever is left of an aside that never closed ("Napoleonka (Polish: ;
    # colloquially kremówka is a …"): drop it up to its verb, within the
    # sentence.
    para = re.sub(
        rf"\s*\((?![^()]*\))[^().]*?[;:][^().]*?(?=\s{_VERB}\b)", "", para
    )
    # An aside emptied of everything but punctuation: "Lisboa ( ) é …".
    para = re.sub(r"\s*\([\s,;:]*\)", "", para)
    para = re.sub(r"\s+([,.;])", r"\1", re.sub(r"\s{2,}", " ", para)).strip()
    # A quoted name leading the paragraph: "”Manggha” Museum …".
    para = re.sub(r'^["“”„]([^"“”„]+)["“”„]', r"\1", para)
    if len(para) <= limit:
        return para
    sentences = _SENTENCE_END.split(para)
    kept = sentences[0]
    for sentence in sentences[1:]:
        if len(kept) + 1 + len(sentence) > limit:
            break
        kept += " " + sentence
    return kept


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
                    slug = quote(filename.replace(" ", "_"))
                    return {
                        "name": filename,
                        "image": thumb,
                        "url": f"https://commons.wikimedia.org/wiki/File:{slug}",
                    }
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
            headers={**HEADERS, "Authorization": f"Bearer {TMDB_API_KEY}"},
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
            headers={**HEADERS, "Authorization": f"Bearer {TMDB_API_KEY}"},
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
            _wiki_api(),
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
            title.split("(")[0]
            .replace("River", "")
            .replace("river", "")
            .strip()
            .lower()
        )
        for page in pages.values():
            for img in page.get("images", []):
                fname = img["title"].lower()
                is_map = any(kw in fname for kw in map_keywords)
                if is_map and "commons-logo" not in fname:
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
            _wiki_api(),
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
            _wiki_api(),
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
        resp = requests.get(
            f"{BONES_API_URL}/bones/{bone_id}", headers=HEADERS, timeout=10
        )
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
            _wiki_api(),
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
            _wiki_api(),
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
