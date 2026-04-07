document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("[data-copy-target]").forEach((button) => {
        button.addEventListener("click", async () => {
            const target = document.getElementById(button.dataset.copyTarget);
            if (!target) {
                return;
            }

            try {
                await navigator.clipboard.writeText(target.textContent.trim());
                button.textContent = "Codigo copiado";
            } catch (_error) {
                button.textContent = "Nao foi possivel copiar";
            }
        });
    });

    const page = document.querySelector(".client-company-page[data-slots-url]");
    if (!page) {
        return;
    }

    const bookingTypeInputs = Array.from(document.querySelectorAll('input[name="tipo_reserva"]'));

    const elements = {
        slotsUrl: page.dataset.slotsUrl,
        servico: document.getElementById("id_servico"),
        profissional: document.getElementById("id_profissional"),
        data: document.getElementById("id_data"),
        mesReferencia: document.getElementById("id_mes_referencia"),
        diaSemana: document.getElementById("id_dia_semana"),
        hora: document.getElementById("id_hora"),
        feedback: document.getElementById("slotsFeedback"),
        bookingTypeInputs,
        bookingFields: Array.from(document.querySelectorAll("[data-booking-field]")),
    };

    function getBookingType() {
        const selected = elements.bookingTypeInputs.find((input) => input.checked);
        return selected ? selected.value : "avulso";
    }

    function setFeedback(message, state = "") {
        elements.feedback.textContent = message;
        elements.feedback.classList.remove("is-loading", "is-success", "is-error");
        if (state) {
            elements.feedback.classList.add(state);
        }
    }

    function setOptions(options, placeholder) {
        elements.hora.innerHTML = "";

        const defaultOption = document.createElement("option");
        defaultOption.value = "";
        defaultOption.textContent = placeholder;
        elements.hora.appendChild(defaultOption);

        options.forEach((option) => {
            const item = document.createElement("option");
            item.value = option.value;
            item.textContent = option.label;
            elements.hora.appendChild(item);
        });
    }

    function syncBookingMode() {
        const bookingType = getBookingType();

        elements.bookingFields.forEach((field) => {
            const shouldShow = field.dataset.bookingField === bookingType;
            field.classList.toggle("is-hidden", !shouldShow);
        });

        if (bookingType === "pacote_mensal") {
            setFeedback("Selecione servico, profissional, mes e dia da semana para ver os horarios fixos do pacote.");
            setOptions([], "Selecione um horario fixo");
        } else {
            setFeedback("Selecione servico, profissional e data para ver os horarios livres.");
            setOptions([], "Selecione um horario");
        }
    }

    async function refreshSlots() {
        const bookingType = getBookingType();
        const servico = elements.servico.value;
        const profissional = elements.profissional.value;

        if (bookingType === "pacote_mensal") {
            const mesReferencia = elements.mesReferencia.value;
            const diaSemana = elements.diaSemana.value;

            if (!servico || !profissional || !mesReferencia || !diaSemana) {
                setOptions([], "Selecione um horario fixo");
                setFeedback("Selecione servico, profissional, mes e dia da semana para ver os horarios fixos do pacote.");
                return;
            }

            setFeedback("Buscando horarios fixos disponiveis para o mes...", "is-loading");

            const url = new URL(elements.slotsUrl, window.location.origin);
            url.searchParams.set("tipo_reserva", bookingType);
            url.searchParams.set("servico", servico);
            url.searchParams.set("profissional", profissional);
            url.searchParams.set("mes_referencia", mesReferencia);
            url.searchParams.set("dia_semana", diaSemana);

            try {
                const response = await fetch(url.toString(), {
                    headers: {
                        "X-Requested-With": "XMLHttpRequest",
                    },
                });

                if (!response.ok) {
                    throw new Error("Nao foi possivel consultar os horarios do pacote.");
                }

                const payload = await response.json();
                const slots = payload.slots || [];

                if (slots.length) {
                    setOptions(slots, "Selecione um horario fixo");
                    setFeedback(payload.message || "Horarios do pacote atualizados.", "is-success");
                } else {
                    setOptions([], "Nenhum horario fixo disponivel");
                    setFeedback(payload.message || "Nenhum horario fixo ficou livre no mes.", "is-error");
                }
            } catch (error) {
                setOptions([], "Erro ao carregar horarios");
                setFeedback(error.message, "is-error");
            }

            return;
        }

        const data = elements.data.value;

        if (!servico || !profissional || !data) {
            setOptions([], "Selecione um horario");
            setFeedback("Selecione servico, profissional e data para ver os horarios livres.");
            return;
        }

        setFeedback("Buscando horarios disponiveis...", "is-loading");

        const url = new URL(elements.slotsUrl, window.location.origin);
        url.searchParams.set("tipo_reserva", bookingType);
        url.searchParams.set("servico", servico);
        url.searchParams.set("profissional", profissional);
        url.searchParams.set("data", data);

        try {
            const response = await fetch(url.toString(), {
                headers: {
                    "X-Requested-With": "XMLHttpRequest",
                },
            });

            if (!response.ok) {
                throw new Error("Nao foi possivel consultar os horarios.");
            }

            const payload = await response.json();
            const slots = payload.slots || [];

            if (slots.length) {
                setOptions(slots, "Selecione um horario");
                setFeedback(payload.message || "Horarios atualizados.", "is-success");
            } else {
                setOptions([], "Nenhum horario disponivel");
                setFeedback(payload.message || "Nenhum horario livre para essa combinacao.", "is-error");
            }
        } catch (error) {
            setOptions([], "Erro ao carregar horarios");
            setFeedback(error.message, "is-error");
        }
    }

    syncBookingMode();

    [
        elements.servico,
        elements.profissional,
        elements.data,
        elements.mesReferencia,
        elements.diaSemana,
    ].forEach((field) => {
        if (field) {
            field.addEventListener("change", refreshSlots);
        }
    });

    elements.bookingTypeInputs.forEach((input) => {
        input.addEventListener("change", () => {
            syncBookingMode();
            refreshSlots();
        });
    });
});
