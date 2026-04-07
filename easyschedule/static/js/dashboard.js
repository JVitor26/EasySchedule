let graficoAgendamentos = null;
let graficoProfissionais = null;
let graficoServicos = null;
let graficoPrevisaoAgendamentos = null;
let graficoPrevisaoReceita = null;
let dashboardPayload = null;

const moneyFormatter = new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
});

const numberFormatter = new Intl.NumberFormat("pt-BR");
const shortDateFormatter = new Intl.DateTimeFormat("pt-BR", {
    day: "2-digit",
    month: "short",
});
const longDateFormatter = new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "long",
});
const dateTimeFormatter = new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "short",
});

function getCssValue(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function getThemePalette() {
    return {
        textPrimary: getCssValue("--text-1"),
        textSecondary: getCssValue("--text-2"),
        textMuted: getCssValue("--text-3"),
        borderSoft: getCssValue("--border-soft"),
        accent: getCssValue("--accent"),
        accent2: getCssValue("--accent-2"),
        accent3: getCssValue("--accent-3"),
        success: getCssValue("--success"),
        warning: getCssValue("--warning"),
        danger: getCssValue("--danger"),
        info: getCssValue("--info"),
        accentSoft: getCssValue("--accent-soft"),
        accentSoftStrong: getCssValue("--accent-soft-strong"),
    };
}

document.addEventListener("DOMContentLoaded", () => {
    const reportPage = document.querySelector(".report-page[data-dashboard-url]");
    if (!reportPage) {
        return;
    }

    const elements = {
        dashboardUrl: reportPage.dataset.dashboardUrl,
        visibleKpis: new Set((reportPage.dataset.visibleKpis || "").split(",").filter(Boolean)),
        dataInicio: document.getElementById("data_inicio"),
        dataFim: document.getElementById("data_fim"),
        feedback: document.getElementById("reportFeedback"),
        filterButton: document.getElementById("filtrarRelatorio"),
        clearButton: document.getElementById("limparFiltros"),
        period: document.getElementById("reportPeriod"),
        updatedAt: document.getElementById("reportUpdatedAt"),
        faturamento: document.getElementById("faturamento"),
        faturamentoAux: document.getElementById("faturamentoAux"),
        agendamentos: document.getElementById("agendamentos"),
        agendamentosAux: document.getElementById("agendamentosAux"),
        cancelamentos: document.getElementById("cancelamentos"),
        cancelamentosAux: document.getElementById("cancelamentosAux"),
        ticket: document.getElementById("ticket"),
        ticketAux: document.getElementById("ticketAux"),
        previsaoAgendamentos: document.getElementById("previsaoAgendamentos"),
        previsaoAgendamentosAux: document.getElementById("previsaoAgendamentosAux"),
        previsaoReceita: document.getElementById("previsaoReceita"),
        previsaoReceitaAux: document.getElementById("previsaoReceitaAux"),
        planosPendentes: document.getElementById("planosPendentes"),
        planosPendentesAux: document.getElementById("planosPendentesAux"),
        tabelaProfissionais: document.getElementById("tabelaProfissionais"),
        tabelaServicos: document.getElementById("tabelaServicos"),
        graficoAgendamentos: document.getElementById("graficoAgendamentos"),
        graficoProfissionais: document.getElementById("graficoProfissionais"),
        graficoServicos: document.getElementById("graficoServicos"),
        graficoPrevisaoAgendamentos: document.getElementById("graficoPrevisaoAgendamentos"),
        graficoPrevisaoReceita: document.getElementById("graficoPrevisaoReceita"),
    };

    const trackedFields = [elements.dataInicio, elements.dataFim].filter(Boolean);

    function formatCurrency(value) {
        return moneyFormatter.format(Number(value) || 0);
    }

    function formatNumber(value) {
        return numberFormatter.format(Number(value) || 0);
    }

    function parseDate(value) {
        if (!value) {
            return null;
        }

        const date = new Date(`${value}T00:00:00`);
        return Number.isNaN(date.getTime()) ? null : date;
    }

    function formatDateLabel(value) {
        const date = parseDate(value);
        return date ? shortDateFormatter.format(date) : value;
    }

    function formatSelectedPeriod() {
        const dataInicio = parseDate(elements.dataInicio.value);
        const dataFim = parseDate(elements.dataFim.value);

        if (dataInicio && dataFim) {
            return `${longDateFormatter.format(dataInicio)} a ${longDateFormatter.format(dataFim)}`;
        }

        if (dataInicio) {
            return `A partir de ${longDateFormatter.format(dataInicio)}`;
        }

        if (dataFim) {
            return `Até ${longDateFormatter.format(dataFim)}`;
        }

        return "Período completo";
    }

    function pluralize(value, singular, plural) {
        return `${formatNumber(value)} ${value === 1 ? singular : plural}`;
    }

    function setFeedback(message, state = "") {
        elements.feedback.textContent = message;
        elements.feedback.classList.remove("is-loading", "is-error");

        if (state) {
            elements.feedback.classList.add(state);
        }
    }

    function setLoadingState(isLoading) {
        elements.filterButton.disabled = isLoading;
        elements.clearButton.disabled = isLoading;
        elements.filterButton.textContent = isLoading ? "Atualizando..." : "Atualizar relatório";
    }

    function destroyChart(chart) {
        if (chart) {
            chart.destroy();
        }
        return null;
    }

    function applyKpiVisibility() {
        const cards = document.querySelectorAll(".metric-kpi[data-kpi-key]");
        if (!elements.visibleKpis.size) {
            cards.forEach((card) => {
                card.hidden = false;
            });
            return;
        }

        cards.forEach((card) => {
            const key = card.dataset.kpiKey;
            card.hidden = !elements.visibleKpis.has(key);
        });
    }

    function commonScale(axis) {
        const palette = getThemePalette();
        return {
            ticks: {
                color: palette.textMuted,
                maxRotation: axis === "x" ? 0 : undefined,
            },
            grid: {
                color: palette.borderSoft,
            },
        };
    }

    function createLineChart(labels, values) {
        const palette = getThemePalette();
        const context = elements.graficoAgendamentos.getContext("2d");
        const gradient = context.createLinearGradient(0, 0, 0, 320);
        gradient.addColorStop(0, palette.accentSoftStrong);
        gradient.addColorStop(1, "rgba(0, 0, 0, 0)");

        graficoAgendamentos = destroyChart(graficoAgendamentos);
        graficoAgendamentos = new Chart(elements.graficoAgendamentos, {
            type: "line",
            data: {
                labels,
                datasets: [{
                    label: "Agendamentos",
                    data: values,
                    borderColor: palette.accent,
                    backgroundColor: gradient,
                    fill: true,
                    borderWidth: 3,
                    tension: 0.35,
                    pointRadius: 4,
                    pointHoverRadius: 6,
                    pointBackgroundColor: palette.textPrimary,
                    pointBorderColor: palette.accent,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        labels: {
                            color: palette.textSecondary,
                        },
                    },
                },
                scales: {
                    x: commonScale("x"),
                    y: {
                        ...commonScale("y"),
                        beginAtZero: true,
                        ticks: {
                            color: palette.textMuted,
                            precision: 0,
                        },
                    },
                },
            },
        });
    }

    function createProfessionalChart(labels, values) {
        const palette = getThemePalette();
        graficoProfissionais = destroyChart(graficoProfissionais);
        graficoProfissionais = new Chart(elements.graficoProfissionais, {
            type: "bar",
            data: {
                labels,
                datasets: [{
                    label: "Faturamento",
                    data: values,
                    borderRadius: 12,
                    backgroundColor: [
                        palette.accent,
                        palette.accent2,
                        palette.accent3,
                        palette.info,
                        palette.warning,
                    ],
                }],
            },
            options: {
                indexAxis: "y",
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false,
                    },
                    tooltip: {
                        callbacks: {
                            label(context) {
                                return formatCurrency(context.raw);
                            },
                        },
                    },
                },
                scales: {
                    x: {
                        ...commonScale("x"),
                        beginAtZero: true,
                        ticks: {
                            color: palette.textMuted,
                            callback(value) {
                                return formatCurrency(value);
                            },
                        },
                    },
                    y: commonScale("y"),
                },
            },
        });
    }

    function createServicesChart(labels, values) {
        const palette = getThemePalette();
        graficoServicos = destroyChart(graficoServicos);
        graficoServicos = new Chart(elements.graficoServicos, {
            type: "doughnut",
            data: {
                labels,
                datasets: [{
                    data: values,
                    borderWidth: 0,
                    backgroundColor: [
                        palette.accent,
                        palette.accent2,
                        palette.accent3,
                        palette.info,
                        palette.warning,
                        palette.danger,
                    ],
                    hoverOffset: 8,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: "bottom",
                        labels: {
                            color: palette.textSecondary,
                            padding: 18,
                        },
                    },
                    tooltip: {
                        callbacks: {
                            label(context) {
                                const label = context.label ? `${context.label}: ` : "";
                                return `${label}${formatNumber(context.raw)} atendimentos`;
                            },
                        },
                    },
                },
                cutout: "62%",
            },
        });
    }

    function createForecastAppointmentsChart(labels, values) {
        const palette = getThemePalette();
        graficoPrevisaoAgendamentos = destroyChart(graficoPrevisaoAgendamentos);
        graficoPrevisaoAgendamentos = new Chart(elements.graficoPrevisaoAgendamentos, {
            type: "line",
            data: {
                labels,
                datasets: [{
                    label: "Previsão de agendamentos",
                    data: values,
                    borderColor: palette.info,
                    backgroundColor: palette.accentSoft,
                    fill: true,
                    borderWidth: 3,
                    tension: 0.32,
                    pointRadius: 3,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        labels: {
                            color: palette.textSecondary,
                        },
                    },
                },
                scales: {
                    x: commonScale("x"),
                    y: {
                        ...commonScale("y"),
                        beginAtZero: true,
                        ticks: {
                            color: palette.textMuted,
                            precision: 0,
                        },
                    },
                },
            },
        });
    }

    function createForecastRevenueChart(summary) {
        const palette = getThemePalette();
        graficoPrevisaoReceita = destroyChart(graficoPrevisaoReceita);
        graficoPrevisaoReceita = new Chart(elements.graficoPrevisaoReceita, {
            type: "bar",
            data: {
                labels: ["Agendamentos previstos", "Planos pendentes", "Total previsto"],
                datasets: [{
                    label: "Valor (R$)",
                    data: [
                        Number(summary.totalAgendamentosPrevistos) || 0,
                        Number(summary.totalPlanosPendentes) || 0,
                        Number(summary.totalPrevisto) || 0,
                    ],
                    borderRadius: 12,
                    backgroundColor: [palette.accent2, palette.warning, palette.success],
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false,
                    },
                    tooltip: {
                        callbacks: {
                            label(context) {
                                return formatCurrency(context.raw);
                            },
                        },
                    },
                },
                scales: {
                    x: commonScale("x"),
                    y: {
                        ...commonScale("y"),
                        beginAtZero: true,
                        ticks: {
                            color: palette.textMuted,
                            callback(value) {
                                return formatCurrency(value);
                            },
                        },
                    },
                },
            },
        });
    }

    function renderDashboard(payload) {
        if (!payload) {
            return;
        }

        dashboardPayload = payload;
        const faturamentoTotal = Number(payload.faturamento?.total) || 0;
        const totalFinalizados = Number(payload.faturamento?.quantidade) || 0;
        const totalAgendamentos = Number(payload.cancelamentos?.total) || 0;
        const totalCancelados = Number(payload.cancelamentos?.cancelados) || 0;
        const taxaCancelamento = Number(payload.cancelamentos?.taxa_cancelamento) || 0;
        const ticketMedio = totalFinalizados > 0 ? faturamentoTotal / totalFinalizados : 0;
        const previsaoAgendamentos = Array.isArray(payload.previsao_agendamentos) ? payload.previsao_agendamentos : [];
        const previsaoReceita = payload.previsao_receita || {};
        const totalPrevisaoAgendamentos = previsaoAgendamentos.reduce(
            (total, item) => total + (Number(item.total) || 0),
            0
        );
        const totalAgendamentosPrevistosValor = Number(previsaoReceita.total_agendamentos_previstos) || 0;
        const totalPlanosPendentes = Number(previsaoReceita.total_planos_pendentes) || 0;
        const totalPrevisto = Number(previsaoReceita.total_previsto) || 0;

        elements.faturamento.textContent = formatCurrency(faturamentoTotal);
        elements.faturamentoAux.textContent = pluralize(
            totalFinalizados,
            "atendimento finalizado",
            "atendimentos finalizados"
        );

        elements.agendamentos.textContent = formatNumber(totalAgendamentos);
        elements.agendamentosAux.textContent = pluralize(
            totalAgendamentos,
            "registro no período",
            "registros no período"
        );

        elements.cancelamentos.textContent = `${taxaCancelamento.toFixed(2)}%`;
        elements.cancelamentosAux.textContent = `${pluralize(
            totalCancelados,
            "cancelamento",
            "cancelamentos"
        )} no período`;

        elements.ticket.textContent = formatCurrency(ticketMedio);
        elements.ticketAux.textContent = totalFinalizados > 0
            ? "Média por atendimento finalizado"
            : "Sem atendimentos finalizados no período";

        elements.previsaoAgendamentos.textContent = formatNumber(totalPrevisaoAgendamentos);
        elements.previsaoAgendamentosAux.textContent = pluralize(
            totalPrevisaoAgendamentos,
            "agendamento previsto",
            "agendamentos previstos"
        );

        elements.previsaoReceita.textContent = formatCurrency(totalPrevisto);
        elements.previsaoReceitaAux.textContent =
            `${formatCurrency(totalAgendamentosPrevistosValor)} em agenda + ${formatCurrency(totalPlanosPendentes)} em planos pendentes`;

        elements.planosPendentes.textContent = formatCurrency(totalPlanosPendentes);
        elements.planosPendentesAux.textContent =
            totalPlanosPendentes > 0
                ? "Existe previsão de receita ainda não paga em planos"
                : "Nenhum plano pendente de pagamento no período";

        const agendamentos = Array.isArray(payload.agendamentos) ? payload.agendamentos : [];
        const profissionais = Array.isArray(payload.profissionais) ? payload.profissionais : [];
        const servicos = Array.isArray(payload.servicos) ? payload.servicos : [];

        createLineChart(
            agendamentos.map((item) => formatDateLabel(item.data)),
            agendamentos.map((item) => Number(item.total) || 0)
        );

        createProfessionalChart(
            profissionais.map((item) => item.profissional__nome || "Sem nome"),
            profissionais.map((item) => Number(item.faturamento) || 0)
        );

        createServicesChart(
            servicos.map((item) => item.servico__nome || "Sem nome"),
            servicos.map((item) => Number(item.total) || 0)
        );

        createForecastAppointmentsChart(
            previsaoAgendamentos.map((item) => formatDateLabel(item.data)),
            previsaoAgendamentos.map((item) => Number(item.total) || 0)
        );

        createForecastRevenueChart({
            totalAgendamentosPrevistos: totalAgendamentosPrevistosValor,
            totalPlanosPendentes,
            totalPrevisto,
        });

        renderProfessionalsTable(profissionais);
        renderServicesTable(servicos);

        elements.updatedAt.textContent = `Atualizado em ${dateTimeFormatter.format(new Date())}`;

        if (totalAgendamentos > 0) {
            setFeedback(
                `Indicadores atualizados com base em ${pluralize(totalAgendamentos, "registro", "registros")}.`
            );
        } else {
            setFeedback("Nenhum registro encontrado para o período informado.");
        }
    }

    function createCell(text, className = "") {
        const cell = document.createElement("td");
        cell.textContent = text;
        if (className) {
            cell.className = className;
        }
        return cell;
    }

    function renderEmptyRow(tbody, columns, message) {
        tbody.innerHTML = "";
        const row = document.createElement("tr");
        const cell = document.createElement("td");
        cell.colSpan = columns;
        cell.className = "report-empty";
        cell.textContent = message;
        row.appendChild(cell);
        tbody.appendChild(row);
    }

    function renderProfessionalsTable(items) {
        if (!items.length) {
            renderEmptyRow(elements.tabelaProfissionais, 3, "Nenhum profissional com faturamento no período.");
            return;
        }

        elements.tabelaProfissionais.innerHTML = "";

        items.forEach((item) => {
            const row = document.createElement("tr");
            row.appendChild(createCell(item.profissional__nome || "Sem nome"));
            row.appendChild(createCell(formatNumber(item.total)));
            row.appendChild(createCell(formatCurrency(item.faturamento)));
            elements.tabelaProfissionais.appendChild(row);
        });
    }

    function renderServicesTable(items) {
        if (!items.length) {
            renderEmptyRow(elements.tabelaServicos, 3, "Nenhum serviço finalizado no período.");
            return;
        }

        elements.tabelaServicos.innerHTML = "";

        items.forEach((item) => {
            const row = document.createElement("tr");
            row.appendChild(createCell(item.servico__nome || "Sem nome"));
            row.appendChild(createCell(formatNumber(item.total)));
            row.appendChild(createCell(formatCurrency(item.faturamento)));
            elements.tabelaServicos.appendChild(row);
        });
    }

    async function carregarDashboard() {
        const url = new URL(elements.dashboardUrl, window.location.origin);

        if (elements.dataInicio.value) {
            url.searchParams.set("data_inicio", elements.dataInicio.value);
        }

        if (elements.dataFim.value) {
            url.searchParams.set("data_fim", elements.dataFim.value);
        }

        elements.period.textContent = formatSelectedPeriod();
        setLoadingState(true);
        setFeedback("Atualizando indicadores...", "is-loading");

        try {
            const response = await fetch(url.toString(), {
                headers: {
                    "X-Requested-With": "XMLHttpRequest",
                },
            });

            if (!response.ok) {
                throw new Error("Não foi possível carregar o relatório.");
            }

            renderDashboard(await response.json());
        } catch (error) {
            graficoAgendamentos = destroyChart(graficoAgendamentos);
            graficoProfissionais = destroyChart(graficoProfissionais);
            graficoServicos = destroyChart(graficoServicos);
            graficoPrevisaoAgendamentos = destroyChart(graficoPrevisaoAgendamentos);
            graficoPrevisaoReceita = destroyChart(graficoPrevisaoReceita);

            renderEmptyRow(elements.tabelaProfissionais, 3, "Não foi possível carregar os dados.");
            renderEmptyRow(elements.tabelaServicos, 3, "Não foi possível carregar os dados.");
            elements.updatedAt.textContent = "Falha ao atualizar";
            setFeedback(error.message, "is-error");
        } finally {
            setLoadingState(false);
        }
    }

    elements.filterButton.addEventListener("click", carregarDashboard);
    elements.clearButton.addEventListener("click", () => {
        elements.dataInicio.value = "";
        elements.dataFim.value = "";
        carregarDashboard();
    });

    trackedFields.forEach((field) => {
        field.addEventListener("keydown", (event) => {
            if (event.key === "Enter") {
                carregarDashboard();
            }
        });
    });

    document.addEventListener("themechange", () => {
        if (dashboardPayload) {
            renderDashboard(dashboardPayload);
        }
    });

    applyKpiVisibility();
    carregarDashboard();
});
