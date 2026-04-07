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
    };

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
    });

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
    
    document.querySelectorAll('input[name="plano"]').forEach((input) => {
        input.addEventListener("change", window.updateLimitField);
    });

    window.updateLimitField();
    renderProfile(select.value);
});
