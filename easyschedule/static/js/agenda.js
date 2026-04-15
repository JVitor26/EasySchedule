document.addEventListener("DOMContentLoaded", () => {
    const agendaPage = document.querySelector(".agenda-page[data-events-url]");
    if (!agendaPage) {
        return;
    }

    const hasFullCalendar = typeof window.FullCalendar !== "undefined";
    if (!hasFullCalendar) {
        const calendarEl = document.getElementById("calendar");
        if (calendarEl) {
            calendarEl.innerHTML =
                '<p style="padding:2rem;text-align:center;color:var(--color-text-muted,#888);">' +
                "Não foi possível carregar o calendário. Verifique sua conexão e recarregue a página." +
                "</p>";
        }
    }

    const eventsUrl = agendaPage.dataset.eventsUrl;
    const moveUrlTemplate = agendaPage.dataset.moveUrlTemplate;
    const editUrlTemplate = agendaPage.dataset.editUrlTemplate;
    const statusUrlTemplate = agendaPage.dataset.statusUrlTemplate;
    const remindersUrl = agendaPage.dataset.remindersUrl;
    const reengagementUrl = agendaPage.dataset.reengagementUrl;
    const aiChatUrl = agendaPage.dataset.aiChatUrl;
    const SpeechRecognitionConstructor = window.SpeechRecognition || window.webkitSpeechRecognition;

    const STATUS_TRANSITIONS = {
        pendente: ["confirmado", "cancelado"],
        confirmado: ["finalizado", "cancelado", "no_show"],
        finalizado: [],
        cancelado: [],
        no_show: [],
    };

    const elements = {
        filtroTipo: document.getElementById("agendaFiltroTipo"),
        filtroProfissional: document.getElementById("agendaFiltroProfissional"),
        filtroStatus: document.getElementById("agendaFiltroStatus"),
        limparFiltros: document.getElementById("agendaLimparFiltros"),
        feedback: document.getElementById("agendaFeedback"),
        modal: document.getElementById("modalEvento"),
        modalTitle: document.getElementById("agendaModalTitle"),
        modalCliente: document.getElementById("modalCliente"),
        modalProfissional: document.getElementById("modalProfissional"),
        modalItemLabel: document.getElementById("modalItemLabel"),
        modalServico: document.getElementById("modalServico"),
        modalValor: document.getElementById("modalValor"),
        modalStatus: document.getElementById("modalStatus"),
        modalTelefone: document.getElementById("modalTelefone"),
        modalCadastroStatus: document.getElementById("modalCadastroStatus"),
        modalObservacoes: document.getElementById("modalObservacoes"),
        modalEditarLink: document.getElementById("modalEditarLink"),
        fecharModal: document.getElementById("fecharModal"),
        modalFecharAcao: document.getElementById("modalFecharAcao"),
        calendar: document.getElementById("calendar"),
        campaignFeedback: document.getElementById("campaignFeedback"),
        dispararReengajamentoBtn: document.getElementById("dispararReengajamentoBtn"),
        aiChatPhone: document.getElementById("aiChatPhone"),
        aiChatInput: document.getElementById("aiChatInput"),
        aiChatSendBtn: document.getElementById("aiChatSendBtn"),
        aiChatVoiceBtn: document.getElementById("aiChatVoiceBtn"),
        aiChatVoiceStatus: document.getElementById("aiChatVoiceStatus"),
        aiChatFeedback: document.getElementById("aiChatFeedback"),
        aiChatMessages: document.getElementById("aiChatMessages"),
        aiChatSuggestions: document.getElementById("aiChatSuggestions"),
        aiClientInfo: document.getElementById("aiClientInfo"),
    };

    const moneyFormatter = new Intl.NumberFormat("pt-BR", {
        style: "currency",
        currency: "BRL",
    });

    function setFeedback(message, state = "") {
        elements.feedback.textContent = message;
        elements.feedback.classList.remove("is-loading", "is-error", "is-success");

        if (state) {
            elements.feedback.classList.add(state);
        }
    }

    function setCampaignFeedback(message, state = "") {
        if (!elements.campaignFeedback) {
            return;
        }
        elements.campaignFeedback.textContent = message;
        elements.campaignFeedback.classList.remove("is-loading", "is-error", "is-success");
        if (state) {
            elements.campaignFeedback.classList.add(state);
        }
    }

    function setAiFeedback(message, state = "") {
        if (!elements.aiChatFeedback) return;
        elements.aiChatFeedback.textContent = message || "";
        elements.aiChatFeedback.classList.remove("is-loading", "is-error", "is-success");
        if (state) elements.aiChatFeedback.classList.add(state);
    }

    function appendAiMessage(text, role) {
        if (!elements.aiChatMessages) return;
        const node = document.createElement("div");
        node.className = `ai-chat-message ${role}`;
        node.textContent = text;
        elements.aiChatMessages.appendChild(node);
        elements.aiChatMessages.scrollTop = elements.aiChatMessages.scrollHeight;
    }

    function renderClientInfo(info) {
        if (!elements.aiClientInfo || !info || !info.telefone) {
            if (elements.aiClientInfo) {
                elements.aiClientInfo.hidden = true;
                elements.aiClientInfo.textContent = "";
            }
            return;
        }

        const pending = info.campos_pendentes || [];
        elements.aiClientInfo.hidden = false;
        elements.aiClientInfo.classList.toggle("is-missing", !info.cadastrado || pending.length > 0);
        elements.aiClientInfo.textContent = "";

        const title = document.createElement("strong");
        const detail = document.createElement("span");

        if (info.cadastrado) {
            const pendingText = pending.length ? `Pendencias: ${pending.join(", ")}.` : "Cadastro completo.";
            title.textContent = `Cliente encontrado: ${info.nome}`;
            detail.textContent = pendingText;
        } else {
            title.textContent = "Cliente nao cadastrado";
            detail.textContent = "O horario sera criado como pendente para completar o cadastro antes da confirmacao.";
        }

        elements.aiClientInfo.appendChild(title);
        elements.aiClientInfo.appendChild(detail);
    }

    let aiContext = {};
    let voiceRecognition = null;
    let voiceIsListening = false;
    let voiceHadError = false;
    let voiceTranscript = "";

    function setVoiceStatus(message = "", isListening = false) {
        if (elements.aiChatVoiceStatus) {
            elements.aiChatVoiceStatus.textContent = message;
        }
        if (elements.aiChatVoiceBtn) {
            elements.aiChatVoiceBtn.textContent = isListening ? "Parar audio" : "Gravar audio";
            elements.aiChatVoiceBtn.setAttribute("aria-pressed", isListening ? "true" : "false");
            elements.aiChatVoiceBtn.classList.toggle("is-listening", isListening);
        }
    }

    function renderAiSuggestions(suggestions) {
        if (!elements.aiChatSuggestions) return;
        elements.aiChatSuggestions.innerHTML = "";
        (suggestions || []).slice(0, 8).forEach((item) => {
            const btn = document.createElement("button");
            btn.type = "button";
            btn.className = "ai-chat-suggestion";
            btn.textContent = item;
            btn.addEventListener("click", () => {
                if (elements.aiChatInput) elements.aiChatInput.value = item;
                sendAiMessage();
            });
            elements.aiChatSuggestions.appendChild(btn);
        });
    }

    function getVoiceRecognition() {
        if (!SpeechRecognitionConstructor) {
            return null;
        }

        if (voiceRecognition) {
            return voiceRecognition;
        }

        voiceRecognition = new SpeechRecognitionConstructor();
        voiceRecognition.lang = "pt-BR";
        voiceRecognition.continuous = false;
        voiceRecognition.interimResults = true;

        voiceRecognition.onstart = () => {
            voiceHadError = false;
            voiceIsListening = true;
            voiceTranscript = "";
            if (elements.aiChatInput) {
                elements.aiChatInput.value = "";
            }
            setAiFeedback("");
            setVoiceStatus("Ouvindo o pedido do cliente...", true);
        };

        voiceRecognition.onresult = (event) => {
            let interimTranscript = "";

            for (let index = event.resultIndex; index < event.results.length; index += 1) {
                const transcript = event.results[index][0]?.transcript || "";
                if (event.results[index].isFinal) {
                    voiceTranscript += ` ${transcript}`;
                } else {
                    interimTranscript += transcript;
                }
            }

            const message = `${voiceTranscript} ${interimTranscript}`.trim();
            if (message && elements.aiChatInput) {
                elements.aiChatInput.value = message;
            }
        };

        voiceRecognition.onerror = (event) => {
            voiceHadError = true;
            const message = event.error === "no-speech"
                ? "Nao ouvi nada. Tente gravar novamente ou digite o pedido."
                : "Nao consegui usar o audio agora. Digite o pedido para continuar.";
            setAiFeedback(message, "is-error");
        };

        voiceRecognition.onend = () => {
            voiceIsListening = false;
            setVoiceStatus("", false);

            if (voiceHadError) {
                return;
            }

            const message = (elements.aiChatInput?.value || "").trim();
            if (!message) {
                setAiFeedback("Nao ouvi nada. Tente gravar novamente ou digite o pedido.", "is-error");
                return;
            }

            setVoiceStatus("Audio transcrito. Enviando para a IA...");
            sendAiMessage();
        };

        return voiceRecognition;
    }

    function toggleVoiceScheduling() {
        const recognition = getVoiceRecognition();
        if (!recognition) {
            setAiFeedback("Agendamento por audio indisponivel neste navegador. Use a mensagem escrita.", "is-error");
            return;
        }

        if (voiceIsListening) {
            recognition.stop();
            return;
        }

        try {
            recognition.start();
        } catch (error) {
            setAiFeedback("Nao consegui iniciar o audio. Tente novamente ou use o texto.", "is-error");
        }
    }

    let calendar = null;

    async function sendAiMessage() {
        if (!aiChatUrl) return;
        const telefone = (elements.aiChatPhone?.value || "").trim();
        const mensagem = (elements.aiChatInput?.value || "").trim();
        if (!mensagem) return;

        appendAiMessage(mensagem, "user");
        if (elements.aiChatInput) elements.aiChatInput.value = "";
        setAiFeedback("IA consultando horarios...", "is-loading");

        try {
            const response = await fetch(aiChatUrl, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": getCookie("csrftoken"),
                    "X-Requested-With": "XMLHttpRequest",
                },
                body: JSON.stringify({ telefone, mensagem, contexto: aiContext }),
            });
            const payload = await response.json();
            if (!response.ok || payload.status !== "sucesso") {
                throw new Error(payload.message || "Falha ao falar com a IA.");
            }
            aiContext = payload.contexto || {};
            if (payload.telefone && elements.aiChatPhone) {
                elements.aiChatPhone.value = payload.telefone;
            }
            renderClientInfo(payload.cliente_info);
            appendAiMessage(payload.resposta || "Sem resposta da IA.", "bot");
            renderAiSuggestions(payload.sugestoes || []);
            if (payload.agendamento_id) {
                setAiFeedback("Agendamento criado com sucesso pela IA.", "is-success");
                calendar?.refetchEvents();
            } else if (payload.acao === "sem_horario" || payload.acao === "horario_indisponivel") {
                setAiFeedback("A IA nao conseguiu concluir. Use o cadastro detalhado se precisar de mais campos.", "is-error");
            } else {
                setAiFeedback("");
            }
        } catch (error) {
            setAiFeedback(error.message, "is-error");
        }
    }

    function buildUrl(baseUrl, params = {}) {
        const url = new URL(baseUrl, window.location.origin);
        Object.entries(params).forEach(([key, value]) => {
            if (value) {
                url.searchParams.set(key, value);
            }
        });
        return url;
    }

    function getCookie(name) {
        const cookie = document.cookie
            .split(";")
            .map((item) => item.trim())
            .find((item) => item.startsWith(`${name}=`));

        return cookie ? decodeURIComponent(cookie.split("=")[1]) : "";
    }

    function replaceTemplateId(urlTemplate, id) {
        return urlTemplate.replace("999999", String(id));
    }

    function isMobileViewport() {
        return window.matchMedia("(max-width: 768px)").matches;
    }

    function mobileCalendarView() {
        return window.matchMedia("(max-width: 480px)").matches ? "listWeek" : "timeGridDay";
    }

    function formatDateForAi(date) {
        const day = String(date.getDate()).padStart(2, "0");
        const month = String(date.getMonth() + 1).padStart(2, "0");
        return `${day}/${month}/${date.getFullYear()}`;
    }

    function formatTimeForAi(date) {
        return `${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
    }

    function startAiSchedulingFromCalendar(date, dateOnly = false) {
        if (!elements.aiChatInput) {
            return;
        }

        const timeText = dateOnly ? "" : ` as ${formatTimeForAi(date)}`;
        elements.aiChatInput.value = `Quero agendar para ${formatDateForAi(date)}${timeText}`;
        document.getElementById("assistenteAgendamento")?.scrollIntoView({
            behavior: "smooth",
            block: "start",
        });
        elements.aiChatInput.focus();
        setAiFeedback("Complete o pedido por texto ou grave o restante em audio.");
    }

    function getHeaderToolbar() {
        if (isMobileViewport()) {
            return {
                left: "prev,next",
                center: "title",
                right: "today",
            };
        }

        return {
            left: "prev,next today",
            center: "title",
            right: "dayGridMonth,timeGridWeek,timeGridDay,listWeek",
        };
    }

    function applyResponsiveCalendarLayout(calendar) {
        const mobile = isMobileViewport();
        calendar.setOption("headerToolbar", getHeaderToolbar());
        calendar.setOption("eventMaxStack", mobile ? 2 : 5);
        calendar.setOption("dayMaxEventRows", mobile ? 3 : true);

        const currentView = calendar.view.type;
        if (mobile && currentView === "timeGridWeek") {
            calendar.changeView(mobileCalendarView());
        }
        if (!mobile && (currentView === "timeGridDay" || currentView === "listWeek")) {
            calendar.changeView("timeGridWeek");
        }
    }

    function fillModal(event) {
        const props = event.extendedProps || {};
        const isProductEvent = props.tipo_evento === "produto" || props.is_product_event;

        elements.modalTitle.textContent = event.title;
        elements.modalCliente.textContent = props.cliente || "-";
        elements.modalProfissional.textContent = props.profissional || "-";
        elements.modalItemLabel.textContent = isProductEvent ? "Produto" : "Servico";
        elements.modalServico.textContent = props.servico || "-";
        elements.modalValor.textContent = moneyFormatter.format(Number(props.valor) || 0);
        elements.modalStatus.textContent = props.status_label || "-";
        elements.modalTelefone.textContent = props.telefone || "-";
        if (elements.modalCadastroStatus) {
            const camposPendentes = props.campos_cadastro_pendentes || [];
            elements.modalCadastroStatus.textContent = props.cadastro_incompleto
                ? `Pendente: ${camposPendentes.join(", ")}`
                : "Completo";
        }
        elements.modalObservacoes.textContent = props.observacoes || "Sem observacoes informadas.";
        if (isProductEvent) {
            elements.modalEditarLink.style.display = "none";
        } else {
            elements.modalEditarLink.style.display = "";
            elements.modalEditarLink.href = replaceTemplateId(editUrlTemplate, event.id);
        }

        const allowed = STATUS_TRANSITIONS[props.status] || [];
        document.querySelectorAll(".agenda-status-btn").forEach((btn) => {
            if (isProductEvent) {
                btn.style.display = "none";
            } else {
                btn.style.display = allowed.includes(btn.dataset.status) ? "" : "none";
            }
            btn.dataset.eventId = event.id;
        });
    }

    function openModal(event) {
        fillModal(event);
        elements.modal.hidden = false;
    }

    function closeModal() {
        elements.modal.hidden = true;
    }

    if (hasFullCalendar && elements.calendar) {
        calendar = new FullCalendar.Calendar(elements.calendar, {
            initialView: isMobileViewport() ? mobileCalendarView() : "timeGridWeek",
            locale: "pt-br",
            editable: true,
            selectable: true,
            nowIndicator: true,
            height: "auto",
            slotMinTime: "06:00:00",
            slotMaxTime: "22:00:00",
            allDaySlot: false,
            headerToolbar: getHeaderToolbar(),
            buttonText: {
                today: "Hoje",
                month: "Mes",
                week: "Semana",
                day: "Dia",
                list: "Lista",
            },
            eventTimeFormat: {
                hour: "2-digit",
                minute: "2-digit",
                meridiem: false,
            },
            loading(isLoading) {
                if (isLoading) {
                    setFeedback("Carregando calendario...", "is-loading");
                }
            },
            events(fetchInfo, successCallback, failureCallback) {
                const url = buildUrl(eventsUrl, {
                    start: fetchInfo.startStr,
                    end: fetchInfo.endStr,
                    tipo_evento: elements.filtroTipo.value,
                    profissional: elements.filtroProfissional.value,
                    status: elements.filtroStatus.value,
                });

                fetch(url.toString(), {
                    headers: {
                        "X-Requested-With": "XMLHttpRequest",
                    },
                })
                    .then((response) => {
                        if (!response.ok) {
                            throw new Error("Nao foi possivel carregar a agenda.");
                        }

                        return response.json();
                    })
                    .then((data) => {
                        successCallback(data);

                        if (data.length) {
                            setFeedback(`${data.length} evento(s) exibido(s) no calendario.`);
                        } else {
                            setFeedback("Nenhum evento encontrado para os filtros selecionados.");
                        }
                    })
                    .catch((error) => {
                        setFeedback(error.message, "is-error");
                        failureCallback(error);
                    });
            },
            eventClick(info) {
                openModal(info.event);
            },
            dateClick(info) {
                startAiSchedulingFromCalendar(info.date, info.allDay || info.view.type === "dayGridMonth");
            },
            async eventDrop(info) {
                const props = info.event.extendedProps || {};
                if (props.tipo_evento === "produto" || props.is_product_event) {
                    info.revert();
                    setFeedback("Eventos de produto nao podem ser arrastados no calendario.", "is-error");
                    return;
                }

                const moveUrl = replaceTemplateId(moveUrlTemplate, info.event.id);

                setFeedback("Atualizando horario do agendamento...", "is-loading");

                try {
                    const response = await fetch(moveUrl, {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json",
                            "X-CSRFToken": getCookie("csrftoken"),
                            "X-Requested-With": "XMLHttpRequest",
                        },
                        body: JSON.stringify({
                            data: info.event.start ? info.event.start.toISOString() : "",
                        }),
                    });

                    const payload = await response.json();
                    if (!response.ok || payload.status !== "ok") {
                        throw new Error(payload.mensagem || "Nao foi possivel mover o agendamento.");
                    }

                    setFeedback("Agendamento atualizado com sucesso.", "is-success");
                } catch (error) {
                    info.revert();
                    setFeedback(error.message, "is-error");
                }
            },
        });

        calendar.render();
        applyResponsiveCalendarLayout(calendar);

        let lastWasMobile = isMobileViewport();
        window.addEventListener("resize", () => {
            const currentMobile = isMobileViewport();
            if (currentMobile !== lastWasMobile) {
                applyResponsiveCalendarLayout(calendar);
                lastWasMobile = currentMobile;
            }
        });
    }

    [elements.filtroTipo, elements.filtroProfissional, elements.filtroStatus].forEach((field) => {
        field.addEventListener("change", () => {
            calendar?.refetchEvents();
        });
    });

    elements.limparFiltros.addEventListener("click", () => {
        elements.filtroTipo.value = "geral";
        elements.filtroProfissional.value = "";
        elements.filtroStatus.value = "";
        calendar?.refetchEvents();
    });

    [elements.fecharModal, elements.modalFecharAcao].forEach((button) => {
        button.addEventListener("click", closeModal);
    });

    document.querySelectorAll(".agenda-status-btn").forEach((btn) => {
        btn.addEventListener("click", async () => {
            const eventId = btn.dataset.eventId;
            const novoStatus = btn.dataset.status;
            if (!eventId || !novoStatus) return;

            setFeedback("Atualizando status...", "is-loading");

            try {
                const response = await fetch(replaceTemplateId(statusUrlTemplate, eventId), {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRFToken": getCookie("csrftoken"),
                        "X-Requested-With": "XMLHttpRequest",
                    },
                    body: JSON.stringify({ status: novoStatus }),
                });

                const payload = await response.json();
                if (payload.requires_review && payload.review_url) {
                    setFeedback(payload.mensagem || "Complete os dados do cliente antes de confirmar.", "is-error");
                    window.location.href = payload.review_url;
                    return;
                }

                if (!response.ok || payload.status !== "ok") {
                    throw new Error(payload.mensagem || "Erro ao atualizar status.");
                }

                setFeedback(`Status atualizado para "${payload.novo_status_label}".`, "is-success");
                closeModal();
                calendar?.refetchEvents();
            } catch (error) {
                setFeedback(error.message, "is-error");
            }
        });
    });

    elements.modal.addEventListener("click", (event) => {
        if (event.target.dataset.closeModal === "true") {
            closeModal();
        }
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && !elements.modal.hidden) {
            closeModal();
        }
    });

    elements.dispararReengajamentoBtn?.addEventListener("click", async () => {
        if (!reengagementUrl) {
            return;
        }

        setCampaignFeedback("Disparando campanha de reengajamento...", "is-loading");
        try {
            const response = await fetch(reengagementUrl, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": getCookie("csrftoken"),
                    "X-Requested-With": "XMLHttpRequest",
                },
                body: JSON.stringify({}),
            });
            const payload = await response.json();
            if (!response.ok || payload.status !== "sucesso") {
                throw new Error(payload.message || "Falha ao disparar campanha.");
            }
            setCampaignFeedback(payload.message || "Campanha disparada com sucesso.", "is-success");
        } catch (error) {
            setCampaignFeedback(error.message, "is-error");
        }
    });

    elements.aiChatSendBtn?.addEventListener("click", sendAiMessage);
    elements.aiChatVoiceBtn?.addEventListener("click", toggleVoiceScheduling);
    elements.aiChatInput?.addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
            event.preventDefault();
            sendAiMessage();
        }
    });

    if (elements.aiChatVoiceBtn && !SpeechRecognitionConstructor) {
        elements.aiChatVoiceBtn.disabled = true;
        elements.aiChatVoiceBtn.title = "Audio indisponivel neste navegador.";
        setVoiceStatus("Audio indisponivel neste navegador. Use a mensagem escrita.");
    }
});
