/**
 * reels.js — автовоспроизведение, пауза, лайки для страницы Reels.
 */
(function () {
    'use strict';

    // ── Утилиты ──────────────────────────────────────────────────────────────

    function getCookie(name) {
        var val = '; ' + document.cookie;
        var parts = val.split('; ' + name + '=');
        if (parts.length === 2) return parts.pop().split(';').shift();
        return '';
    }
    var csrfToken = getCookie('csrftoken');

    // ── Autoplay через IntersectionObserver ───────────────────────────────────

    var currentVideo = null;

    var observer = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
            var item = entry.target;
            var video = item.querySelector('.reel-video');
            var hint = item.querySelector('.js-reel-play-hint');
            if (!video) return;

            if (entry.isIntersecting && entry.intersectionRatio >= 0.6) {
                // Останавливаем предыдущее видео
                if (currentVideo && currentVideo !== video) {
                    currentVideo.pause();
                    showHint(currentVideo.closest('.reel-item'));
                }
                currentVideo = video;
                video.muted = true;  // autoplay требует muted
                var playPromise = video.play();
                if (playPromise !== undefined) {
                    playPromise.then(function () {
                        hideHint(item);
                    }).catch(function () {
                        showHint(item);
                    });
                }
            } else {
                video.pause();
            }
        });
    }, { threshold: 0.6 });

    function showHint(item) {
        var hint = item && item.querySelector('.js-reel-play-hint');
        if (hint) hint.classList.add('show');
    }
    function hideHint(item) {
        var hint = item && item.querySelector('.js-reel-play-hint');
        if (hint) hint.classList.remove('show');
    }

    // ── Tap на видео: play / pause ────────────────────────────────────────────

    document.querySelectorAll('.reel-item').forEach(function (item) {
        observer.observe(item);

        var video = item.querySelector('.reel-video');
        if (!video) return;

        // Клик по видео — переключение паузы
        video.addEventListener('click', function () {
            if (video.paused) {
                video.play().then(function () { hideHint(item); }).catch(function () {});
            } else {
                video.pause();
                showHint(item);
            }
        });

        // Кнопка play-hint
        var hint = item.querySelector('.js-reel-play-hint');
        if (hint) {
            hint.addEventListener('click', function () {
                video.play().then(function () { hideHint(item); }).catch(function () {});
            });
        }
    });

    // ── AJAX: лайк рила ───────────────────────────────────────────────────────

    document.querySelectorAll('.js-reel-like-form').forEach(function (form) {
        form.addEventListener('submit', function (e) {
            e.preventDefault();
            var btn = form.querySelector('.js-reel-like-btn');
            var countEl = form.querySelector('.js-reel-likes-count');
            var url = form.action;

            fetch(url, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrfToken,
                    'X-Requested-With': 'XMLHttpRequest',
                },
            })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (!data.ok) return;
                btn.classList.toggle('active', data.liked);
                if (countEl) countEl.textContent = data.likes_count;
            })
            .catch(function () {});
        });
    });

    // ── AJAX: удаление рила ───────────────────────────────────────────────────

    document.querySelectorAll('.js-reel-delete-form').forEach(function (form) {
        form.addEventListener('submit', function (e) {
            e.preventDefault();
            if (!confirm('Удалить этот рил?')) return;

            var item = form.closest('.reel-item');
            var url = form.action;

            fetch(url, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrfToken,
                    'X-Requested-With': 'XMLHttpRequest',
                },
            })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.ok && item) {
                    item.remove();
                }
            })
            .catch(function () {});
        });
    });

}());
