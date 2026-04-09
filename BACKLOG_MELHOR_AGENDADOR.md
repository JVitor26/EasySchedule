# Backlog Priorizado para virar o melhor agendador

Data base: 2026-04-09
Escopo: EasySchedule (Django multiempresa, agenda publica, pagamento, plano mensal, produtos)

## Status de execucao (entrega atual)

- Concluido: ES-P0-001 (health/readiness)
- Concluido: ES-P0-002 (correlation id e logging)
- Concluido: ES-P0-003 base (Sentry opcional por ambiente)
- Concluido: ES-P0-004 base (webhook Stripe com assinatura e idempotencia por event_id)
- Concluido: ES-P0-007 base (hold temporario de horario com TTL e feedback no portal)
- Concluido: ES-P0-008 base (lock transacional por profissional/data para reduzir corrida)
- Concluido: estabilizacao da suite de testes e alinhamento de templates com o dominio atual

## 1) North Star e metas de produto

North Star Metric (NSM): agendamentos concluidos por empresa por semana.

Metas de 12 meses:
- Uptime >= 99.95%
- Tempo medio para concluir agendamento <= 45s no mobile
- Conversao visita -> agendamento >= 35%
- No-show <= 8%
- Reagendamento concluido em <= 2 cliques
- NPS >= 70

## 2) Principios para priorizar

- Regra 1: confiabilidade antes de novas features.
- Regra 2: toda feature precisa impactar KPI medido.
- Regra 3: automacao para reduzir trabalho manual da empresa.
- Regra 4: experiencia mobile-first sem friccao.
- Regra 5: seguranca e idempotencia em pagamentos e webhooks.

## 3) Epicos priorizados (90 dias)

| ID | Epico | Prioridade | Impacto | Esforco | KPI principal |
|---|---|---|---|---|---|
| E1 | Confiabilidade e Observabilidade | P0 | Muito alto | Medio | Uptime, erro 5xx |
| E2 | Motor de agenda sem conflito | P0 | Muito alto | Medio | Conflito de agenda, sucesso na reserva |
| E3 | Conversao no agendamento publico | P0 | Alto | Medio | Conversao visita -> reserva |
| E4 | Anti no-show e retencao | P0 | Alto | Medio | No-show, comparecimento |
| E5 | Pagamentos Stripe robustos | P0 | Alto | Medio | Conversao pagamento, falhas webhook |
| E6 | Inteligencia de horarios | P1 | Alto | Alto | Taxa de comparecimento |
| E7 | Integracoes de ecossistema | P1 | Medio | Medio | Ativacao e retencao |
| E8 | BI operacional para empresa | P1 | Medio | Medio | Receita e ocupacao |

## 4) Roadmap de 90 dias (6 sprints)

Sprint 1 (semanas 1-2):
- E1: health checks, logging estruturado, erro tracking
- E2: lock de reserva de horario, indice e validacao forte
- E5: idempotencia basica no webhook Stripe

Sprint 2 (semanas 3-4):
- E1: alertas e SLO
- E3: simplificacao do fluxo publico (menos campos)
- E4: lembrete automatico D-1 e H-2

Sprint 3 (semanas 5-6):
- E2: hold temporario de slot com expiracao
- E5: reconciliacao automatica de pagamentos pendentes
- E3: acompanhamento de funil completo

Sprint 4 (semanas 7-8):
- E4: confirmacao de presenca com 1 toque
- E4: lista de espera com preenchimento automatico
- E8: dashboard de no-show, ocupacao e receita

Sprint 5 (semanas 9-10):
- E6: score simples de risco de no-show por agendamento
- E6: sugestao de melhor horario para cliente
- E7: sincronizacao com Google Calendar

Sprint 6 (semanas 11-12):
- E7: webhook/integ WhatsApp provider resiliente
- E8: benchmark por empresa (dia, profissional, servico)
- Hardening final, testes E2E e preparacao de lancamento

## 5) Backlog detalhado (top itens P0)

### ES-P0-001 - Health endpoints e readiness
Objetivo:
- Expor /healthz e /readyz para monitorar aplicacao e dependencias.

Criterios de aceite:
- /healthz responde 200 com status basico da app.
- /readyz valida DB e retorna 503 quando dependencia critica falhar.
- Endpoint sem dados sensiveis.

Impacto esperado:
- Detectar incidentes mais rapido e reduzir downtime.

### ES-P0-002 - Logging estruturado com request_id
Objetivo:
- Padronizar logs JSON com request_id por requisicao.

Criterios de aceite:
- Toda request HTTP recebe correlation id.
- Logs de erro, pagamento e agendamento incluem request_id, empresa_id e objeto_id.
- Busca de incidente por request_id em menos de 2 minutos.

Impacto esperado:
- Acelera diagnostico de bugs e falhas de pagamento.

### ES-P0-003 - Error tracking e alertas
Objetivo:
- Capturar excecoes em producao e alertar time automaticamente.

Criterios de aceite:
- Erros nao tratados chegam em painel de monitoramento.
- Alertas para taxa de erro acima do limite por 5 minutos.
- Runbook curto para top 5 incidentes.

Impacto esperado:
- MTTR menor e maior confiabilidade percebida.

### ES-P0-004 - Idempotencia no webhook Stripe
Objetivo:
- Evitar processamento duplicado em eventos Stripe.

