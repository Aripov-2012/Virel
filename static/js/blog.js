(function () {
    document.addEventListener("click", function (event) {
        const btn = event.target.closest(".js-toggle-comments");
        if (!btn) return;
        const postId = btn.dataset.target;
        const post = document.getElementById(postId);
        if (!post) return;
        const section = post.querySelector(".comments");
        if (!section) return;
        const isHidden = section.hasAttribute("hidden");
        if (isHidden) {
            section.removeAttribute("hidden");
            post.classList.add("comments-active");
        } else {
            section.setAttribute("hidden", "");
            post.classList.remove("comments-active");
        }
    });
})();
