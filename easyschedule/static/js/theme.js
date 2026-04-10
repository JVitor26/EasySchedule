(function () {
    const STORAGE_KEY = "easyschedule-theme";
    const THEMES = {
        dark: "dark",
        light: "light",
        sage: "light",
        midnight: "dark",
    };
    const LIGHT_THEMES = new Set(["light", "sage"]);
    const DEFAULT_PRIMARY = "#22c55e";
    const DEFAULT_SECONDARY = "#34d399";
    const BRAND_VARS = [
        "--accent",
        "--accent-2",
        "--accent-3",
        "--success",
        "--border-strong",
        "--focus-ring",
        "--accent-soft",
        "--accent-soft-strong",
        "--accent-gradient",
        "--accent-gradient-soft",
        "--table-row-hover",
        "--brand-glow-1",
        "--brand-glow-2",
    ];

    function normalizeTheme(theme) {
        return Object.prototype.hasOwnProperty.call(THEMES, theme) ? theme : "dark";
    }

    function normalizeHexColor(value) {
        const raw = (value || "").trim().toLowerCase();
        if (!raw) {
            return "";
        }

        const prefixed = raw.startsWith("#") ? raw : `#${raw}`;
        return /^#[0-9a-f]{6}$/.test(prefixed) ? prefixed : "";
    }

    function clampChannel(value) {
        return Math.min(255, Math.max(0, Math.round(value)));
    }

    function hexToRgb(hex) {
        const normalized = normalizeHexColor(hex);
        if (!normalized) {
            return null;
        }

        return {
            r: parseInt(normalized.slice(1, 3), 16),
            g: parseInt(normalized.slice(3, 5), 16),
            b: parseInt(normalized.slice(5, 7), 16),
        };
    }

    function rgbToHex(rgb) {
        const toHex = (channel) => clampChannel(channel).toString(16).padStart(2, "0");
        return `#${toHex(rgb.r)}${toHex(rgb.g)}${toHex(rgb.b)}`;
    }

    function shiftColor(hex, amount) {
        const rgb = hexToRgb(hex);
        if (!rgb) {
            return "";
        }

        const normalizedAmount = Math.max(-1, Math.min(1, amount));
        const mixTarget = normalizedAmount >= 0 ? 255 : 0;
        const mixFactor = Math.abs(normalizedAmount);

        return rgbToHex({
            r: rgb.r + (mixTarget - rgb.r) * mixFactor,
            g: rgb.g + (mixTarget - rgb.g) * mixFactor,
            b: rgb.b + (mixTarget - rgb.b) * mixFactor,
        });
    }

    function toRgba(hex, alpha) {
        const rgb = hexToRgb(hex);
        if (!rgb) {
            return `rgba(34, 197, 94, ${alpha})`;
        }
        return `rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, ${alpha})`;
    }

    function syncThemePickers(theme) {
        const pickers = document.querySelectorAll("[data-theme-picker]");
        pickers.forEach((picker) => {
            if (picker.value !== theme) {
                picker.value = theme;
            }
        });
    }

    function removeBrandOverrides() {
        BRAND_VARS.forEach((variableName) => {
            document.documentElement.style.removeProperty(variableName);
        });
    }

    function getCompanyBrandingFromDataset() {
        const root = document.documentElement;
        return {
            primary: normalizeHexColor(root.dataset.companyPrimary || ""),
            secondary: normalizeHexColor(root.dataset.companySecondary || ""),
        };
    }

    function resolveBrandingPalette(theme, branding = {}) {
        const customPrimary = normalizeHexColor(branding.primary || "");
        const customSecondary = normalizeHexColor(branding.secondary || "");

        if (!customPrimary && !customSecondary) {
            return null;
        }

        const basePrimary = customPrimary || DEFAULT_PRIMARY;
        const baseSecondary = customSecondary || shiftColor(basePrimary, 0.2) || DEFAULT_SECONDARY;
        const isLightTheme = LIGHT_THEMES.has(theme);
        const accent = isLightTheme ? shiftColor(basePrimary, -0.22) : basePrimary;
        const accentSecondary = isLightTheme ? shiftColor(baseSecondary, -0.18) : baseSecondary;
        const accentTertiary = shiftColor(accentSecondary, isLightTheme ? -0.12 : 0.12) || accentSecondary;

        return {
            accent,
            accentSecondary,
            accentTertiary,
        };
    }

    function applyCompanyBranding(options = {}) {
        const root = document.documentElement;
        const theme = normalizeTheme(root.dataset.theme || getSavedTheme());

        if (typeof options.primary === "string") {
            root.dataset.companyPrimary = normalizeHexColor(options.primary);
        }
        if (typeof options.secondary === "string") {
            root.dataset.companySecondary = normalizeHexColor(options.secondary);
        }

        const palette = resolveBrandingPalette(theme, getCompanyBrandingFromDataset());
        if (!palette) {
            removeBrandOverrides();
            return;
        }

        root.style.setProperty("--accent", palette.accent);
        root.style.setProperty("--accent-2", palette.accentSecondary);
        root.style.setProperty("--accent-3", palette.accentTertiary);
        root.style.setProperty("--success", palette.accent);
        root.style.setProperty("--border-strong", toRgba(palette.accent, 0.34));
        root.style.setProperty("--focus-ring", `0 0 0 4px ${toRgba(palette.accent, 0.2)}`);
        root.style.setProperty("--accent-soft", toRgba(palette.accent, LIGHT_THEMES.has(theme) ? 0.12 : 0.16));
        root.style.setProperty("--accent-soft-strong", toRgba(palette.accent, LIGHT_THEMES.has(theme) ? 0.2 : 0.24));
        root.style.setProperty(
            "--accent-gradient",
            `linear-gradient(135deg, ${shiftColor(palette.accentSecondary, 0.15) || palette.accentSecondary} 0%, ${palette.accent} 48%, ${palette.accentTertiary} 100%)`
        );
        root.style.setProperty(
            "--accent-gradient-soft",
            `linear-gradient(135deg, ${toRgba(palette.accentSecondary, 0.14)}, ${toRgba(palette.accent, 0.08)}, ${toRgba(palette.accentTertiary, 0.16)})`
        );
        root.style.setProperty("--table-row-hover", toRgba(palette.accent, 0.1));
        root.style.setProperty("--brand-glow-1", toRgba(palette.accent, 0.14));
        root.style.setProperty("--brand-glow-2", toRgba(palette.accentSecondary, 0.14));
    }

    function applyTheme(theme, options = {}) {
        const resolvedTheme = normalizeTheme(theme);
        document.documentElement.dataset.theme = resolvedTheme;
        document.documentElement.style.colorScheme = THEMES[resolvedTheme];

        if (!options.skipStorage) {
            window.localStorage.setItem(STORAGE_KEY, resolvedTheme);
        }

        syncThemePickers(resolvedTheme);
        applyCompanyBranding();

        document.dispatchEvent(new CustomEvent("themechange", {
            detail: {
                theme: resolvedTheme,
                companyBranding: getCompanyBrandingFromDataset(),
            },
        }));
    }

    function getSavedTheme() {
        return normalizeTheme(window.localStorage.getItem(STORAGE_KEY) || "dark");
    }

    document.addEventListener("DOMContentLoaded", () => {
        const pickers = document.querySelectorAll("[data-theme-picker]");
        const initialTheme = normalizeTheme(document.documentElement.dataset.theme || getSavedTheme());

        applyTheme(initialTheme, { skipStorage: true });

        pickers.forEach((picker) => {
            picker.addEventListener("change", (event) => {
                applyTheme(event.target.value);
            });
        });
    });

    window.EasyScheduleTheme = {
        applyTheme,
        applyCompanyBranding(primary = "", secondary = "") {
            applyCompanyBranding({ primary, secondary });
        },
        getCompanyBranding() {
            return getCompanyBrandingFromDataset();
        },
        getTheme() {
            return normalizeTheme(document.documentElement.dataset.theme || getSavedTheme());
        },
    };
})();
