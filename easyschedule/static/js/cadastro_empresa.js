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

    renderProfile(select.value);
});
