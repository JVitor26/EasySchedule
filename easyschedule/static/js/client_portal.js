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
        slotHoldUrl: page.dataset.slotHoldUrl,
        clientLookupUrl: page.dataset.clientLookupUrl,
        aiChatUrl: page.dataset.aiChatUrl,
        nome: document.getElementById("id_nome"),
        email: document.getElementById("id_email"),
        telefone: document.getElementById("id_telefone"),
        documento: document.getElementById("id_documento"),
        dataNascimento: document.getElementById("id_data_nascimento"),
        servico: document.getElementById("id_servico"),
        profissional: document.getElementById("id_profissional"),
        data: document.getElementById("id_data"),
        mesReferencia: document.getElementById("id_mes_referencia"),
        diaSemana: document.getElementById("id_dia_semana"),
        hora: document.getElementById("id_hora"),
        feedback: document.getElementById("slotsFeedback"),
        holdFeedback: document.getElementById("slotHoldFeedback"),
        slotHoldToken: document.getElementById("id_slot_hold_token"),
        bookingForm: document.getElementById("bookingForm"),
        bookingTypeInputs,
        bookingFields: Array.from(document.querySelectorAll("[data-booking-field]")),
        quickSlots: document.getElementById("quickSlots"),
        slotChips: document.getElementById("slotChips"),
        firstAvailableBtn: document.getElementById("firstAvailableBtn"),
        bookingSummary: document.getElementById("bookingSummary"),
        clientLookupFeedback: document.getElementById("clientLookupFeedback"),
        repeatBookingBox: document.getElementById("repeatBookingBox"),
        clientAiInput: document.getElementById("clientAiInput"),
        clientAiSendBtn: document.getElementById("clientAiSendBtn"),
        clientAiVoiceBtn: document.getElementById("clientAiVoiceBtn"),
        clientAiVoiceStatus: document.getElementById("clientAiVoiceStatus"),
        clientAiFeedback: document.getElementById("clientAiFeedback"),
        clientAiSuggestions: document.getElementById("clientAiSuggestions"),
    };

    const SpeechRecognitionConstructor = window.SpeechRecognition || window.webkitSpeechRecognition;

    function readCookie(name) {
        const prefix = `${name}=`;
        const cookie = document.cookie
            .split(";")
            .map((item) => item.trim())
            .find((item) => item.startsWith(prefix));
        return cookie ? cookie.slice(prefix.length) : "";
    }

    function getCsrfToken() {
        return (
            document.querySelector("[name=csrfmiddlewaretoken]")?.value ||
            readCookie("csrftoken") ||
            ""
        );
    }

    async function parseJsonResponse(response, fallbackErrorMessage) {
        const bodyText = await response.text();
        if (!bodyText) {
            return {};
        }

        try {
            return JSON.parse(bodyText);
        } catch (_error) {
            if (!response.ok) {
                throw new Error(fallbackErrorMessage || "O servidor retornou uma resposta invalida.");
            }
            throw new Error("Resposta invalida do servidor. Atualize a pagina e tente novamente.");
        }
    }

    const csrfToken = getCsrfToken();

    let holdTimer = null;
    let clientVoiceRecognition = null;
    let clientVoiceIsListening = false;
    let clientVoiceHadError = false;
    let clientVoiceTranscript = "";

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

    function setHoldFeedback(message, state = "") {
        if (!elements.holdFeedback) {
            return;
        }
        elements.holdFeedback.textContent = message;
        elements.holdFeedback.classList.remove("is-loading", "is-success", "is-error");
        if (state) {
            elements.holdFeedback.classList.add(state);
        }
    }

    function setClientLookupFeedback(message, state = "") {
        if (!elements.clientLookupFeedback) {
            return;
        }
        elements.clientLookupFeedback.textContent = message || "";
        elements.clientLookupFeedback.classList.remove("is-loading", "is-success", "is-error");
        if (state) {
            elements.clientLookupFeedback.classList.add(state);
        }
    }

    function setAiFeedback(message, state = "") {
        if (!elements.clientAiFeedback) {
            return;
        }
        elements.clientAiFeedback.textContent = message || "";
        elements.clientAiFeedback.classList.remove("is-loading", "is-success", "is-error");
        if (state) {
            elements.clientAiFeedback.classList.add(state);
        }
    }

    function setClientVoiceStatus(message = "", isListening = false) {
        if (elements.clientAiVoiceStatus) {
            elements.clientAiVoiceStatus.textContent = message;
        }
        if (elements.clientAiVoiceBtn) {
            elements.clientAiVoiceBtn.textContent = isListening ? "Parar audio" : "Gravar audio";
            elements.clientAiVoiceBtn.setAttribute("aria-pressed", isListening ? "true" : "false");
            elements.clientAiVoiceBtn.classList.toggle("is-listening", isListening);
        }
    }

    function clearHoldState(resetToken = true) {
        if (holdTimer) {
            window.clearInterval(holdTimer);
            holdTimer = null;
        }
        if (resetToken && elements.slotHoldToken) {
            elements.slotHoldToken.value = "";
        }
        setHoldFeedback("");
    }

    function startHoldCountdown(expiresAtIso) {
        if (!expiresAtIso) {
            clearHoldState(false);
            return;
        }

        const expiresAt = new Date(expiresAtIso);
        if (Number.isNaN(expiresAt.getTime())) {
            clearHoldState(false);
            return;
        }

        if (holdTimer) {
            window.clearInterval(holdTimer);
        }

        const tick = () => {
            const remainingMs = expiresAt.getTime() - Date.now();
            if (remainingMs <= 0) {
                clearHoldState();
                setHoldFeedback("A reserva temporaria expirou. Selecione o horario novamente.", "is-error");
                return;
            }

            const totalSeconds = Math.floor(remainingMs / 1000);
            const minutes = Math.floor(totalSeconds / 60).toString().padStart(2, "0");
            const seconds = (totalSeconds % 60).toString().padStart(2, "0");
            setHoldFeedback(`Horario reservado por ${minutes}:${seconds}. Finalize a reserva antes de expirar.`, "is-success");
        };

        tick();
        holdTimer = window.setInterval(tick, 1000);
    }

    async function reserveSelectedSlotHold() {
        if (getBookingType() !== "avulso") {
            clearHoldState();
            return;
        }

        if (!elements.slotHoldUrl || !elements.servico.value || !elements.profissional.value || !elements.data.value || !elements.hora.value) {
            clearHoldState();
            return;
        }

        setHoldFeedback("Reservando horario temporariamente...", "is-loading");

        try {
            const response = await fetch(elements.slotHoldUrl, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-Requested-With": "XMLHttpRequest",
                    ...(csrfToken ? { "X-CSRFToken": csrfToken } : {}),
                },
                body: JSON.stringify({
                    servico: elements.servico.value,
                    profissional: elements.profissional.value,
                    data: elements.data.value,
                    hora: elements.hora.value,
                    hold_token: elements.slotHoldToken?.value || "",
                }),
            });

            const payload = await parseJsonResponse(response, "Nao foi possivel reservar o horario temporariamente.");
            if (!response.ok || payload.status !== "sucesso") {
                throw new Error(payload.message || "Nao foi possivel reservar o horario temporariamente.");
            }

            if (elements.slotHoldToken) {
                elements.slotHoldToken.value = payload.hold_token || "";
            }

            startHoldCountdown(payload.expires_at);
        } catch (error) {
            clearHoldState();
            setHoldFeedback(error.message, "is-error");
            refreshSlots();
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
            if (option.profissional_id) {
                item.dataset.profissionalId = option.profissional_id;
            }
            elements.hora.appendChild(item);
        });
    }

    function ensureHourOption(value, label, profissionalId = "") {
        if (!value || !elements.hora) {
            return;
        }
        const existing = Array.from(elements.hora.options).find((option) => option.value === value);
        if (existing) {
            if (profissionalId) {
                existing.dataset.profissionalId = profissionalId;
            }
            return;
        }
        const option = document.createElement("option");
        option.value = value;
        option.textContent = label || value;
        if (profissionalId) {
            option.dataset.profissionalId = profissionalId;
        }
        elements.hora.appendChild(option);
    }

    function getSelectedText(select) {
        if (!select || select.selectedIndex < 0) {
            return "";
        }
        return select.options[select.selectedIndex]?.textContent?.trim() || "";
    }

    function updateBookingSummary(extra = {}) {
        if (!elements.bookingSummary) {
            return;
        }

        const serviceLabel = getSelectedText(elements.servico);
        const professionalLabel = extra.profissionalNome || getSelectedText(elements.profissional) || "Qualquer profissional";
        const dateLabel = extra.dataLabel || elements.data?.value || "";
        const hourLabel = extra.hora || elements.hora?.value || "";

        if (!serviceLabel || !hourLabel || getBookingType() !== "avulso") {
            elements.bookingSummary.hidden = true;
            elements.bookingSummary.innerHTML = "";
            return;
        }

        elements.bookingSummary.hidden = false;
        elements.bookingSummary.innerHTML = `
            <strong>Resumo da reserva</strong>
            <span>${serviceLabel}</span>
            <span>${professionalLabel}</span>
            <span>${dateLabel} as ${hourLabel}</span>
        `;
    }

    async function applySlotChoice(slot) {
        if (!slot) {
            return;
        }

        if (slot.data && elements.data) {
            elements.data.value = slot.data;
        }
        if (slot.profissional_id && elements.profissional) {
            elements.profissional.value = String(slot.profissional_id);
        }
        ensureHourOption(slot.hora || slot.value, slot.label, slot.profissional_id || "");
        if (elements.hora) {
            elements.hora.value = slot.hora || slot.value;
        }

        updateBookingSummary({
            dataLabel: slot.data || elements.data?.value || "",
            hora: slot.hora || slot.value,
            profissionalNome: slot.profissional_nome || "",
        });
        await reserveSelectedSlotHold();
    }

    function renderSlotButtons(container, slots, emptyMessage = "") {
        if (!container) {
            return;
        }

        container.innerHTML = "";
        if (!slots?.length) {
            if (emptyMessage) {
                const empty = document.createElement("p");
                empty.className = "slots-feedback";
                empty.textContent = emptyMessage;
                container.appendChild(empty);
            }
            return;
        }

        slots.forEach((slot) => {
            const button = document.createElement("button");
            button.type = "button";
            button.className = "quick-slot-chip";
            button.textContent = slot.label || slot.value || slot.hora;
            button.addEventListener("click", () => applySlotChoice({
                ...slot,
                hora: slot.hora || slot.value,
                data: slot.data || elements.data?.value || "",
            }));
            container.appendChild(button);
        });
    }

    function syncBookingMode() {
        const bookingType = getBookingType();

        elements.bookingFields.forEach((field) => {
            const modes = (field.dataset.bookingField || "")
                .split(",")
                .map((value) => value.trim())
                .filter(Boolean);
            const shouldShow = !modes.length || modes.includes(bookingType);
            field.classList.toggle("is-hidden", !shouldShow);
        });

        if (bookingType === "somente_produtos") {
            clearHoldState();
            setFeedback("Confirme os dados pessoais, a data de retirada/entrega e finalize somente os produtos do carrinho.");
            setOptions([], "Nao se aplica para compra somente de produtos");
            renderSlotButtons(elements.quickSlots, []);
            renderSlotButtons(elements.slotChips, []);
        } else if (bookingType === "pacote_mensal") {
            clearHoldState();
            setFeedback("Selecione servico, mes e dia da semana para ver os horarios fixos do pacote.");
            setOptions([], "Selecione um horario fixo");
            renderSlotButtons(elements.quickSlots, []);
            renderSlotButtons(elements.slotChips, []);
        } else {
            setFeedback("Selecione servico e data para ver os horarios livres, ou use o primeiro horario disponivel.");
            setOptions([], "Selecione um horario");
            renderSlotButtons(elements.slotChips, []);
        }
        updateBookingSummary();
    }

    async function refreshSlots() {
        const bookingType = getBookingType();
        const servico = elements.servico.value;
        const profissional = elements.profissional.value;

        if (bookingType === "somente_produtos") {
            clearHoldState();
            setOptions([], "Nao se aplica para compra somente de produtos");
            setFeedback("Os horarios nao sao obrigatorios para confirmar somente produtos.");
            return;
        }

        if (bookingType === "pacote_mensal") {
            const mesReferencia = elements.mesReferencia.value;
            const diaSemana = elements.diaSemana.value;

            if (!servico || !mesReferencia || !diaSemana) {
                setOptions([], "Selecione um horario fixo");
                setFeedback("Selecione servico, mes e dia da semana para ver os horarios fixos do pacote.");
                return;
            }

            setFeedback("Buscando horarios fixos disponiveis para o mes...", "is-loading");

            const url = new URL(elements.slotsUrl, window.location.origin);
            url.searchParams.set("tipo_reserva", bookingType);
            url.searchParams.set("servico", servico);
            if (profissional) {
                url.searchParams.set("profissional", profissional);
            }
            url.searchParams.set("mes_referencia", mesReferencia);
            url.searchParams.set("dia_semana", diaSemana);

            try {
                const response = await fetch(url.toString(), {
                    headers: {
                        "X-Requested-With": "XMLHttpRequest",
                    },
                });

                const payload = await parseJsonResponse(response, "Nao foi possivel consultar os horarios do pacote.");
                if (!response.ok) {
                    throw new Error(payload.message || "Nao foi possivel consultar os horarios do pacote.");
                }
                const slots = payload.slots || [];

                if (slots.length) {
                    setOptions(slots, "Selecione um horario fixo");
                    renderSlotButtons(elements.slotChips, slots);
                    setFeedback(payload.message || "Horarios do pacote atualizados.", "is-success");
                } else {
                    setOptions([], "Nenhum horario fixo disponivel");
                    renderSlotButtons(elements.slotChips, []);
                    setFeedback(payload.message || "Nenhum horario fixo ficou livre no mes.", "is-error");
                }
            } catch (error) {
                setOptions([], "Erro ao carregar horarios");
                renderSlotButtons(elements.slotChips, []);
                setFeedback(error.message, "is-error");
            }

            return;
        }

        const data = elements.data.value;

        if (!servico || !data) {
            setOptions([], "Selecione um horario");
            renderSlotButtons(elements.slotChips, []);
            setFeedback("Selecione servico e data para ver os horarios livres.");
            return;
        }

        setFeedback("Buscando horarios disponiveis...", "is-loading");

        const url = new URL(elements.slotsUrl, window.location.origin);
        url.searchParams.set("tipo_reserva", bookingType);
        url.searchParams.set("servico", servico);
        if (profissional) {
            url.searchParams.set("profissional", profissional);
        }
        url.searchParams.set("data", data);
            if (elements.slotHoldToken?.value) {
                url.searchParams.set("hold_token", elements.slotHoldToken.value);
            }

        try {
            const response = await fetch(url.toString(), {
                headers: {
                    "X-Requested-With": "XMLHttpRequest",
                },
            });

            const payload = await parseJsonResponse(response, "Nao foi possivel consultar os horarios.");
            if (!response.ok) {
                throw new Error(payload.message || "Nao foi possivel consultar os horarios.");
            }
            const slots = payload.slots || [];

            if (slots.length) {
                setOptions(slots, "Selecione um horario");
                renderSlotButtons(elements.slotChips, slots.map((slot) => ({ ...slot, data })));
                setFeedback(payload.message || "Horarios atualizados.", "is-success");
            } else {
                setOptions([], "Nenhum horario disponivel");
                renderSlotButtons(elements.slotChips, []);
                setFeedback(payload.message || "Nenhum horario livre para essa combinacao.", "is-error");
            }
            renderSlotButtons(elements.quickSlots, payload.suggestions || []);
        } catch (error) {
            setOptions([], "Erro ao carregar horarios");
            renderSlotButtons(elements.slotChips, []);
            setFeedback(error.message, "is-error");
        }
    }

    async function loadFirstAvailableSlots() {
        if (getBookingType() !== "avulso") {
            return;
        }

        const servico = elements.servico.value;
        const profissional = elements.profissional.value;
        if (!servico) {
            setFeedback("Escolha um servico para encontrar o primeiro horario.", "is-error");
            return;
        }

        setFeedback("Procurando os primeiros horarios livres...", "is-loading");
        renderSlotButtons(elements.quickSlots, []);

        const url = new URL(elements.slotsUrl, window.location.origin);
        url.searchParams.set("tipo_reserva", "avulso");
        url.searchParams.set("servico", servico);
        if (profissional) {
            url.searchParams.set("profissional", profissional);
        }

        try {
            const response = await fetch(url.toString(), {
                headers: { "X-Requested-With": "XMLHttpRequest" },
            });
            const payload = await parseJsonResponse(response, "Nao foi possivel buscar horarios livres.");
            if (!response.ok) {
                throw new Error(payload.message || "Nao foi possivel buscar horarios livres.");
            }
            renderSlotButtons(elements.quickSlots, payload.suggestions || [], "Nenhum horario encontrado nos proximos dias.");
            setFeedback(payload.message || "Escolha um dos horarios sugeridos.", payload.suggestions?.length ? "is-success" : "is-error");
        } catch (error) {
            setFeedback(error.message, "is-error");
        }
    }

    async function lookupClientByContact() {
        if (!elements.clientLookupUrl || !elements.telefone) {
            return;
        }

        const telefone = elements.telefone.value || "";
        const email = elements.email?.value || "";
        const normalizedPhone = telefone.replace(/\D/g, "");
        if (normalizedPhone.length < 10 && !email.includes("@")) {
            return;
        }

        setClientLookupFeedback("Buscando seu cadastro...", "is-loading");
        const url = new URL(elements.clientLookupUrl, window.location.origin);
        if (normalizedPhone) {
            url.searchParams.set("telefone", normalizedPhone);
        }
        if (email) {
            url.searchParams.set("email", email);
        }

        try {
            const response = await fetch(url.toString(), {
                headers: { "X-Requested-With": "XMLHttpRequest" },
            });
            const payload = await parseJsonResponse(response, "Nao foi possivel buscar o cadastro.");
            if (!response.ok || payload.status !== "sucesso") {
                throw new Error(payload.message || "Nao foi possivel buscar o cadastro.");
            }

            if (!payload.cliente) {
                setClientLookupFeedback(payload.message || "Cliente novo. Continue o cadastro.", "");
                if (elements.repeatBookingBox) {
                    elements.repeatBookingBox.innerHTML = "";
                }
                return;
            }

            const cliente = payload.cliente;
            if (elements.nome && cliente.nome) elements.nome.value = cliente.nome;
            if (elements.email && cliente.email) elements.email.value = cliente.email;
            if (elements.telefone && cliente.telefone) elements.telefone.value = cliente.telefone;
            if (elements.documento && cliente.documento) elements.documento.value = cliente.documento;
            if (elements.dataNascimento && cliente.data_nascimento) elements.dataNascimento.value = cliente.data_nascimento;

            setClientLookupFeedback(payload.message || "Cadastro encontrado.", "is-success");

            if (elements.repeatBookingBox) {
                elements.repeatBookingBox.innerHTML = "";
                if (payload.ultimo_agendamento) {
                    const button = document.createElement("button");
                    button.type = "button";
                    button.className = "quick-slot-chip";
                    button.textContent = `Agendar novamente: ${payload.ultimo_agendamento.servico_nome} com ${payload.ultimo_agendamento.profissional_nome}`;
                    button.addEventListener("click", () => {
                        elements.servico.value = String(payload.ultimo_agendamento.servico_id);
                        elements.profissional.value = String(payload.ultimo_agendamento.profissional_id);
                        setFeedback("Atendimento anterior selecionado. Agora escolha o primeiro horario disponivel.", "is-success");
                        loadFirstAvailableSlots();
                    });
                    elements.repeatBookingBox.appendChild(button);
                }
            }
        } catch (error) {
            setClientLookupFeedback(error.message, "is-error");
        }
    }

    function applyAiContext(context) {
        const booking = context?.booking || {};
        if (booking.servico_id && elements.servico) {
            elements.servico.value = String(booking.servico_id);
        }
        if (booking.profissional_id && elements.profissional) {
            elements.profissional.value = String(booking.profissional_id);
        }
        if (booking.data && elements.data) {
            elements.data.value = booking.data;
        }
        if (booking.hora && elements.hora) {
            ensureHourOption(booking.hora, booking.hora, booking.profissional_id || "");
            elements.hora.value = booking.hora;
        }
        if (booking.nome_cliente && elements.nome && !elements.nome.value) {
            elements.nome.value = booking.nome_cliente;
        }
        updateBookingSummary();
    }

    async function sendClientAiMessage(messageOverride = "") {
        if (!elements.aiChatUrl || !elements.clientAiInput) {
            return;
        }
        const mensagem = (messageOverride || elements.clientAiInput.value || "").trim();
        if (!mensagem) {
            setAiFeedback("Digite o pedido de agendamento.", "is-error");
            return;
        }

        setAiFeedback("Entendendo seu pedido...", "is-loading");
        if (elements.clientAiSuggestions) {
            elements.clientAiSuggestions.innerHTML = "";
        }
        try {
            const response = await fetch(elements.aiChatUrl, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-Requested-With": "XMLHttpRequest",
                    ...(csrfToken ? { "X-CSRFToken": csrfToken } : {}),
                },
                body: JSON.stringify({
                    telefone: elements.telefone?.value || "",
                    mensagem,
                    contexto: window._clientAiContext || {},
                }),
            });
            const payload = await parseJsonResponse(response, "Nao foi possivel entender o pedido.");
            if (!response.ok || payload.status !== "sucesso") {
                throw new Error(payload.message || "Nao foi possivel entender o pedido.");
            }
            window._clientAiContext = payload.contexto || {};
            applyAiContext(payload.contexto);
            setAiFeedback(payload.resposta || "Pedido entendido.", "is-success");

            (payload.sugestoes || []).slice(0, 6).forEach((suggestion) => {
                if (!elements.clientAiSuggestions) {
                    return;
                }
                const button = document.createElement("button");
                button.type = "button";
                button.className = "quick-slot-chip";
                button.textContent = suggestion;
                button.addEventListener("click", () => {
                    elements.clientAiInput.value = suggestion;
                    sendClientAiMessage(suggestion);
                });
                elements.clientAiSuggestions.appendChild(button);
            });
        } catch (error) {
            setAiFeedback(error.message, "is-error");
        }
    }

    function getClientVoiceRecognition() {
        if (!SpeechRecognitionConstructor) {
            return null;
        }

        if (clientVoiceRecognition) {
            return clientVoiceRecognition;
        }

        clientVoiceRecognition = new SpeechRecognitionConstructor();
        clientVoiceRecognition.lang = "pt-BR";
        clientVoiceRecognition.continuous = false;
        clientVoiceRecognition.interimResults = true;

        clientVoiceRecognition.onstart = () => {
            clientVoiceHadError = false;
            clientVoiceIsListening = true;
            clientVoiceTranscript = "";
            if (elements.clientAiInput) {
                elements.clientAiInput.value = "";
            }
            setAiFeedback("");
            setClientVoiceStatus("Ouvindo seu pedido...", true);
        };

        clientVoiceRecognition.onresult = (event) => {
            let interimTranscript = "";

            for (let index = event.resultIndex; index < event.results.length; index += 1) {
                const transcript = event.results[index][0]?.transcript || "";
                if (event.results[index].isFinal) {
                    clientVoiceTranscript += ` ${transcript}`;
                } else {
                    interimTranscript += transcript;
                }
            }

            const message = `${clientVoiceTranscript} ${interimTranscript}`.trim();
            if (message && elements.clientAiInput) {
                elements.clientAiInput.value = message;
            }
        };

        clientVoiceRecognition.onerror = (event) => {
            clientVoiceHadError = true;
            const message = event.error === "no-speech"
                ? "Nao ouvi nada. Tente gravar novamente ou digite o pedido."
                : "Nao consegui usar o audio agora. Digite o pedido para continuar.";
            setAiFeedback(message, "is-error");
        };

        clientVoiceRecognition.onend = () => {
            clientVoiceIsListening = false;
            setClientVoiceStatus("", false);

            if (clientVoiceHadError) {
                return;
            }

            const message = (elements.clientAiInput?.value || "").trim();
            if (!message) {
                setAiFeedback("Nao ouvi nada. Tente gravar novamente ou digite o pedido.", "is-error");
                return;
            }

            setClientVoiceStatus("Audio transcrito. Entendendo seu pedido...");
            sendClientAiMessage(message);
        };

        return clientVoiceRecognition;
    }

    function toggleClientVoiceScheduling() {
        const recognition = getClientVoiceRecognition();
        if (!recognition) {
            setAiFeedback("Agendamento por audio indisponivel neste navegador. Use a mensagem escrita.", "is-error");
            return;
        }

        if (clientVoiceIsListening) {
            recognition.stop();
            return;
        }

        try {
            recognition.start();
        } catch (_error) {
            setAiFeedback("Nao consegui iniciar o audio. Tente novamente ou use o texto.", "is-error");
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
            field.addEventListener("change", () => {
                clearHoldState();
                refreshSlots();
            });
        }
    });

    elements.hora?.addEventListener("change", () => {
        const selected = elements.hora.options[elements.hora.selectedIndex];
        if (!elements.profissional.value && selected?.dataset?.profissionalId) {
            elements.profissional.value = selected.dataset.profissionalId;
        }
        updateBookingSummary();
        reserveSelectedSlotHold();
    });

    elements.bookingForm?.addEventListener("submit", (event) => {
        if (getBookingType() !== "avulso") {
            return;
        }
        if (!elements.hora.value) {
            return;
        }
        if (elements.profissional.value && !elements.slotHoldToken?.value) {
            event.preventDefault();
            setHoldFeedback("Selecione novamente o horario para criar a reserva temporaria.", "is-error");
        }
    });

    elements.bookingTypeInputs.forEach((input) => {
        input.addEventListener("change", () => {
            clearHoldState();
            syncBookingMode();
            refreshSlots();
        });
    });

    elements.firstAvailableBtn?.addEventListener("click", loadFirstAvailableSlots);
    elements.telefone?.addEventListener("blur", lookupClientByContact);
    elements.email?.addEventListener("blur", lookupClientByContact);
    elements.clientAiSendBtn?.addEventListener("click", () => sendClientAiMessage());
    elements.clientAiVoiceBtn?.addEventListener("click", toggleClientVoiceScheduling);
    elements.clientAiInput?.addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
            event.preventDefault();
            sendClientAiMessage();
        }
    });

    if (elements.clientAiVoiceBtn && !SpeechRecognitionConstructor) {
        elements.clientAiVoiceBtn.disabled = true;
        elements.clientAiVoiceBtn.title = "Audio indisponivel neste navegador.";
        setClientVoiceStatus("Audio indisponivel neste navegador. Use a mensagem escrita.");
    }

    if (elements.servico?.value && getBookingType() === "avulso") {
        loadFirstAvailableSlots();
    }
});
