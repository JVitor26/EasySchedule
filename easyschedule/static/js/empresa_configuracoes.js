document.addEventListener("DOMContentLoaded", () => {
    const ids = {
        companyNameInput: document.getElementById("id_nome"),
        companyTypeInput: document.getElementById("id_tipo"),
        primaryColorInput: document.getElementById("id_cor_primaria"),
        secondaryColorInput: document.getElementById("id_cor_secundaria"),
        primaryColorPicker: document.getElementById("id_cor_primaria_picker"),
        secondaryColorPicker: document.getElementById("id_cor_secundaria_picker"),
        previewHeader: document.getElementById("brandingCompanyPreviewHeader"),
        previewMonogram: document.getElementById("brandingCompanyPreviewMonogram"),
        previewName: document.getElementById("brandingCompanyPreviewName"),
        previewType: document.getElementById("brandingCompanyPreviewType"),
    };

    if (!ids.primaryColorInput || !ids.secondaryColorInput) {
        return;
    }

    function normalizeHexColor(value) {
        const raw = (value || "").trim().toLowerCase();
        if (!raw) {
            return "";
        }
        return raw.startsWith("#") ? raw : `#${raw}`;
    }

    function isHexColor(value) {
        return /^#[0-9a-f]{6}$/i.test(value || "");
    }

    function buildMonogram(companyName) {
        const parts = (companyName || "")
            .replace(/[^a-zA-Z0-9]+/g, " ")
            .trim()
            .split(/\s+/)
            .filter(Boolean);

        if (parts.length >= 2) {
            return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
        }
        if (parts.length === 1) {
            return parts[0].slice(0, 2).toUpperCase();
        }
        return "ES";
    }

    function resolveColor(inputElement, fallbackColor) {
        const normalized = normalizeHexColor(inputElement ? inputElement.value : "");
        if (isHexColor(normalized)) {
            return normalized.toLowerCase();
        }
        return fallbackColor;
    }

    function bindColorPicker(input, picker, fallbackColor, onChange) {
        if (!input || !picker) {
            return;
        }

        const normalized = normalizeHexColor(input.value);
        picker.value = isHexColor(normalized) ? normalized : fallbackColor;

        input.addEventListener("input", () => {
            const parsed = normalizeHexColor(input.value);
            if (isHexColor(parsed)) {
                picker.value = parsed;
            }
            if (onChange) {
                onChange();
            }
        });

        picker.addEventListener("input", () => {
            input.value = picker.value.toLowerCase();
            if (onChange) {
                onChange();
            }
        });
    }

    function refreshPreview() {
        const companyName = (ids.companyNameInput && ids.companyNameInput.value.trim()) || "Sua empresa";
        const primary = resolveColor(ids.primaryColorInput, "#0f4c81");
        const secondary = resolveColor(ids.secondaryColorInput, "#188fa7");

        if (ids.previewHeader) {
            ids.previewHeader.style.background = `linear-gradient(135deg, ${primary}, ${secondary})`;
        }
        if (ids.previewMonogram) {
            ids.previewMonogram.textContent = buildMonogram(companyName);
        }
        if (ids.previewName) {
            ids.previewName.textContent = companyName;
        }
        if (ids.previewType && ids.companyTypeInput) {
            const selectedOption = ids.companyTypeInput.options[ids.companyTypeInput.selectedIndex];
            ids.previewType.textContent = selectedOption ? selectedOption.text : "Identidade da empresa";
        }

        if (window.EasyScheduleTheme && typeof window.EasyScheduleTheme.applyCompanyBranding === "function") {
            window.EasyScheduleTheme.applyCompanyBranding(primary, secondary);
        }
    }

    bindColorPicker(ids.primaryColorInput, ids.primaryColorPicker, "#0f4c81", refreshPreview);
    bindColorPicker(ids.secondaryColorInput, ids.secondaryColorPicker, "#188fa7", refreshPreview);

    if (ids.companyNameInput) {
        ids.companyNameInput.addEventListener("input", refreshPreview);
    }
    if (ids.companyTypeInput) {
        ids.companyTypeInput.addEventListener("change", refreshPreview);
    }

    refreshPreview();
});
