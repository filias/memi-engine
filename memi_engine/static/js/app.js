let selectedCategories = [];
let revealed = false;
let loaded = false;
let clueMode = false;
let currentName = '';
let currentTag = '';
let currentTagStyle = '';
let currentMoreUrl = '';
let currentRevealImage = '';
let currentDetails = null;
let currentAudio = null;
let playingAudio = null;
let currentItem = '';
let currentCats = '';
let lettersRevealed = 0;
let seenItems = [];
let prefetchedData = null;
let prefetchedImage = null;

// Generic filter state: {filterName: [selectedValues]}
let activeFilters = {};

const subcategories = JSON.parse(document.getElementById('subcategories-data').textContent);

function selectCategory(cat) {
    selectedCategories = [cat];
    document.querySelectorAll('#main-categories button').forEach(b => {
        if (b.classList.contains('back-btn')) return;
        b.classList.remove('active');
    });
    updateFilters();
    loadNew();
}

const singleSelectGroups = ['countries', 'movies', 'paintings', 'us states', 'sports'];
let currentGroup = null;
let menuStack = [];

function renderSubmenu(items, group) {
    const main = document.getElementById('main-categories');
    const submenu = document.getElementById('submenu');
    const buttons = document.getElementById('submenu-buttons');
    currentGroup = group;

    buttons.innerHTML = '';
    const leafKeys = [];
    for (const sub of items) {
        const btn = document.createElement('button');
        btn.textContent = sub.text || sub.label;
        // The key segment, for deep links: what's shown may be a translation.
        btn.dataset.label = sub.label;
        if (sub.children) {
            btn.onclick = function() {
                menuStack.push({items, group: currentGroup});
                selectedCategories = [];
                seenItems = [];
                renderSubmenu(sub.children, sub.label);
                startSubmenuDefault(sub.children);
            };
        } else {
            btn.dataset.key = sub.key;
            btn.onclick = function() { selectSubcategory(sub.key, this); };
            leafKeys.push(sub.key);
        }
        buttons.appendChild(btn);
    }

    // "all": play every category of this level together. Not for one-at-a-time
    // groups, not for a single category, and not when the game already has its
    // own "…:all" category here.
    const ownAll = leafKeys.some(k => k.split(':').pop() === 'all');
    if (leafKeys.length > 1 && !ownAll && !singleSelectGroups.includes(group)) {
        const allBtn = document.createElement('button');
        allBtn.className = 'all-btn';
        allBtn.textContent = LABELS.all;
        allBtn.onclick = function() { selectAllSubcategories(leafKeys, this); };
        buttons.appendChild(allBtn);
    }

    main.style.display = 'none';
    submenu.style.display = 'flex';
}

function toggleSubmenu(parent) {
    selectedCategories = [];
    seenItems = [];
    menuStack = [];
    syncUrl();
    renderSubmenu(subcategories[parent], parent);
    startSubmenuDefault(subcategories[parent]);
}

// A submenu can name the category it opens on (a provider's submenu_default):
// opening it then starts that one instead of waiting for a choice. Skipped
// while a shared link opens its own category, so it doesn't load twice.
let openingInitialCategory = false;

function startSubmenuDefault(items) {
    if (openingInitialCategory) return;
    const sub = items.find(s => s.default && s.key);
    if (!sub) return;
    const btn = document.querySelector('#submenu-buttons [data-key="' + CSS.escape(sub.key) + '"]');
    if (btn) btn.click();
}

function markSubmenuActive(btn) {
    document.querySelectorAll('#submenu-buttons button').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
}

// A tap switches to that category: one at a time, like the top-level buttons.
// Tapping the one already playing changes nothing.
function selectSubcategory(key, btn) {
    if (selectedCategories.length === 1 && selectedCategories[0] === key) return;
    selectedCategories = [key];
    markSubmenuActive(btn);
    updateFilters();
    loadNew();
}

function selectAllSubcategories(keys, btn) {
    const same = selectedCategories.length === keys.length &&
        keys.every(k => selectedCategories.includes(k));
    if (same) return;
    selectedCategories = keys.slice();
    markSubmenuActive(btn);
    updateFilters();
    loadNew();
}

function toggleClueMode() {
    clueMode = !clueMode;
    const btn = document.getElementById('clue-toggle');
    btn.textContent = clueMode ? LABELS.cluesOn : LABELS.cluesOff;
    btn.classList.toggle('active', clueMode);
    document.getElementById('clue-area').style.display = (clueMode && loaded && !revealed) ? 'block' : 'none';
}

