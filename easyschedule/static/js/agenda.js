document.addEventListener("DOMContentLoaded", () => {
    const agendaPage = document.querySelector(".agenda-page[data-events-url]");
    if (!agendaPage) {
        return;
    }

    const eventsUrl = agendaPage.dataset.eventsUrl;
    const moveUrlTemplate = agendaPage.dataset.moveUrlTemplate;
    const editUrlTemplate = agendaPage.dataset.editUrlTemplate;

    const elements = {
        filtroProfissional: document.getElementById("agendaFiltroProfissional"),
        filtroStatus: document.getElementById("agendaFiltroStatus"),
        limparFiltros: document.getElementById("agendaLimparFiltros"),
        feedback: document.getElementById("agendaFeedback"),
        modal: document.getElementById("modalEvento"),
        modalTitle: document.getElementById("agendaModalTitle"),
        modalCliente: document.getElementById("modalCliente"),
        modalProfissional: document.getElementById("modalProfissional"),
        modalServico: document.getElementById("modalServico"),
        modalValor: document.getElementById("modalValor"),
        modalStatus: document.getElementById("modalStatus"),
        modalTelefone: document.getElementById("modalTelefone"),
        modalObservacoes: document.getElementById("modalObservacoes"),
        modalEditarLink: document.getElementById("modalEditarLink"),
        fecharModal: document.getElementById("fecharModal"),
        modalFecharAcao: document.getElementById("modalFecharAcao"),
        calendar: document.getElementById("calendar"),
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

    function fillModal(event) {
        const props = event.extendedProps || {};

        elements.modalTitle.textContent = event.title;
        elements.modalCliente.textContent = props.cliente || "-";
        elements.modalProfissional.textContent = props.profissional || "-";
        elements.modalServico.textContent = props.servico || "-";
        elements.modalValor.textContent = moneyFormatter.format(Number(props.valor) || 0);
        elements.modalStatus.textContent = props.status_label || "-";
        elements.modalTelefone.textContent = props.telefone || "-";
        elements.modalObservacoes.textContent = props.observacoes || "Sem observacoes informadas.";
        elements.modalEditarLink.href = replaceTemplateId(editUrlTemplate, event.id);
    }

    function openModal(event) {
        fillModal(event);
        elements.modal.hidden = false;
    }

    function closeModal() {
        elements.modal.hidden = true;
    }

    const calendar = new FullCalendar.Calendar(elements.calendar, {
        initialView: "timeGridWeek",
        locale: "pt-br",
        editable: true,
        nowIndicator: true,
        height: "auto",
        slotMinTime: "06:00:00",
        slotMaxTime: "22:00:00",
        allDaySlot: false,
        headerToolbar: {
            left: "prev,next today",
            center: "title",
            right: "dayGridMonth,timeGridWeek,timeGridDay,listWeek",
        },
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
                        setFeedback(`${data.length} agendamentos exibidos no calendario.`);
                    } else {
                        setFeedback("Nenhum agendamento encontrado para os filtros selecionados.");
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
        async eventDrop(info) {
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

    [elements.filtroProfissional, elements.filtroStatus].forEach((field) => {
        field.addEventListener("change", () => {
            calendar.refetchEvents();
        });
    });

    elements.limparFiltros.addEventListener("click", () => {
        elements.filtroProfissional.value = "";
        elements.filtroStatus.value = "";
        calendar.refetchEvents();
    });

    [elements.fecharModal, elements.modalFecharAcao].forEach((button) => {
        button.addEventListener("click", closeModal);
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
});
