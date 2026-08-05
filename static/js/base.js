(function () {
    // Hide header when scrolling down, show when scrolling up
    (function () {
        var header = document.querySelector('.header');
        if (!header) return;
        var last = window.scrollY || 0;
        var threshold = 10; // minimal delta to react
        window.addEventListener('scroll', function () {
            var current = window.scrollY || 0;
            if (Math.abs(current - last) < threshold) return;
            if (current > last && current > 80) {
                header.classList.add('header--hidden');
            } else if (current < last) {
                header.classList.remove('header--hidden');
            }
            last = current;
        }, { passive: true });
    })();

    const overlay = document.getElementById("mobileOverlay");
    const openBtn = document.getElementById("menuToggle");
    const closeBtn = document.getElementById("menuClose");
    if (openBtn && overlay) {
        openBtn.addEventListener("click", function () {
            overlay.classList.add("active");
        });
    }
    if (closeBtn && overlay) {
        closeBtn.addEventListener("click", function () {
            overlay.classList.remove("active");
        });
    }
    if (overlay) {
        overlay.addEventListener("click", function (e) {
            if (e.target === overlay) {
                overlay.classList.remove("active");
            }
        });
    }
    document.querySelectorAll(".like-button").forEach(function (btn) {
        btn.addEventListener("click", function () {
            btn.classList.add("pulse");
            setTimeout(function () { btn.classList.remove("pulse"); }, 220);
        });
    });
    document.querySelectorAll(".lazy-media").forEach(function (media) {
        media.addEventListener("load", function () {
            const w = media.closest(".media-wrap");
            if (w) w.classList.remove("loading");
        });
    });
})();

// Dock interactions: quick search submit on enter and small haptics for dock buttons
(function () {
    document.addEventListener('click', function (e) {
        var dockBtn = e.target.closest('.dock-btn');
        if (!dockBtn) return;
        dockBtn.classList.add('dock-press');
        setTimeout(function () { dockBtn.classList.remove('dock-press'); }, 180);
    });

    var dockSearch = document.querySelector('.dock-search');
    if (dockSearch) {
        dockSearch.addEventListener('submit', function (e) {
            // allow normal submit (navigates to search results)
        });
    }
})();

