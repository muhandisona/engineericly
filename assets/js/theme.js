// Light/dark toggle. With no saved choice the page follows the phone's setting.
(function () {
    var root = document.documentElement;
    var prefersLight = window.matchMedia('(prefers-color-scheme: light)');

    function currentTheme() {
        return root.dataset.theme || (prefersLight.matches ? 'light' : 'dark');
    }

    document.querySelectorAll('[data-theme-toggle]').forEach(function (btn) {
        btn.addEventListener('click', function () {
            var next = currentTheme() === 'light' ? 'dark' : 'light';
            root.dataset.theme = next;
            try {
                localStorage.setItem('theme', next);
            } catch (e) {}
        });
    });
})();