function revealLetter() {
    if (lettersRevealed >= currentName.length) return;
    lettersRevealed++;
    updateClueDisplay();
}

function updateClueDisplay() {
    let display = '';
    for (let i = 0; i < currentName.length; i++) {
        if (currentName[i] === ' ') {
            display += '  ';
        } else if (i < lettersRevealed) {
            display += currentName[i];
        } else {
            display += '_';
        }
    }
    document.getElementById('clue-letters').textContent = display;
}

function closeSubmenu() {
    selectedCategories = [];
    seenItems = [];
    updateFilters();
    if (menuStack.length > 0) {
        const prev = menuStack.pop();
        renderSubmenu(prev.items, prev.group);
    } else {
        document.getElementById('main-categories').style.display = 'flex';
        document.getElementById('submenu').style.display = 'none';
    }
}

// --- Generic filter system ---

// Keep the address bar on the shareable URL of what's being played: /<slug>
// while exactly one category is selected, / otherwise. replaceState, so moving
// between categories doesn't pile up back-button entries.
function syncUrl() {
    if (typeof CATEGORY_SLUGS === 'undefined' || !window.history.replaceState) return;
    const slug = selectedCategories.length === 1 ? CATEGORY_SLUGS[selectedCategories[0]] : null;
    const prefix = typeof PATH_PREFIX === 'string' ? PATH_PREFIX : '';
    const path = prefix + (slug ? '/' + encodeURIComponent(slug) : '/');
    if (window.location.pathname !== path || window.location.search) {
        window.history.replaceState(null, '', path);
    }
}

function updateFilters() {
    syncUrl();
    for (const [filterName, filterInfo] of Object.entries(FILTER_CONFIG)) {
        const el = document.getElementById(filterName + '-filter');
        if (!el) continue;
        const show = selectedCategories.some(c => filterInfo.categories.includes(c));
        el.style.display = show ? 'flex' : 'none';
    }
}

function toggleFilter(filterName, value, btn) {
    if (!activeFilters[filterName]) activeFilters[filterName] = [];
    const arr = activeFilters[filterName];
    const idx = arr.indexOf(value);
    if (idx === -1) {
        arr.push(value);
        btn.classList.add('active');
    } else {
        arr.splice(idx, 1);
        btn.classList.remove('active');
    }
    seenItems = [];
    if (loaded || selectedCategories.length > 0) loadNew();
}

function buildFetchUrl() {
    const cats = selectedCategories.join(',');
    let url = `/api/random?cats=${encodeURIComponent(cats)}`;
    if (typeof GAME_LANG === 'string' && GAME_LANG) {
        url += `&lang=${encodeURIComponent(GAME_LANG)}`;
    }
    // One seen= per item: names can contain commas ("Pantheon, Rome").
    for (const item of seenItems) {
        url += `&seen=${encodeURIComponent(item)}`;
    }
    for (const [filterName, values] of Object.entries(activeFilters)) {
        if (values.length > 0) {
            url += `&${filterName}=${encodeURIComponent(values.join(','))}`;
        }
    }
    return url;
}

// --- Footer management ---

function updateFooters(data) {
    document.querySelectorAll('footer[id$="-footer"]').forEach(f => {
        if (f.id !== 'wikipedia-footer') f.style.display = 'none';
    });
    if (data && data.footers) {
        for (const fid of data.footers) {
            const el = document.getElementById(fid + '-footer');
            if (el) el.style.display = 'block';
        }
    }
}

// --- Load & display ---

