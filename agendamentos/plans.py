from calendar import monthrange
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .availability import coerce_time_value, find_schedule_conflict, list_available_slots


WEEKDAY_CHOICES = [
    (0, "Segunda-feira"),
    (1, "Terca-feira"),
    (2, "Quarta-feira"),
    (3, "Quinta-feira"),
    (4, "Sexta-feira"),
    (5, "Sabado"),
    (6, "Domingo"),
]
WEEKDAY_LABELS = dict(WEEKDAY_CHOICES)


def normalize_month_reference(value):
    if not value:
        return None
    return value.replace(day=1)


def get_month_last_day(month_reference):
    month_reference = normalize_month_reference(month_reference)
    if not month_reference:
        return None

    last_day = monthrange(month_reference.year, month_reference.month)[1]
    return month_reference.replace(day=last_day)


def list_monthly_occurrence_dates(month_reference, weekday):
    month_reference = normalize_month_reference(month_reference)
    if month_reference is None or weekday is None:
        return []

    today = timezone.localdate()
    month_end = get_month_last_day(month_reference)
    current = month_reference
    dates = []

    while current <= month_end:
        if current.weekday() == int(weekday) and current >= today:
            dates.append(current)
        current += timedelta(days=1)

    return dates


def list_monthly_available_slots(
    empresa,
    profissional,
    servico,
    month_reference,
    weekday,
    exclude_agendamento_ids=None,
):
    occurrence_dates = list_monthly_occurrence_dates(month_reference, weekday)
    if not occurrence_dates:
        return [], []

    shared_values = None
    slot_map = {}

    for occurrence_date in occurrence_dates:
        day_slots = list_available_slots(
            empresa=empresa,
            profissional=profissional,
            servico=servico,
            data=occurrence_date,
            exclude_agendamento_ids=exclude_agendamento_ids,
        )
        day_values = {slot.strftime("%H:%M") for slot in day_slots}

        if shared_values is None:
            shared_values = day_values
            slot_map = {slot.strftime("%H:%M"): slot for slot in day_slots}
        else:
            shared_values &= day_values

    if not shared_values:
        return [], occurrence_dates

    ordered_slots = [slot_map[value] for value in sorted(shared_values)]
    return ordered_slots, occurrence_dates


@transaction.atomic
def sync_monthly_plan_schedule(plano):
    from .models import Agendamento

    if not plano.empresa_id or not plano.cliente_id or not plano.servico_id or not plano.profissional_id:
        raise ValidationError("Preencha cliente, servico e profissional antes de gerar o plano.")

    month_reference = normalize_month_reference(plano.mes_referencia)
    occurrence_dates = list_monthly_occurrence_dates(month_reference, plano.dia_semana)
    if not occurrence_dates:
        raise ValidationError({
            "mes_referencia": "Nao existem datas futuras disponiveis para esse pacote no mes selecionado.",
        })

    existing_ids = list(plano.agendamentos.values_list("id", flat=True))
    requested_time = coerce_time_value(plano.hora)
    available_slots, _dates = list_monthly_available_slots(
        empresa=plano.empresa,
        profissional=plano.profissional,
        servico=plano.servico,
        month_reference=month_reference,
        weekday=plano.dia_semana,
        exclude_agendamento_ids=existing_ids,
    )
    available_values = {slot.strftime("%H:%M") for slot in available_slots}
    requested_value = requested_time.strftime("%H:%M") if requested_time else None

    if requested_value not in available_values:
        conflitos = []
        for occurrence_date in occurrence_dates:
            conflito = find_schedule_conflict(
                empresa=plano.empresa,
                profissional=plano.profissional,
                servico=plano.servico,
                data=occurrence_date,
                hora=plano.hora,
                exclude_agendamento_ids=existing_ids,
            )
            if conflito:
                conflitos.append(occurrence_date.strftime("%d/%m"))

        if conflitos:
            raise ValidationError({
                "hora": (
                    "Esse horario nao esta livre em todas as semanas do pacote. "
                    f"Conflitos encontrados em: {', '.join(conflitos)}."
                ),
            })

        raise ValidationError({
            "hora": "Nao foi possivel reservar esse horario fixo para todas as semanas do mes.",
        })

    existing_by_date = {agendamento.data: agendamento for agendamento in plano.agendamentos.all()}
    agendamentos_usados = []
    status = "confirmado" if plano.pagamento_status == "pago" else "pendente"
    forma_pagamento = plano.metodo_pagamento or None

    for occurrence_date in occurrence_dates:
        agendamento = existing_by_date.get(occurrence_date, Agendamento(plano=plano))
        agendamento.plano = plano
        agendamento.empresa = plano.empresa
        agendamento.cliente = plano.cliente
        agendamento.servico = plano.servico
        agendamento.profissional = plano.profissional
        agendamento.data = occurrence_date
        agendamento.hora = requested_time
        agendamento.observacoes = plano.observacoes or ""
        agendamento.status = status
        agendamento.forma_pagamento = forma_pagamento
        agendamento.full_clean()
        agendamento.save()
        agendamentos_usados.append(agendamento.pk)

    plano.agendamentos.exclude(pk__in=agendamentos_usados).delete()

    quantidade_encontros = len(occurrence_dates)
    valor_mensal = (plano.servico.preco or Decimal("0.00")) * quantidade_encontros
    changed_fields = []

    if plano.quantidade_encontros != quantidade_encontros:
        plano.quantidade_encontros = quantidade_encontros
        changed_fields.append("quantidade_encontros")

    if plano.valor_mensal != valor_mensal:
        plano.valor_mensal = valor_mensal
        changed_fields.append("valor_mensal")

    if plano.mes_referencia != month_reference:
        plano.mes_referencia = month_reference
        changed_fields.append("mes_referencia")

    if changed_fields:
        plano.save(update_fields=changed_fields + ["atualizado_em"])

    return plano
