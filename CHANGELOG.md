# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.5.0] - 2026-10-14

### Added
- **Audio: a speaker button on reveal.** A provider's new
  `get_audio(item)` returns `{"text", "lang", "src"}`; the card then shows a
  round speaker button once revealed (any layout). It plays the recording at
  `src` and falls back to the browser's speech synthesis of `text` in `lang`
  when there is no recording, or when it fails to play (Chromium can't decode
  the AAC in phone voice memos, for one). The browser voice is picked by
  language, so a phone set to English still reads Polish with a Polish voice.
  Tapping the button doesn't advance the card; loading the next card stops any
  playback. `AggregateProvider` delegates it; the label is `label_listen`.

## [0.4.2] - 2026-10-14

### Changed
- **Category URLs are plain ASCII slugs.** `/<slug>` used the raw category name,
  so a name with a space, apostrophe, `&` or accent (`marta’s tips`, `road
  signs`, `mestá`) gave a link that chat apps cut at the space or turned into
  `%C3%A1`. Slugs are now lowercase ASCII words joined by dashes (`/martas-tips`,
  `/road-signs`, `/mesta`) — `seo.slugify`. The old raw URLs keep working and
  canonicalise to the new ones, so links already shared don't break. Names with
  nothing ASCII in them (a non-Latin script) keep their raw slug.

### Added
- **The address bar follows the game.** Picking a category replaces the URL with
  its shareable `/<slug>` (and with `/` when none, or several, are selected), so
  the link to share is right there to copy. `replaceState`, not `pushState`:
  switching categories doesn't fill the back button. The page gets the slugs as
  `CATEGORY_SLUGS`.

## [0.4.1] - 2026-10-14