(function () {
    function escapeHtml(value) {
        return String(value)
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll('"', "&quot;")
            .replaceAll("'", "&#39;");
    }

    function showToast(message, type) {
        const wrap = document.getElementById("toastWrap");
        if (!wrap) return;
        const toast = document.createElement("div");
        toast.className = "toast " + (type || "success");
        toast.textContent = message;
        wrap.appendChild(toast);
        requestAnimationFrame(function () {
            toast.classList.add("show");
        });
        setTimeout(function () {
            toast.classList.remove("show");
            setTimeout(function () {
                toast.remove();
            }, 240);
        }, 2200);
    }

    async function sendForm(form) {
        const response = await fetch(form.action, {
            method: "POST",
            headers: { "X-Requested-With": "XMLHttpRequest" },
            body: new FormData(form),
            credentials: "same-origin"
        });
        if (!response.ok) {
            const payload = await response.json().catch(function () { return {}; });
            throw new Error(payload.error || "Ошибка запроса");
        }
        return response.json();
    }

    document.addEventListener("submit", async function (event) {
        const form = event.target;
        if (!(form instanceof HTMLFormElement)) return;

        if (form.classList.contains("js-post-like-form") || form.classList.contains("js-comment-like-form")) {
            event.preventDefault();
            try {
                const data = await sendForm(form);
                const button = form.querySelector(".js-like-btn");
                const count = form.querySelector(".count");
                if (button && typeof data.liked === "boolean") button.classList.toggle("active", data.liked);
                if (count && typeof data.likes_count === "number") count.textContent = String(data.likes_count);
                showToast(data.liked ? "Пост лайкнут" : "Лайк убран", "success");
            } catch (err) {
                console.error(err);
                showToast(err.message || "Ошибка лайка", "error");
            }
            return;
        }

        if (form.classList.contains("js-save-form")) {
            event.preventDefault();
            try {
                const data = await sendForm(form);
                const button = form.querySelector(".js-save-btn");
                const label = form.querySelector(".label");
                if (button && typeof data.saved === "boolean") {
                    button.classList.toggle("active", data.saved);
                    const saveLabel = button.dataset.saveLabel || "Сохранить";
                    const unsaveLabel = button.dataset.unsaveLabel || "Сохранено";
                    if (label) label.textContent = data.saved ? unsaveLabel : saveLabel;
                }
                showToast(data.saved ? "Пост сохранён" : "Пост убран из сохранённых", "success");
            } catch (err) {
                console.error(err);
                showToast(err.message || "Ошибка сохранения", "error");
            }
            return;
        }

        if (form.classList.contains("js-subscription-form")) {
            event.preventDefault();
            try {
                const data = await sendForm(form);
                const button = form.querySelector(".js-subscription-btn");
                const followersCount = document.querySelector(".js-followers-count");
                if (button && typeof data.is_subscribed === "boolean") {
                    const subscribeLabel = button.dataset.subscribeLabel || "Подписаться";
                    const unsubscribeLabel = button.dataset.unsubscribeLabel || "Отписаться";
                    button.textContent = data.is_subscribed ? unsubscribeLabel : subscribeLabel;
                    button.classList.toggle("btn-secondary", data.is_subscribed);
                }
                if (followersCount && typeof data.followers_count === "number") {
                    followersCount.textContent = String(data.followers_count);
                }
                showToast(data.is_subscribed ? "Подписка оформлена" : "Вы отписались", "success");
            } catch (err) {
                console.error(err);
                showToast(err.message || "Ошибка подписки", "error");
            }
            return;
        }

        if (form.classList.contains("js-add-comment-form")) {
            event.preventDefault();
            const textarea = form.querySelector("textarea[name='text']");
            const text = textarea ? textarea.value.trim() : "";
            if (!text) {
                showToast("Введите текст комментария", "error");
                return;
            }
            try {
                const data = await sendForm(form);
                if (!data.comment) return;
                const commentsSection = form.closest(".comments");
                if (!commentsSection) return;
                const list = commentsSection.querySelector(".js-comments-list");
                if (!list) return;
                const empty = commentsSection.querySelector(".js-comments-empty");
                if (empty) empty.remove();

                const item = document.createElement("div");
                const csrfInput = form.querySelector("input[name='csrfmiddlewaretoken']");
                const csrfToken = csrfInput ? csrfInput.value : "";
                item.className = "comment";
                item.dataset.commentId = String(data.comment.id);
                item.innerHTML = `
                    <div class="comment-header">
                        <span class="comment-author">
                            <a href="${escapeHtml(data.comment.profile_url)}">${escapeHtml(data.comment.author)}</a>
                        </span>
                        <span class="comment-date">${escapeHtml(data.comment.created_at)}</span>
                    </div>
                    <p class="comment-text">${escapeHtml(data.comment.text)}</p>
                    <div class="post-actions">
                        <form method="post" action="${escapeHtml(data.comment.like_url)}" class="js-comment-like-form">
                            <input type="hidden" name="csrfmiddlewaretoken" value="${escapeHtml(csrfToken)}">
                            <button type="submit" class="btn-like like-button js-like-btn"><span class="icon">♥</span> <span class="count">${data.comment.likes_count}</span></button>
                        </form>
                    </div>
                `;
                list.appendChild(item);
                if (textarea) textarea.value = "";
                showToast("Комментарий добавлен", "success");
            } catch (err) {
                console.error(err);
                showToast(err.message || "Ошибка комментария", "error");
            }
        }

    });
})();

(function () {
    document.addEventListener("click", function (event) {
        const btn = event.target.closest(".post-content-toggle");
        if (!btn) return;
        const container = btn.closest(".post-content");
        if (!container) return;
        const shortText = container.querySelector(".post-content-short");
        const fullText = container.querySelector(".post-content-full");
        if (!shortText || !fullText) return;
        const isExpanded = fullText.classList.contains("is-visible");

        if (isExpanded) {
            fullText.classList.remove("is-visible");
            shortText.classList.remove("is-hidden");
            btn.textContent = "Показать полностью";
        } else {
            fullText.classList.add("is-visible");
            shortText.classList.add("is-hidden");
            btn.textContent = "Свернуть";
        }
    });
})();

