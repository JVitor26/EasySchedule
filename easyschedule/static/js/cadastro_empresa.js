document.addEventListener("DOMContentLoaded", () => {
    const configElement = document.getElementById("business-profile-config");
    const select = document.getElementById("id_tipo_empresa");

    if (!configElement || !select) {
        return;
    }

    const profiles = JSON.parse(configElement.textContent);
    const ids = {
        title: document.getElementById("registrationTitle"),
        subtitle: document.getElementById("registrationSubtitle"),
        ownerLabel: document.getElementById("registrationOwnerLabel"),
        documentLabel: document.getElementById("registrationDocumentLabel"),
        companyLabel: document.getElementById("registrationCompanyLabel"),
        companyInput: document.getElementById("id_nome_empresa"),
        previewTitle: document.getElementById("businessPreviewTitle"),
        previewHighlight: document.getElementById("businessPreviewHighlight"),
        previewProfessionals: document.getElementById("businessPreviewProfessionals"),
        previewServices: document.getElementById("businessPreviewServices"),
        previewAppointments: document.getElementById("businessPreviewAppointments"),
        previewPoints: document.getElementById("businessPreviewPoints"),
        primaryColorInput: document.getElementById("id_cor_primaria"),
        secondaryColorInput: document.getElementById("id_cor_secundaria"),
        primaryColorPicker: document.getElementById("id_cor_primaria_picker"),
        secondaryColorPicker: document.getElementById("id_cor_secundaria_picker"),
        emailPreviewHeader: document.getElementById("brandingEmailPreviewHeader"),
        emailPreviewMonogram: document.getElementById("brandingEmailPreviewMonogram"),
        emailPreviewCompany: document.getElementById("brandingEmailPreviewCompany"),
        emailPreviewType: document.getElementById("brandingEmailPreviewType"),
        whatsappPreviewHeader: document.getElementById("brandingWhatsappPreviewHeader"),
        whatsappPreviewCustomer: document.getElementById("brandingWhatsappPreviewCustomer"),
        whatsappPreviewProfessional: document.getElementById("brandingWhatsappPreviewProfessional"),
    };

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

    function updateEmailHeaderPreview() {
        if (!ids.emailPreviewHeader) {
            return;
        }

        const primary = resolveColor(ids.primaryColorInput, "#0f4c81");
        const secondary = resolveColor(ids.secondaryColorInput, "#188fa7");
        const companyName = (ids.companyInput && ids.companyInput.value.trim()) || "Sua empresa";
        const profile = profiles[select.value] || profiles.outro || {};

        ids.emailPreviewHeader.style.background = `linear-gradient(135deg, ${primary}, ${secondary})`;

        if (ids.emailPreviewMonogram) {
            ids.emailPreviewMonogram.textContent = buildMonogram(companyName);
        }
        if (ids.emailPreviewCompany) {
            ids.emailPreviewCompany.textContent = companyName;
        }
        if (ids.emailPreviewType) {
            ids.emailPreviewType.textContent = profile.label || "Negocio de servicos";
        }
    }

    function updateWhatsAppPreview() {
        if (!ids.whatsappPreviewCustomer || !ids.whatsappPreviewProfessional) {
            return;
        }

        const primary = resolveColor(ids.primaryColorInput, "#0f4c81");
        const secondary = resolveColor(ids.secondaryColorInput, "#188fa7");
        const companyName = (ids.companyInput && ids.companyInput.value.trim()) || "Sua empresa";
        const profile = profiles[select.value] || profiles.outro || {};
        const profileLabel = profile.label || "Negocio de servicos";

        if (ids.whatsappPreviewHeader) {
            ids.whatsappPreviewHeader.style.background = `linear-gradient(135deg, ${primary}, ${secondary})`;
        }

        ids.whatsappPreviewCustomer.textContent = [
            `${companyName} | Confirmacao de agendamento`,
            `Segmento: ${profileLabel}`,
            "Servico: Corte completo",
            "Profissional: Rafael",
            "Data: 12/05/2026",
            "Hora: 10:00",
            "Status: Pendente",
            "Nos vemos em breve!",
        ].join("\n");

        ids.whatsappPreviewProfessional.textContent = [
            `${companyName} | Novo agendamento recebido`,
            `Segmento: ${profileLabel}`,
            "Cliente: Joao Cliente",
            "Servico: Corte completo",
            "Data: 12/05/2026",
            "Hora: 10:00",
            "Status: Pendente",
            "Acesse a agenda para acompanhar os detalhes.",
        ].join("\n");
    }

    function refreshBrandingPreviews() {
        updateEmailHeaderPreview();
        updateWhatsAppPreview();

        if (window.EasyScheduleTheme && typeof window.EasyScheduleTheme.applyCompanyBranding === "function") {
            const primary = resolveColor(ids.primaryColorInput, "#0f4c81");
            const secondary = resolveColor(ids.secondaryColorInput, "#188fa7");
            window.EasyScheduleTheme.applyCompanyBranding(primary, secondary);
        }
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

    function renderProfile(profileKey) {
        const profile = profiles[profileKey] || profiles.outro;
        if (!profile) {
            return;
        }

        ids.title.textContent = profile.registration_title;
        ids.subtitle.textContent = profile.registration_subtitle;
        ids.ownerLabel.textContent = profile.owner_name_label;
        ids.documentLabel.textContent = profile.document_label;
        ids.companyLabel.textContent = profile.company_name_label;
        ids.companyInput.placeholder = profile.company_name_placeholder;
        ids.previewTitle.textContent = profile.label;
        ids.previewHighlight.textContent = profile.registration_highlight;
        ids.previewProfessionals.textContent = profile.professional_term_plural;
        ids.previewServices.textContent = profile.service_term_plural;
        ids.previewAppointments.textContent = profile.appointment_term_plural;
        ids.previewPoints.innerHTML = "";

        (profile.preview_points || []).forEach((point) => {
            const item = document.createElement("li");
            item.textContent = point;
            ids.previewPoints.appendChild(item);
        });
    }

    select.addEventListener("change", (event) => {
        renderProfile(event.target.value);
        refreshBrandingPreviews();
    });

    if (ids.companyInput) {
        ids.companyInput.addEventListener("input", refreshBrandingPreviews);
    }

    // 🎨 Visual Plan Selector
    const planoSelector = document.getElementById("plano-selector");
    const planoField = document.getElementById("id_plano");
    const limitFieldWrap = document.getElementById("limiteProfissionaisField");
    const limitInput = document.getElementById("id_limite_profissionais");

    const plans = [
        {
            id: "solo",
            name: "Solo",
            subtitle: "Para você trabalhar sozinho",
            desc: "1 profissional com acesso ao sistema",
            price: "R$ 97",
            features: ["1 usuário com acesso", "Agenda completa", "Portal do cliente"],
            recommended: false,
        },
        {
            id: "start",
            name: "Start",
            subtitle: "Para equipes pequenas",
            desc: "Até 5 profissionais com acesso",
            price: "R$ 147",
            features: ["Até 5 usuários", "Notificações em app", "Gestão de produtos", "Relatórios"],
            recommended: true,
        },
        {
            id: "admin_only",
            name: "Gestão Interna",
            subtitle: "Você gerencia tudo",
            desc: "Apenas você tem acesso. Crie funcionários pra agenda",
            price: "R$ 127",
            features: ["Acesso só seu", "Cadastre quantos quiser", "Você manipula tudo", "Ideal pra controle total"],
            recommended: false,
        },
    ];

    function renderPlans() {
        planoSelector.innerHTML = plans.map((plan) => `
            <label class="plan-card" style="display: grid; grid-template-columns: 1fr auto; gap: 1rem; padding: 1.2rem; border: 2px solid var(--border-soft); border-radius: var(--radius-lg); cursor: pointer; transition: all 0.2s;
                ${plan.recommended ? 'background: linear-gradient(135deg, rgba(34, 197, 94, 0.12), transparent); border-color: var(--accent);' : 'background: var(--surface-soft);'}"
                    onchange="document.getElementById('updateLimitField')();">
                
                <input type="radio" name="plano" value="${plan.id}" ${plan.id === "solo" ? "checked" : ""} 
                       style="margin: 0; cursor: pointer; transform: scale(1.4); accent-color: var(--accent);" />
                
                <div style="grid-column: 1 / -1;">
                    <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem;">
                        <strong style="font-size: 1.1rem; color: var(--text-1);">${plan.name}</strong>
                        ${plan.recommended ? '<span style="background: var(--accent); color: white; padding: 0.25rem 0.75rem; border-radius: 9999px; font-size: 0.75rem; font-weight: 700;">RECOMENDADO</span>' : ''}
                    </div>
                    <p style="color: var(--text-2); font-size: 0.9rem; margin: 0 0 0.75rem 0;">${plan.desc}</p>
                    <div style="color: var(--accent); font-weight: 700; font-size: 1.15rem; margin-bottom: 0.75rem;">${plan.price}</div>
                    <ul style="margin: 0; padding: 0 0 0 1.25rem; list-style: disc; color: var(--text-2); font-size: 0.85rem;">
                        ${plan.features.map((f) => `<li>${f}</li>`).join("")}
                    </ul>
                </div>
            </label>
        `).join("");
    }

    window.updateLimitField = function() {
        const selected = document.querySelector('input[name="plano"]:checked');
        if (!selected) return;

        const planoValue = selected.value;
        planoField.value = planoValue;

        if (planoValue === "start") {
            limitFieldWrap.style.display = "block";
            limitInput.readOnly = false;
            if (!limitInput.value || limitInput.value < 1) limitInput.value = "1";
        } else {
            limitFieldWrap.style.display = "none";
            if (planoValue === "solo") {
                limitInput.value = "1";
            } else if (planoValue === "admin_only") {
                limitInput.value = "5";
            }
        }
    };

    renderPlans();

    bindColorPicker(ids.primaryColorInput, ids.primaryColorPicker, "#0f4c81", refreshBrandingPreviews);
    bindColorPicker(ids.secondaryColorInput, ids.secondaryColorPicker, "#188fa7", refreshBrandingPreviews);
    
    document.querySelectorAll('input[name="plano"]').forEach((input) => {
        input.addEventListener("change", window.updateLimitField);
    });

    window.updateLimitField();
    renderProfile(select.value);
    refreshBrandingPreviews();
});
