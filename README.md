# memi-engine

[![PyPI version](https://img.shields.io/pypi/v/memi-engine.svg)](https://pypi.org/project/memi-engine/)
[![Python versions](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://pypi.org/project/memi-engine/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

> In a world where a language model will answer almost anything in an instant, the
> part of your mind that *recalls* — that retrieves what you know on its own — gets
> little exercise. **memi** is a small counterweight: a game built on *active
> recall*. You look at an image, try to name it before revealing the answer, and
> follow the *know more* link to learn more. Each round strengthens the link
> between what you see and what you know. The answer is always one tap away — the
> point is to reach for it yourself first.

`memi-engine` lets you build your own [memi](https://memi.click) game — a
tap-to-reveal flashcard trainer — from a list of names and where to find their
images.

You define **categories** (countries, animals, monuments, movies…); the engine
gives you the responsive web UI, the menu, image fetching from Wikipedia and
friends, filters, clue mode, a **"know more" link** to each item's Wikipedia
(or source) page on reveal, theming, and a reporting system.

```bash
pip install memi-engine
```

```python
from memi_engine import CategoryProvider, MemiConfig, create_app, register


class Animals(CategoryProvider):
    key = "nature:animals"
    items = ["Lion", "Tiger", "Elephant", "Aardvark"]


register(Animals())
app = create_app(MemiConfig(title="My Memi"))

if __name__ == "__main__":
    app.run(debug=True)
```

Open <http://localhost:5000>, pick **nature → animals**, and play. Images are
resolved from Wikipedia automatically from each item's name.

## Concepts

A memi game is just a set of **category providers** registered with the engine.
Each provider declares:

- **`items`** — the list of names to guess.
- **`key`** — where the category sits in the menu (see below).
- **how to get an image** for an item (default: Wikipedia), and optionally a
  **tag** (a subtitle shown on reveal) and a **clue**.

The engine handles routing, the random game loop (`/api/random`), filtering,
prefetching, and rendering.

### Keys *are* the menu

A category `key` is a colon-separated path. The engine splits it to build a
nested menu, and **renders each segment verbatim as the on-screen label** — so
the key is also your menu copy. This is why localized games keep their keys in
the game's language:

| Key                          | Menu shown to the player        |
| ---------------------------- | ------------------------------- |
| `"space"`                    | space                           |
| `"nature:animals"`           | nature → animals                |
| `"nature:plants:flowers"`    | nature → plants → flowers       |
| `"geografia:freguesias"`     | geografia → freguesias          |

Up to four levels are supported. A child labelled `all` always sorts first.

## `CategoryProvider`

Subclass it and set at least `key` and `items`. Override the methods you need.

```python
class Monuments(CategoryProvider):
    key = "culture:monuments"
    items = ["Belém Tower", "Eiffel Tower"]
    override_name = True            # show the item name, not the article title

    def get_tag(self, item):       # subtitle on the revealed card
        return PARISHES.get(item)
```

**Attributes**

| Attribute        | Default | Meaning                                                             |
| ---------------- | ------- | ------------------------------------------------------------------ |
| `key`            | `""`    | Menu path (see above).                                             |
| `items`          | `[]`    | List of item names.                                                |
| `filters`        | `{}`    | `{filter_name: {value: [items]}}` — auto-generates filter UI.      |
| `single_select`  | `False` | Only one subcategory active at a time.                             |
| `light_bg`       | `False` | Light card background (good for logos).                            |
| `override_name`  | `False` | Use the item key as the display name, not the article title.       |
| `footers`        | `[]`    | Footer IDs (attribution) to show when this category is active.     |
| `tag_style`      | `None`  | `"plain"`, `"scientific"`, or `None` (auto-detect) — tag styling.  |

**Methods**

| Method                 | Returns                                                        |
| ---------------------- | ------------------------------------------------------------- |
| `get_image(item)`      | `{"name": ..., "image": ..., "url": ...}` or `None`. Default: Wikipedia. |
| `get_tag(item)`        | A short subtitle for the revealed card, or `None`.            |
| `get_clue(item)`       | A clue shown *before* reveal, or `None`.                      |

The optional **`url`** in the `get_image` result is the item's source page; the
engine turns it into the *"know more"* link shown on reveal (label set via
`MemiConfig.label_more`). The built-in image helpers populate it automatically —
e.g. `get_wikipedia_image` returns the Wikipedia article URL — so Wikipedia-backed
categories get the link for free.

### Scientific names

`ScientificNameProvider` tags each item with its Latin name. It ships a bundled
English database (`SCIENTIFIC_NAMES`, ~1500 species) used by default; pass your
own mapping for other languages. The tag is shown only when the Latin name
differs from the display name, in italic *scientific* style.

```python
from memi_engine import ScientificNameProvider, register

class Animals(ScientificNameProvider):
    key = "nature:animals"
    items = ["Lion", "Tiger"]      # → "Panthera leo", "Panthera tigris"

class Plantas(ScientificNameProvider):
    key = "natureza:plantas"
    items = ["Sobreiro"]
    scientific_names = {"Sobreiro": "Quercus suber"}
```

### Filters

A filter maps option values to subsets of `items`. The engine renders the filter
buttons and applies the choice via a URL parameter.

```python
class Countries(CategoryProvider):
    key = "geography:countries"
    items = ["France", "Spain", "Japan"]
    filters = {
        "continent": {"europe": ["France", "Spain"], "asia": ["Japan"]},
    }
```

## Images

`memi_engine.images` resolves item names to image URLs and caches results
in-memory. Providers call these from `get_image`:

`get_wikipedia_image`, `get_wikipedia_file_image`, `get_commons_file_image`,
`get_tmdb_image`, `get_tmdb_tv_image`, `get_fandom_image`, `get_country_shape`,
`get_album_cover`, `get_logo_image`, and more.

Some sources need configuration via environment variables:

| Variable        | Used by                         | Default                  |
| --------------- | ------------------------------- | ------------------------ |
| `TMDB_API_KEY`  | `get_tmdb_image` (movies / TV)  | _(unset — TMDB skipped)_ |
| `BONES_API_URL` | anatomy image service           | `http://127.0.0.1:8081`  |

## `MemiConfig`

Passed to `create_app`. Common fields:

| Field             | Default              | Purpose                                  |
| ----------------- | -------------------- | ---------------------------------------- |
| `title`           | `"memi"`             | Header title.                            |
| `subtitle`        | `"practise…"`        | Header subtitle.                         |
| `themes`          | 8 built-in themes    | Available colour themes.                 |
| `default_theme`   | `"light"`            | Initial theme.                           |
| `sponsor_url`     | `None`               | Sponsor link (hidden if `None`).         |
| `about_html`      | `None`               | Custom HTML for the about page.          |
| `analytics_html`  | `None`               | Analytics snippet injected on the page.  |
| `favicon_color`   | `"#b8860b"`          | Favicon background colour.               |
| `related_sites`   | `[]`                 | Sibling games to link from the about page. |
| `label_*`         | English strings      | UI labels (for localization).            |

All UI strings are `label_*` fields, so a fully localized game keeps its labels
and `about_html` in its own language while the code stays English.

### Instance static files

To serve your own logo or images, point `create_app` at a static folder; its
files take precedence over the engine's:

```python
app = create_app(config, instance_static="/path/to/static")
# served at /static/... , falling back to the engine's static files
```

## Deployment

The app is a standard WSGI Flask app. For production, install the `server`
extra and run under gunicorn:

```bash
pip install "memi-engine[server]"
gunicorn "yourgame:app"
```

Two optional data files are read from the working directory at runtime:
`excluded_items.txt` (items to hide) and `reported_items.log` (written when
players report a bad card).

## Live examples

Real games built on this engine: [memi](https://memi.click) ·
[memi portugal](https://pt.memi.click) · [memi lisboa](https://lx.memi.click) ·
[memi slovensko](https://sk.memi.click) · [memi US](https://us.memi.click).

## Development

```bash
uv sync --extra dev
pytest          # run the test suite
ruff check .    # lint
```

## License

MIT — see [LICENSE](LICENSE).
