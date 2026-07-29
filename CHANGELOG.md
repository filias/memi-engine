# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
