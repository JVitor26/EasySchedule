(function () {
    const STORAGE_KEY = "easyschedule-theme";
    const THEMES = {
        dark: "dark",
        light: "light",
        sage: "light",
        midnight: "dark",
    };

    function normalizeTheme(theme) {
        return Object.prototype.hasOwnProperty.call(THEMES, theme) ? theme : "dark";
    }

    function applyTheme(theme, options = {}) {
        const resolvedTheme = normalizeTheme(theme);
        document.documentElement.dataset.theme = resolvedTheme;
        document.documentElement.style.colorScheme = THEMES[resolvedTheme];

        if (!options.skipStorage) {
            window.localStorage.setItem(STORAGE_KEY, resolvedTheme);
        }

        const picker = document.getElementById("themePicker");
        if (picker && picker.value !== resolvedTheme) {
            picker.value = resolvedTheme;
        }

        document.dispatchEvent(new CustomEvent("themechange", {
            detail: {
                theme: resolvedTheme,
            },
        }));
    }

    function getSavedTheme() {
        return normalizeTheme(window.localStorage.getItem(STORAGE_KEY) || "dark");
    }

    document.addEventListener("DOMContentLoaded", () => {
        const picker = document.getElementById("themePicker");
        const initialTheme = normalizeTheme(document.documentElement.dataset.theme || getSavedTheme());

        applyTheme(initialTheme, { skipStorage: true });

        if (picker) {
            picker.addEventListener("change", (event) => {
                applyTheme(event.target.value);
            });
        }
    });

    window.EasyScheduleTheme = {
        applyTheme,
        getTheme() {
            return normalizeTheme(document.documentElement.dataset.theme || getSavedTheme());
        },
    };
})();
