# memi-engine

Engine for building [memi](https://memi.click) memory card game instances.

Create your own memi game with custom categories — countries, animals, brands, or anything else with images on Wikipedia.

## Quick start

```bash
pip install memi-engine
```

```python
from memi_engine import CategoryProvider, MemiConfig, create_app, register

class MyCategory(CategoryProvider):
    key = "my:category"
    items = ["Lion", "Tiger", "Elephant"]

register(MyCategory())

app = create_app(MemiConfig(title="My Memi"))

if __name__ == "__main__":
    app.run()
```

## Features

- Configurable themes, title, sponsor link, analytics
- Generic filter system (difficulty, regions, classes, etc.)
- Image fetching from Wikipedia, TMDB, Fandom, Wikimedia Commons
- Scientific names database for animals and plants
- Clue mode, reporting system, prefetching
- Mobile-friendly responsive design

## License

MIT
