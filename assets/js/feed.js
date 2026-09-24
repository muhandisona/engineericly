(function () {
    'use strict';

    var PLATFORM = JSON.parse(document.getElementById('platform').textContent || '""');
    var API = window.GALLERY_API;
    var SKELETONS = 6;
    var reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    var grid = document.getElementById('grid');
    var statusEl = document.getElementById('status');
    var sentinel = document.getElementById('sentinel');
    var bar = document.getElementById('bar');
    var profile = document.getElementById('profile');

    var page = 1;
    var hasNext = true;
    var loading = false;
    var posts = [];

    // ---------- Tiles ----------

    var PIN_SVG = '<svg width="18" height="18" viewBox="0 0 24 24" fill="#fff" stroke="#fff" stroke-width="1.5" stroke-linejoin="round"><path d="M9 3h6l-1 6 3 3v2H7v-2l3-3z"></path><path d="M12 14v7" fill="none"></path></svg>';
    var GO_SVG = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#0b1410" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M7 17L17 7"></path><path d="M8 7h9v9"></path></svg>';

    // Tiles fade and rise in as they scroll into view, staggered across each row.
    var revealer = 'IntersectionObserver' in window && !reduceMotion
        ? new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (!entry.isIntersecting) return;
                entry.target.classList.add('is-in');
                revealer.unobserve(entry.target);
            });
        }, { rootMargin: '0px 0px -40px 0px' })
        : null;

    function createTile(post, index) {
        var tile = document.createElement('button');
        tile.type = 'button';
        tile.className = 'tile';
        tile.setAttribute('aria-label', post.title);
        tile.style.setProperty('--delay', (index % 3) * 0.06 + 's');
        tile.addEventListener('click', function () {
            openSheet(post, tile);
        });

        var img = document.createElement('img');
        img.src = post.image;
        img.alt = '';
        img.loading = 'lazy';
        img.decoding = 'async';
        tile.appendChild(img);

        if (post.is_pinned) {
            var pin = document.createElement('span');
            pin.className = 'tile-pin';
            pin.setAttribute('aria-hidden', 'true');
            pin.innerHTML = PIN_SVG;
            tile.appendChild(pin);
        }

        var go = document.createElement('span');
        go.className = 'tile-go';
        go.setAttribute('aria-hidden', 'true');
        go.innerHTML = GO_SVG;
        tile.appendChild(go);

        if (revealer) {
            revealer.observe(tile);
        } else {
            tile.classList.add('is-in');
        }
        return tile;
    }

    function addSkeletons() {
        var nodes = [];
        for (var i = 0; i < SKELETONS; i++) {
            var s = document.createElement('div');
            s.className = 'tile-skeleton';
            s.setAttribute('aria-hidden', 'true');
            grid.appendChild(s);
            nodes.push(s);
        }
        return nodes;
    }

    function showStatus(message, retry) {
        statusEl.hidden = false;
        statusEl.textContent = message;
        if (retry) {
            var btn = document.createElement('button');
            btn.type = 'button';
            btn.textContent = 'Try again';
            btn.addEventListener('click', function () {
                statusEl.hidden = true;
                loadMore();
            });
            statusEl.appendChild(document.createElement('br'));
            statusEl.appendChild(btn);
        }
    }

    function loadMore() {
        if (loading || !hasNext) return;
        loading = true;
        var skeletons = addSkeletons();

        var url = API + '?page=' + page + (PLATFORM ? '&platform=' + encodeURIComponent(PLATFORM) : '');
        fetch(url)
            .then(function (res) {
                if (!res.ok) throw new Error('HTTP ' + res.status);
                return res.json();
            })
            .then(function (data) {
                skeletons.forEach(function (s) { s.remove(); });
                var start = posts.length;
                data.items.forEach(function (post, i) {
                    posts.push(post);
                    grid.appendChild(createTile(post, start + i));
                });
                hasNext = data.has_next;
                page += 1;
                if (!posts.length) showStatus('New models are on the way.');
            })
            .catch(function () {
                skeletons.forEach(function (s) { s.remove(); });
                showStatus('Could not load the models.', true);
            })
            .finally(function () {
                loading = false;
                // The sentinel may still be on screen (short page or tall phone).
                if (hasNext && isNearBottom()) loadMore();
            });
    }

    function isNearBottom() {
        return sentinel.getBoundingClientRect().top < window.innerHeight + 600;
    }

    if ('IntersectionObserver' in window) {
        new IntersectionObserver(function (entries) {
            if (entries[0].isIntersecting) loadMore();
        }, { rootMargin: '600px 0px' }).observe(sentinel);
    } else {
        window.addEventListener('scroll', function () {
            if (isNearBottom()) loadMore();
        }, { passive: true });
    }

    loadMore();

    // ---------- Header fade + compact bar ----------

    var ticking = false;
    function onScroll() {
        if (ticking) return;
        ticking = true;
        requestAnimationFrame(function () {
            var y = window.scrollY;
            if (!reduceMotion) {
                var t = Math.min(y / 180, 1);
                profile.style.opacity = String(1 - t * 0.85);
                profile.style.transform = 'translateY(' + (-24 * t) + 'px) scale(' + (1 - 0.04 * t) + ')';
            }
            var on = y > 120;
            bar.classList.toggle('is-on', on);
            bar.setAttribute('aria-hidden', on ? 'false' : 'true');
            bar.querySelectorAll('a, button').forEach(function (el) {
                el.tabIndex = on ? 0 : -1;
            });
            ticking = false;
        });
    }
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();

    // ---------- Sheet ----------

    var layer = document.getElementById('sheet-layer');
    var sheet = document.getElementById('sheet');
    var sheetImg = document.getElementById('sheet-img');
    var sheetHost = document.getElementById('sheet-host');
    var sheetTitle = document.getElementById('sheet-title');
    var sheetCta = document.getElementById('sheet-cta');
    var lastTrigger = null;
    var closeTimer = null;

    function openSheet(post, trigger) {
        clearTimeout(closeTimer);
        lastTrigger = trigger;
        sheetImg.src = post.image;
        sheetHost.textContent = post.host;
        sheetTitle.textContent = post.title;
        sheetCta.href = post.link;
        sheet.style.transform = '';
        layer.classList.remove('is-closing');
        layer.hidden = false;
        document.body.classList.add('is-locked');
        sheetCta.focus({ preventScroll: true });
    }

    function closeSheet() {
        if (layer.hidden || layer.classList.contains('is-closing')) return;
        layer.classList.add('is-closing');
        closeTimer = setTimeout(function () {
            layer.hidden = true;
            layer.classList.remove('is-closing');
            sheet.style.transform = '';
            document.body.classList.remove('is-locked');
            if (lastTrigger) lastTrigger.focus({ preventScroll: true });
        }, reduceMotion ? 0 : 220);
    }

    layer.querySelector('[data-close]').addEventListener('click', closeSheet);

    document.addEventListener('keydown', function (e) {
        if (layer.hidden) return;
        if (e.key === 'Escape') {
            closeSheet();
        } else if (e.key === 'Tab') {
            // Only the link is focusable inside the sheet, so keep focus on it.
            e.preventDefault();
            sheetCta.focus();
        }
    });

    // Drag the sheet down to dismiss it.
    var dragStart = null;
    var dragY = 0;
    sheet.addEventListener('pointerdown', function (e) {
        if (e.target.closest('a')) return;
        dragStart = e.clientY;
        dragY = 0;
        sheet.classList.add('is-dragging');
        sheet.setPointerCapture(e.pointerId);
    });
    sheet.addEventListener('pointermove', function (e) {
        if (dragStart === null) return;
        dragY = Math.max(0, e.clientY - dragStart);
        sheet.style.transform = 'translateY(' + dragY + 'px)';
    });
    function endDrag() {
        if (dragStart === null) return;
        dragStart = null;
        sheet.classList.remove('is-dragging');
        if (dragY > 90) {
            closeSheet();
        } else {
            sheet.style.transition = 'transform 0.3s cubic-bezier(0.16, 1, 0.3, 1)';
            sheet.style.transform = '';
            setTimeout(function () { sheet.style.transition = ''; }, 300);
        }
    }
    sheet.addEventListener('pointerup', endDrag);
    sheet.addEventListener('pointercancel', endDrag);
})();