async function loadNew() {
    if (selectedCategories.length === 0) return;

    const card = document.getElementById('card');
    const image = document.getElementById('image');
    const clue = document.getElementById('clue');
    const answer = document.getElementById('answer');
    const status = document.getElementById('status');
    const hint = document.getElementById('hint');
    const tag = document.getElementById('tag');

    card.classList.remove('revealed');
    card.classList.remove('light-bg');
    image.style.display = 'none';
    clue.style.display = 'none';
    clue.textContent = '';
    tag.style.display = 'none';
    tag.textContent = '';
    const revealHint = document.getElementById('reveal-hint');
    if (revealHint) revealHint.textContent = '';
    const moreLink = document.getElementById('more-link');
    if (moreLink) { moreLink.style.display = 'none'; moreLink.href = ''; }
    hideDetails();
    stopSpeaking();
    document.getElementById('speak-btn').hidden = true;
    document.getElementById('reveal-image').style.display = 'none';
    const doneArt2 = document.getElementById('done-art');
    if (doneArt2) doneArt2.style.display = 'none';
    status.style.display = 'block';
    status.textContent = LABELS.loading;
    status.className = 'loading';
    hint.textContent = '';
    const reportBtn = document.getElementById('report-btn');
    reportBtn.style.display = 'none';
    reportBtn.textContent = LABELS.report;
    reportBtn.disabled = false;
    reportBtn.style.color = '';
    reportBtn.style.borderColor = '';
    revealed = false;
    loaded = false;

    updateFilters();

    if (prefetchedData && prefetchedImage && currentCats === selectedCategories.join(',')) {
        const data = prefetchedData;
        image.src = prefetchedImage.src;
        prefetchedData = null;
        prefetchedImage = null;

        seenItems.push(data.item || data.name);
        status.style.display = 'none';
        image.style.display = 'block';
        reportBtn.style.display = 'inline-block';
        if (data.light_bg) card.classList.add('light-bg');
        clue.style.display = 'none';
        if (data.clue) { clue.textContent = data.clue; clue.style.display = 'block'; }
        setCurrent(data);
        lettersRevealed = 0;
        loaded = true;
        hint.textContent = '';
        if (revealHint) revealHint.textContent = LABELS.clickToReveal;
        updateFooters(data);

        const clueArea = document.getElementById('clue-area');
        if (clueMode) { updateClueDisplay(); clueArea.style.display = 'block'; }
        else { clueArea.style.display = 'none'; }
        return;
    }

    const maxRetries = 5;
    for (let attempt = 0; attempt < maxRetries; attempt++) {
        try {
            const resp = await fetch(buildFetchUrl());
            const data = await resp.json();

            if (data.error) continue;

            const loaded_ok = await new Promise(resolve => {
                image.onload = () => resolve(true);
                image.onerror = () => resolve(false);
                image.src = data.image;
            });

            if (!loaded_ok) continue;

            seenItems.push(data.item || data.name);
            status.style.display = 'none';
            image.style.display = 'block';
            reportBtn.style.display = 'inline-block';
            if (data.light_bg) card.classList.add('light-bg');
            clue.style.display = 'none';
            if (data.clue) {
                clue.textContent = data.clue;
                clue.style.display = 'block';
            }
            setCurrent(data);
            lettersRevealed = 0;
            loaded = true;
            hint.textContent = '';
            if (revealHint) revealHint.textContent = LABELS.clickToReveal;
            updateFooters(data);

            const clueArea = document.getElementById('clue-area');
            if (clueMode) {
                updateClueDisplay();
                clueArea.style.display = 'block';
            } else {
                clueArea.style.display = 'none';
            }

            return;
        } catch (e) {
            continue;
        }
    }
    seenItems = [];
    loaded = false;
    const doneArt = document.getElementById('done-art');
    if (doneArt) {
        status.style.display = 'none';
        doneArt.style.display = 'flex';
        hint.textContent = LABELS.allDone;
    } else {
        status.textContent = LABELS.allDone;
        status.className = 'loading';
    }
}

// Remember the loaded card's answer-side data until it is revealed. Both load
// paths (prefetched and fetched) go through here so they can't drift apart.
function setCurrent(data) {
    currentName = data.name;
    currentTag = data.tag || '';
    currentTagStyle = data.tag_style || '';
    currentMoreUrl = data.url || '';
    currentRevealImage = data.reveal_image || '';
    currentDetails = data.details || null;
    currentAudio = data.audio || null;
    currentItem = data.item || data.name;
    currentCats = selectedCategories.join(',');
    // Audio that is part of the question (hear it, then answer) is playable
    // before the reveal; otherwise the button waits for the answer.
    document.getElementById('speak-btn').hidden =
        !(currentAudio && currentAudio.before_reveal && canSpeak(currentAudio));
}

// --- Details panel (layout="enriched" only; absent from the classic page) ---

function hideDetails() {
    const panel = document.getElementById('details');
    if (!panel) return;
    panel.hidden = true;
    // Drop the map iframe so a hidden panel never keeps loading tiles.
    document.getElementById('details-map').innerHTML = '';
}