Criterios de aceite:
- Evento repetido nao altera estado duas vezes.
- Registro unico por event_id processado.
- Testes cobrindo replay de webhook.

Impacto esperado:
- Zero dupla confirmacao e menos divergencia financeira.

### ES-P0-005 - Reconciliacao de pagamentos pendentes
Objetivo:
- Job periodico para reconciliar status local com Stripe.

Criterios de aceite:
- Job roda em intervalos definidos e atualiza pagamentos pendentes.
- Logs e metricas de quantidade reconciliada.
- Processamento seguro e idempotente.

Impacto esperado:
- Menos agendamento travado em status errado.

### ES-P0-006 - Fila assicrona para notificacoes
Objetivo:
- Tirar envios de notificacao do fluxo sincrono de request.

Criterios de aceite:
- Emails/WhatsApp enviados por fila com retry controlado.
- Falha no provider nao derruba request de agendamento.
- Dead letter e visibilidade de tentativas.

Impacto esperado:
- Menor latencia no front e maior resiliencia.

### ES-P0-007 - Reserva temporaria de slot (hold)
Objetivo:
- Bloquear horario por tempo curto durante checkout.

Criterios de aceite:
- Hold com TTL configuravel (ex: 10 minutos).
- Expiracao libera slot automaticamente.
- Cliente recebe feedback de tempo restante.

Impacto esperado:
- Menos disputa por horario e mais conversao de pagamento.

### ES-P0-008 - Garantia transacional anti-conflito
Objetivo:
- Eliminar corrida de concorrencia em horarios.

Criterios de aceite:
- Criacao/remarcacao valida conflito em transacao atomica.
- Cobertura de teste para requests concorrentes.
- Indicador de double-booking tende a zero.

Impacto esperado:
- Confianca alta no motor de agenda.

### ES-P0-009 - Fluxo publico em menos passos
Objetivo:
- Reduzir friccao no agendamento mobile.

Criterios de aceite:
- Campos opcionais mantidos opcionais.
- Tempo medio de preenchimento reduzido em no minimo 30%.
- Taxa de abandono por etapa monitorada.

Impacto esperado:
- Crescimento da conversao de novos clientes.

### ES-P0-010 - Funil completo de conversao
Objetivo:
- Medir cada etapa: visita, escolha, horario, envio, pagamento.

Criterios de aceite:
- Eventos padronizados com empresa_id e origem.
- Dashboard com conversao por etapa e por canal.
- Alertas para queda abrupta de conversao.

Impacto esperado:
- Prioridade guiada por dados reais.

### ES-P0-011 - Lembretes automaticos anti no-show
Objetivo:
- Disparar lembretes D-1 e H-2 por canal preferido.

Criterios de aceite:
- Agenda de envio por fila com retry.
- Cliente pode escolher canal de notificacao.
- Taxa de no-show monitorada pre e pos rollout.

Impacto esperado:
- Queda significativa de faltas.

### ES-P0-012 - Confirmacao ativa de presenca
Objetivo:
- Pedir confirmacao de presenca antes do horario.

Criterios de aceite:
- Link de confirmar/reagendar/cancelar em 1 toque.
- Atualizacao de status instantanea no painel.
- Opcao de liberacao da vaga quando cliente cancela.

Impacto esperado:
- Aumento de previsibilidade e ocupacao.

### ES-P0-013 - Lista de espera automatica
Objetivo:
- Preencher vagas abertas sem operacao manual.

Criterios de aceite:
- Cliente entra na lista por servico e janela de horario.
- Ao liberar vaga, sistema notifica candidatos com prioridade definida.
- Janela de aceite com expiracao automatica.

Impacto esperado:
- Melhor ocupacao da agenda e menor perda de receita.

## 6) Backlog P1 (fase seguinte)

### ES-P1-001 - Score de risco de no-show
- Modelo inicial baseado em historico de presenca, antecedencia de agendamento e canal.
- Exibir score para a empresa ajustar politica de confirmacao.

### ES-P1-002 - Recomendador de melhor horario
- Ordenar slots por maior chance de comparecimento + ocupacao equilibrada.

### ES-P1-003 - Integracao com Google Calendar e Outlook
- Criar/atualizar/cancelar eventos automaticamente.
- Evitar conflito de agenda pessoal do profissional.

### ES-P1-004 - BI de rentabilidade
- Receita por hora, profissional e servico.
- Margem por pacote mensal e produtos.

### ES-P1-005 - Automacoes por nicho
- Regras prontas por tipo de negocio (barbearia, clinica, aula).

## 7) Dependencias tecnicas sugeridas

- Fila assicrona: Celery + Redis (ou alternativa equivalente).
- Observabilidade: Sentry + logging JSON + painel de metricas.
- Feature flags para rollout gradual.
- Testes E2E para fluxos criticos (agendar, pagar, remarcar, cancelar, webhook).

## 8) Definicao de pronto (DoD)

Para cada item do backlog:
- Codigo + teste automatizado.
- Metrica conectada ao KPI do item.
- Rollback seguro e feature flag quando aplicavel.
- Atualizacao de documentacao tecnica e operacional.

## 9) Ordem recomendada de execucao imediata

1. ES-P0-001
2. ES-P0-002
3. ES-P0-004
4. ES-P0-008
5. ES-P0-007
6. ES-P0-011
7. ES-P0-009
8. ES-P0-010

Com essa ordem, voce ganha confiabilidade primeiro, depois conversao e retencao.