### Changed
- The enriched layout's details panel is headed by the card's name, with the
  area underneath it. It used to open with the area, which read as the panel's
  title ("KAZIMIERZ" above Hevre's notes); panels with only a map now get a
  title too.

## [0.4.0] - 2026-10-14

### Added
- **Two layouts: `MemiConfig.layout = "classic" | "enriched"`.** `"classic"`
  (the default) is the game exactly as before, so existing instances don't
  change. `"enriched"` adds:
  - a **details panel** that appears on reveal, beside the card on wide screens
    (≥1200px, hanging off the card so the card never shifts) and below it
    otherwise. It shows a provider's longer text, a linked area name, and an
    OpenStreetMap view pinned on the item, with an "open map" link
    (`label_open_map`);
  - a prominent **"know more"** button (an accent pill instead of grey text).
    On phones it is pinned to the bottom of the screen while showing: the square
    card fills the width and used to push it below the fold.
- **`CategoryProvider.get_details(item)`** feeds the panel:
  `{"text", "area": {"name", "url"}, "map": {"lat", "lon", "zoom"}}`, every key
  optional. It is only called in the enriched layout; `AggregateProvider`
  delegates it to the item's owner.

### Fixed
- Category names with an apostrophe (`"marta's tips"`) broke their menu button:
  keys were pasted raw into `onclick="selectCategory('…')"`, closing the JS
  string early, so clicking did nothing. Keys, submenu labels, filter values and
  theme names are now JSON-encoded into the handlers.
- Sitemap `<loc>` and canonical URLs are percent-encoded (and XML-escaped), so a
  category with a space or non-ASCII character in its name gets a valid URL.
- A freshly fetched card (as opposed to a prefetched one) didn't reset the tag
  style, so it could inherit the previous card's `plain`/`scientific` styling.

## [0.3.0] - 2026-09-17

### Added
- **Per-page search metadata.** The home page, `/about` and every `/<slug>`
  category landing page now carry their own `<title>`, `meta description`,
  `link rel=canonical` and `og:`/`twitter:` tags. Until now they shared one
  title and had no description or canonical at all: the active category is a
  JavaScript variable, so to a crawler every URL on a site was the same page.
  Titles and descriptions come from patterns on `MemiConfig` (`home_title`,
  `category_title`, `category_description`, with `{category}`, `{title}`,
  `{subtitle}`, `{count}` and `{description}`), and the description falls back
  to the opening of `about_html` — already written in the instance's language —
  so a game gets all of it without configuration. New module: `memi_engine.seo`.
- **`/robots.txt` and `/sitemap.xml`.** The sitemap is built from the registry
  and lists `/`, `/about` and one URL per category; a new provider appears in it
  with no edit. `robots.txt` opens the site, excludes `/api/`, and points at the
  sitemap. The category pages are reachable in the UI only by clicking a button,
  so without the sitemap a crawler found the home page and stopped.
- **`MemiConfig.html_lang`.** `<html lang>` was hardcoded `en` while most games
  are not English. Defaults to `"en"`; set it per instance.
- **`MemiConfig.site_url`** (or the `MEMI_SITE_URL` env var) to pin the origin
  used for canonical, `og:` and sitemap URLs. Unset, it comes from the request:
  the app now runs behind `ProxyFix` (one hop, proto and host only), so the URLs
  it publishes are the public HTTPS ones rather than the proxy's inner hop.
- **`MemiConfig.og_image`** for the link-preview image.

### Changed
- A category with a unique last segment is still reachable at both `/food` and
  `/culture-food`, but the pair now canonicalises to the short form and only
  that one is in the sitemap, so the two are never indexed as separate pages.
- The about page title uses `label_about` instead of a hardcoded English
  "About", and both templates share one `head.html`.

## [0.2.0] - 2026-07-29

### Added
- **Shareable category landing pages.** Opening `/<slug>` (e.g. `/food`) or
  `/?cat=<key>` starts the game with that category already selected and playing.
  Slugs are derived from the registry — a key's last `:`-segment when it is
  unique (`culture:food` → `/food`), with the full dashed key (`/culture-food`)
  always available and the sole slug for colliding segments (several `…:all`).
  A new `INITIAL_CATEGORY` template var drives `app.js` to open into it on load.
- **`MemiConfig.default_category`.** When set, the home page opens straight into
  that category (a live card) instead of the empty "pick a category" screen. An
  explicit `?cat=` / `/<slug>` still wins; an unknown default is ignored.

### Changed
- The "click to reveal" prompt now sits as a right-aligned line just above the
  card (previously plain text below it), so it reads as a caption on the image.
  The text is still `MemiConfig.label_click_to_reveal`.

## [0.1.1] - 2026-06-24

### Fixed
- `User-Agent` header is now `memi-engine/<version>` with the version read
  dynamically from package metadata instead of being hardcoded as `Memi/1.0`.
- TMDB movie and TV fetchers now send the `User-Agent` header alongside their
  `Authorization` header (previously omitted).
- Bones API fetcher now sends the `User-Agent` header (previously no headers
  were sent).

## [0.1.0] - 2026-06-23

Initial public release.

### Added
- `AggregateProvider` — an "all" category whose items, images and tags are the
  auto-derived union of its sibling providers, delegating each lookup to the
  member that owns the item; new sibling categories flow in automatically.
- `ScientificNameProvider` and the exported `SCIENTIFIC_NAMES` database — a
  category that tags items with their Latin name (bundled English default, or a
  custom per-language mapping).
- `MemiConfig.wikipedia_lang` (and the `MEMI_WIKIPEDIA_LANG` env var) to choose
  the Wikipedia language edition used by the default image / "know more" helpers.
- `register` can now be used as a class decorator (`@register`) in addition to
  `register(Provider())`.
- `/healthz` endpoint returning service status and category count.
- `py.typed` marker — the package now ships its type hints (PEP 561).
- Test suite (pytest) covering the registry, menu builder, config, providers,
  scientific names, the image helpers (mocked), and the app routes.
- Continuous integration (GitHub Actions) running ruff and pytest on
  Python 3.10–3.13.

### Changed
- `CategoryProvider` instances no longer share their class-level `items` /
  `filters` / `footers` containers, preventing accidental cross-instance
  mutation.
- Rewrote the README into a full reference with usage badges.

### Fixed
- Removed the broken `/review` route (rendered a non-existent template).
- `/api/report` no longer errors on a non-JSON request body.

### Removed
- Stopped shipping the runtime `reported_items.log` inside the package.