// OpenStreetMap embed centred on lat/lon. The embed takes a bounding box, so
// derive one from the zoom level and the map box's size (Web Mercator: the
// world is 256 * 2^zoom px wide, and a degree of latitude is 1/cos(lat) taller).
function osmEmbedUrl(lat, lon, zoom, width, height) {
    const degPerPx = 360 / (256 * Math.pow(2, zoom));
    const dLon = (degPerPx * width) / 2;
    const dLat = (degPerPx * height * Math.cos(lat * Math.PI / 180)) / 2;
    const bbox = [lon - dLon, lat - dLat, lon + dLon, lat + dLat].map(n => n.toFixed(6)).join(',');
    return 'https://www.openstreetmap.org/export/embed.html?bbox=' + bbox +
        '&layer=mapnik&marker=' + lat + ',' + lon;
}

function showDetails(details) {
    const panel = document.getElementById('details');
    if (!panel || !details) return;
    // Headed by the card's answer; the area (if any) sits underneath it.
    document.getElementById('details-title').textContent = currentName;
    const area = document.getElementById('details-area');
    const text = document.getElementById('details-text');
    const map = document.getElementById('details-map');
    const mapLink = document.getElementById('details-map-link');

    area.hidden = !(details.area && details.area.name);
    if (!area.hidden) {
        area.textContent = details.area.name;
        if (details.area.url) area.href = details.area.url;
        else area.removeAttribute('href');
    }

    text.hidden = !details.text;
    text.textContent = details.text || '';

    const m = details.map;
    const hasMap = m && typeof m.lat === 'number' && typeof m.lon === 'number';
    map.hidden = mapLink.hidden = !hasMap;
    // Show the panel before sizing the map so its box has real dimensions.
    panel.hidden = area.hidden && text.hidden && !hasMap;
    if (hasMap) {
        const zoom = m.zoom || 17;
        const iframe = document.createElement('iframe');
        iframe.title = details.area && details.area.name ? details.area.name : 'map';
        iframe.loading = 'lazy';
        iframe.src = osmEmbedUrl(m.lat, m.lon, zoom, map.clientWidth || 320, map.clientHeight || 240);
        map.innerHTML = '';
        map.appendChild(iframe);
        mapLink.href = 'https://www.openstreetmap.org/?mlat=' + m.lat + '&mlon=' + m.lon +
            '#map=' + zoom + '/' + m.lat + '/' + m.lon;
    }
}

// --- Speaker button: a recording, or the browser's own voice as fallback ---

const synth = window.speechSynthesis || null;
// Chrome fills the voice list asynchronously; asking once warms it up so the
// first tap already finds a matching voice.
if (synth) synth.getVoices();

function canSpeak(audio) {
    return !!audio && (!!audio.src || (!!synth && !!audio.text));
}

function stopSpeaking() {
    if (playingAudio) { playingAudio.pause(); playingAudio = null; }
    if (synth) synth.cancel();
}

function speakText(audio) {
    if (!synth || !audio.text) return;
    synth.cancel();
    const utterance = new SpeechSynthesisUtterance(audio.text);
    if (audio.lang) {
        utterance.lang = audio.lang;
        // Prefer a voice for the language itself, so a phone set to English
        // doesn't read Polish with English sounds.
        const want = audio.lang.toLowerCase().split('-')[0];
        const voice = synth.getVoices().find(v => v.lang.toLowerCase().replace('_', '-').split('-')[0] === want);
        if (voice) utterance.voice = voice;
    }
    synth.speak(utterance);
}

function speak(event) {
    // The button sits on the card, whose own click means "next card".
    if (event) event.stopPropagation();
    const audio = currentAudio;
    if (!audio) return;
    stopSpeaking();
    if (!audio.src) { speakText(audio); return; }
    const player = new Audio(audio.src);
    playingAudio = player;
    let fellBack = false;
    const fallBack = () => {
        if (fellBack || playingAudio !== player) return;
        fellBack = true;
        speakText(audio);
    };
    player.onerror = fallBack;
    player.play().catch(fallBack);
}

