import re
import unicodedata
from datetime import date, datetime, timedelta

from django import forms
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from agendamentos.availability import acquire_schedule_lock, list_available_slots
from agendamentos.models import Agendamento
from pessoa.models import Pessoa
from profissionais.models import Profissional
from servicos.models import Servico


def _normalize_text(value):
    normalized = unicodedata.normalize("NFKD", value or "")
    without_accents = "".join(
        char for char in normalized if not unicodedata.combining(char)
    )
    return re.sub(r"\s+", " ", without_accents.strip().lower())


def _parse_date_from_text(text):
    lowered = _normalize_text(text)
    today = timezone.localdate()

    if "amanha" in lowered:
        return today + timedelta(days=1)
    if "hoje" in lowered:
        return today

    match = re.search(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{4}))?\b", lowered)
    if match:
        day = int(match.group(1))
        month = int(match.group(2))
        year = int(match.group(3) or today.year)
        try:
            parsed = date(year, month, day)
        except ValueError:
            return None
        if parsed < today and not match.group(3):
            try:
                parsed = date(today.year + 1, month, day)
            except ValueError:
                return None
        return parsed

    match_iso = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", lowered)
    if match_iso:
        try:
            return date(int(match_iso.group(1)), int(match_iso.group(2)), int(match_iso.group(3)))
        except ValueError:
            return None
    return None


def _parse_time_from_text(text):
    lowered = _normalize_text(text)

    match = re.search(r"\b([01]?\d|2[0-3])[:h]([0-5]\d)\b", lowered)
    if match:
        return f"{int(match.group(1)):02d}:{match.group(2)}"

    match = re.search(r"\b([01]?\d|2[0-3])\s*(?:h|horas?)\s*([0-5]\d)?\b", lowered)
    if match:
        return f"{int(match.group(1)):02d}:{match.group(2) or '00'}"

    match = re.search(r"\bas\s+([01]?\d|2[0-3])\b", lowered)
    if match:
        return f"{int(match.group(1)):02d}:00"

    match = re.search(r"\b([1-9]|1[0-2])\s*(?:da|de)\s*(manha|tarde|noite)\b", lowered)
    if match:
        hour = int(match.group(1))
        period = match.group(2)
        if period in {"tarde", "noite"} and hour < 12:
            hour += 12
        return f"{hour:02d}:00"

    return None


def _parse_period_from_text(text):
    lowered = _normalize_text(text)
    if re.search(r"\bmanha\b", lowered):
        return "manha"
    if re.search(r"\btarde\b", lowered):
        return "tarde"
    if re.search(r"\bnoite\b", lowered):
        return "noite"
    return ""


def _resolve_servico(empresa, text):
    lowered = _normalize_text(text)
    for servico in Servico.objects.filter(empresa=empresa, ativo=True).order_by("nome"):
        name = _normalize_text(servico.nome)
        if name and name in lowered:
            return servico
    return None


def _resolve_profissional(empresa, text):
    lowered = _normalize_text(text)
    for profissional in Profissional.objects.filter(empresa=empresa, ativo=True).order_by("nome"):
        name = _normalize_text(profissional.nome)
        if name and name in lowered:
            return profissional
    return None


def _filter_slots_by_period(slot_values, period):
    if not period:
        return slot_values
    filtered = []
    for slot in slot_values:
        hour = int(slot[:2])
        if period == "manha" and hour < 12:
            filtered.append(slot)
        elif period == "tarde" and 12 <= hour < 18:
            filtered.append(slot)
        elif period == "noite" and hour >= 18:
            filtered.append(slot)
    return filtered


def _upsert_cliente(empresa, telefone, nome):
    cliente = Pessoa.objects.filter(empresa=empresa, telefone=telefone).first()
    if cliente:
        if nome and cliente.nome != nome:
            cliente.nome = nome
            cliente.save(update_fields=["nome"])
        return cliente
    return Pessoa.objects.create(
        empresa=empresa,
        nome=nome or "Cliente IA",
        telefone=telefone,
        email="",
        documento="",
    )


def _build_service_suggestions(empresa):
    return list(Servico.objects.filter(empresa=empresa, ativo=True).order_by("nome").values_list("nome", flat=True)[:5])


def _build_profissional_suggestions(empresa):
    return list(Profissional.objects.filter(empresa=empresa, ativo=True).order_by("nome").values_list("nome", flat=True)[:5])


