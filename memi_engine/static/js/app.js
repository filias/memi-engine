let selectedCategories = [];
let revealed = false;
let loaded = false;
let clueMode = false;
let currentName = '';
let currentTag = '';
let currentRevealImage = '';
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
    for (const sub of items) {
        const btn = document.createElement('button');
        btn.textContent = sub.label;
        if (sub.children) {
            btn.onclick = function() {
                menuStack.push({items, group: currentGroup});
                selectedCategories = [];
                seenItems = [];
                renderSubmenu(sub.children, sub.label);
            };
        } else {
            btn.dataset.key = sub.key;
            btn.onclick = function() { toggleSubcategory(sub.key, this); };
        }
        buttons.appendChild(btn);
    }

    main.style.display = 'none';
    submenu.style.display = 'flex';
}

function toggleSubmenu(parent) {
    selectedCategories = [];
    seenItems = [];
    menuStack = [];
    renderSubmenu(subcategories[parent], parent);
}

function toggleSubcategory(key, btn) {
    const isSingleSelect = singleSelectGroups.includes(currentGroup);
    const wasEmpty = selectedCategories.length === 0;
    const idx = selectedCategories.indexOf(key);

    if (isSingleSelect) {
        document.querySelectorAll('#submenu-buttons button').forEach(b => b.classList.remove('active'));
        if (idx !== -1) {
            selectedCategories = [];
            return;
        }
        selectedCategories = [key];
        btn.classList.add('active');
    } else {
        if (idx === -1) {
            selectedCategories.push(key);
            btn.classList.add('active');
        } else {
            selectedCategories.splice(idx, 1);
            btn.classList.remove('active');
        }
    }

    updateFilters();
    if (selectedCategories.length > 0 && (wasEmpty || isSingleSelect)) {
        loadNew();
    }
}

function toggleClueMode() {
    clueMode = !clueMode;
    const btn = document.getElementById('clue-toggle');
    btn.textContent = clueMode ? 'clues: on' : 'clues: off';
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

function updateFilters() {
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
    if (seenItems.length > 0) {
        url += `&seen=${encodeURIComponent(seenItems.join(','))}`;
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
    document.getElementById('reveal-image').style.display = 'none';
    status.style.display = 'block';
    status.textContent = 'loading...';
    status.className = 'loading';
    hint.textContent = '';
    const reportBtn = document.getElementById('report-btn');
    reportBtn.style.display = 'none';
    reportBtn.textContent = 'report';
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
        currentName = data.name;
        currentTag = data.tag || '';
        currentRevealImage = data.reveal_image || '';
        currentItem = data.item || data.name;
        currentCats = selectedCategories.join(',');
        lettersRevealed = 0;
        loaded = true;
        hint.textContent = 'click the image to reveal the answer';
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
            currentName = data.name;
            currentTag = data.tag || '';
            currentRevealImage = data.reveal_image || '';
            currentItem = data.item || data.name;
            currentCats = selectedCategories.join(',');
            lettersRevealed = 0;
            loaded = true;
            hint.textContent = 'click the image to reveal the answer';
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
    status.textContent = 'all done! click to start over';
    status.className = 'loading';
    loaded = false;
}

function showTag(tagEl) {
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
    btn.textContent = 'reported';
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
        document.getElementById('hint').textContent = 'click again for a new one';
        document.getElementById('clue-area').style.display = 'none';
        if (currentTag) {
            showTag(document.getElementById('tag'));
        }
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