function showTag(tagEl) {
    if (currentTagStyle === 'plain') {
        tagEl.textContent = currentTag.replace(/[,\s]+$/, '');
        tagEl.style.display = 'block';
        return;
    }
    if (currentTagStyle === 'scientific') {
        tagEl.innerHTML = '<em class="tag-dates">' + currentTag + '</em>';
        tagEl.style.display = 'block';
        return;
    }
    const dateMatch = currentTag.match(/^(.*?)(\d{3,4}[–—-]?\d{0,4})\s*$/);
    const sciMatch = currentTag.match(/^[A-Z][a-z]+(\s[a-z]+)?$/);
    if (dateMatch && dateMatch[1].trim()) {
        const namePart = dateMatch[1].trim().replace(/[,\s]+$/, '');
        tagEl.innerHTML = namePart + ', <span class="tag-dates">' + dateMatch[2] + '</span>';
    } else if (dateMatch) {
        tagEl.textContent = dateMatch[2];
    } else if (sciMatch) {
        tagEl.innerHTML = '<em class="tag-dates">' + currentTag + '</em>';
    } else {
        tagEl.textContent = currentTag.replace(/[,\s]+$/, '');
    }
    tagEl.style.display = 'block';
}

async function reportItem() {
    const btn = document.getElementById('report-btn');
    btn.textContent = LABELS.reported;
    btn.disabled = true;
    btn.style.color = 'var(--accent)';
    btn.style.borderColor = 'var(--accent)';
    try {
        await fetch('/api/report', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({item: currentItem, cats: currentCats}),
        });
    } catch (e) {}
}

async function prefetchNext() {
    if (selectedCategories.length === 0) return;
    prefetchedData = null;
    prefetchedImage = null;
    try {
        const resp = await fetch(buildFetchUrl());
        const data = await resp.json();
        if (data.error) return;
        const img = new Image();
        const ok = await new Promise(resolve => {
            img.onload = () => resolve(true);
            img.onerror = () => resolve(false);
            img.src = data.image;
        });
        if (ok) {
            prefetchedData = data;
            prefetchedImage = img;
        }
    } catch (e) {}
}

function handleClick() {
    if (!loaded && selectedCategories.length > 0) {
        loadNew();
        return;
    }
    if (!loaded) return;
    if (!revealed) {
        document.getElementById('answer').textContent = currentName;
        document.getElementById('card').classList.add('revealed');
        document.getElementById('hint').textContent = LABELS.clickForNew;
        document.getElementById('clue-area').style.display = 'none';
        const revealHintEl = document.getElementById('reveal-hint');
        if (revealHintEl) revealHintEl.textContent = '';
        if (currentTag) {
            showTag(document.getElementById('tag'));
        }
        if (currentMoreUrl) {
            const moreLink = document.getElementById('more-link');
            moreLink.href = currentMoreUrl;
            moreLink.style.display = 'inline-block';
        }
        if (currentDetails) {
            showDetails(currentDetails);
        }
        document.getElementById('speak-btn').hidden = !canSpeak(currentAudio);
        if (currentRevealImage) {
            const revealImg = document.getElementById('reveal-image');
            revealImg.src = currentRevealImage;
            revealImg.style.display = 'block';
        }
        revealed = true;
        prefetchNext();
    } else if (selectedCategories.length > 0) {
        loadNew();
    }
}

// --- Deep-link: open straight into a category from a shareable URL ---
// The server resolves /<slug> or ?cat=<key> to a category key and injects it as
// INITIAL_CATEGORY. We drive the real menu buttons so the selected state and the
// game load exactly as if the user had clicked through.
function startInitialCategory(key) {
    openingInitialCategory = true;
    try {
        clickThroughTo(key);
    } finally {
        openingInitialCategory = false;
    }
}

function clickThroughTo(key) {
    const parts = key.split(':');
    const top = Array.prototype.slice
        .call(document.querySelectorAll('#main-categories button'))
        .find(b => b.dataset.label === parts[0]);
    if (!top) return;
    top.click();  // top-level: selects & loads; parent: opens its submenu
    // Walk any intermediate group levels, then click the leaf subcategory.
    for (let i = 1; i < parts.length - 1; i++) {
        const group = Array.prototype.slice
            .call(document.querySelectorAll('#submenu-buttons button'))
            .find(b => b.dataset.label === parts[i] && !b.dataset.key);
        if (group) group.click();
    }
    if (parts.length > 1) {
        const leaf = document.querySelector('#submenu-buttons [data-key="' + key + '"]');
        if (leaf) leaf.click();
    }
}

if (typeof INITIAL_CATEGORY !== 'undefined' && INITIAL_CATEGORY) {
    startInitialCategory(INITIAL_CATEGORY);
}