def handle_ai_scheduling_message(empresa, telefone, mensagem, contexto=None):
    context = dict(contexto or {})
    booking = dict(context.get("booking") or {})
    text = _normalize_text(mensagem)

    if not telefone:
        return {
            "resposta": "Envie seu telefone para continuar o agendamento.",
            "contexto": context,
            "sugestoes": [],
            "acao": "pedir_telefone",
        }

    if "nome " in f" {text} " and not booking.get("nome_cliente"):
        possible_name = text.split("nome", 1)[-1].strip(" :.-")
        if possible_name:
            booking["nome_cliente"] = possible_name[:80].title()

    servico = None
    if booking.get("servico_id"):
        servico = Servico.objects.filter(empresa=empresa, pk=booking["servico_id"], ativo=True).first()
    if servico is None:
        servico = _resolve_servico(empresa, text)
        if servico:
            booking["servico_id"] = servico.id
            booking["servico_nome"] = servico.nome

    profissional = None
    if booking.get("profissional_id"):
        profissional = Profissional.objects.filter(empresa=empresa, pk=booking["profissional_id"], ativo=True).first()
    if profissional is None:
        profissional = _resolve_profissional(empresa, text)
        if profissional:
            booking["profissional_id"] = profissional.id
            booking["profissional_nome"] = profissional.nome

    parsed_date = _parse_date_from_text(text)
    if parsed_date:
        booking["data"] = parsed_date.isoformat()

    parsed_time = _parse_time_from_text(text)
    if parsed_time:
        booking["hora"] = parsed_time

    period = _parse_period_from_text(text)
    if period:
        booking["periodo"] = period

    wants_confirm = any(
        term in f" {text} "
        for term in (
            " confirmar ",
            " confirmo ",
            " pode confirmar ",
            " sim ",
            " pode marcar ",
            " fechar ",
        )
    )
    if not booking.get("servico_id"):
        context["booking"] = booking
        return {
            "resposta": "Qual servico voce quer agendar?",
            "contexto": context,
            "sugestoes": _build_service_suggestions(empresa),
            "acao": "pedir_servico",
        }

    if not booking.get("profissional_id"):
        context["booking"] = booking
        return {
            "resposta": "Com qual profissional voce prefere agendar?",
            "contexto": context,
            "sugestoes": _build_profissional_suggestions(empresa),
            "acao": "pedir_profissional",
        }

    if not booking.get("data"):
        context["booking"] = booking
        return {
            "resposta": "Qual data voce quer? (ex.: amanha, 15/04 ou 2026-04-15)",
            "contexto": context,
            "sugestoes": ["hoje", "amanha"],
            "acao": "pedir_data",
        }

    try:
        selected_date = forms.DateField().clean(booking["data"])
    except ValidationError:
        booking.pop("data", None)
        context["booking"] = booking
        return {
            "resposta": "Nao entendi a data. Envie no formato 15/04, amanha ou 2026-04-15.",
            "contexto": context,
            "sugestoes": ["amanha"],
            "acao": "pedir_data",
        }
    slots = list_available_slots(
        empresa=empresa,
        profissional=profissional,
        servico=servico,
        data=selected_date,
    )
    slot_values = [slot.strftime("%H:%M") for slot in slots]

    filtered_values = _filter_slots_by_period(slot_values, booking.get("periodo", ""))
    if not filtered_values:
        context["booking"] = booking
        return {
            "resposta": "Nao achei horarios livres nessa data. Quer tentar outro dia?",
            "contexto": context,
            "sugestoes": [],
            "acao": "sem_horario",
        }

    selected_time = booking.get("hora")
    if selected_time and selected_time not in filtered_values:
        booking.pop("hora", None)
        selected_time = None

    if not selected_time:
        context["booking"] = booking
        return {
            "resposta": (
                f"Tenho horarios para {selected_date.strftime('%d/%m/%Y')}. "
                "Escolha um horario e eu confirmo para voce."
            ),
            "contexto": context,
            "sugestoes": filtered_values[:6],
            "acao": "pedir_horario",
        }

    if not wants_confirm:
        context["booking"] = booking
        return {
            "resposta": (
                f"Confirma o agendamento de {servico.nome} com {profissional.nome} "
                f"em {selected_date.strftime('%d/%m/%Y')} as {selected_time}?"
            ),
            "contexto": context,
            "sugestoes": ["confirmar", "trocar horario"],
            "acao": "confirmar_agendamento",
        }

    with transaction.atomic():
        acquire_schedule_lock(empresa=empresa, profissional=profissional, data=selected_date)
        slots_now = list_available_slots(
            empresa=empresa,
            profissional=profissional,
            servico=servico,
            data=selected_date,
        )
        slot_values_now = [slot.strftime("%H:%M") for slot in slots_now]
        if selected_time not in slot_values_now:
            context["booking"] = booking
            return {
                "resposta": "Esse horario acabou de ficar indisponivel. Escolha outro.",
                "contexto": context,
                "sugestoes": slot_values_now[:6],
                "acao": "horario_indisponivel",
            }

        cliente = _upsert_cliente(empresa, telefone, booking.get("nome_cliente") or "Cliente IA")
        agendamento = Agendamento(
            empresa=empresa,
            cliente=cliente,
            servico=servico,
            profissional=profissional,
            data=selected_date,
            hora=forms.TimeField().clean(selected_time),
            observacoes="Agendamento criado pelo assistente de IA.",
            status="pendente",
            pagamento_status="pendente",
            metodo_pagamento="",
        )
        agendamento.full_clean()
        agendamento.save()

    context["booking"] = {}
    return {
        "resposta": (
            f"Agendamento confirmado: {servico.nome} com {profissional.nome} "
            f"em {selected_date.strftime('%d/%m/%Y')} as {selected_time}."
        ),
        "contexto": context,
        "sugestoes": [],
        "acao": "agendamento_criado",
        "agendamento_id": agendamento.id,
    }
