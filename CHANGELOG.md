# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
