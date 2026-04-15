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


PHONE_WORDS = {
    "zero": "0",
    "um": "1",
    "uma": "1",
    "dois": "2",
    "duas": "2",
    "tres": "3",
    "treis": "3",
    "quatro": "4",
    "cinco": "5",
    "seis": "6",
    "meia": "6",
    "sete": "7",
    "oito": "8",
    "nove": "9",
}

WEEKDAY_NAMES = {
    "segunda": 0,
    "segunda feira": 0,
    "terca": 1,
    "terca feira": 1,
    "terça": 1,
    "terça feira": 1,
    "quarta": 2,
    "quarta feira": 2,
    "quinta": 3,
    "quinta feira": 3,
    "sexta": 4,
    "sexta feira": 4,
    "sabado": 5,
    "sabado feira": 5,
    "sábado": 5,
    "domingo": 6,
}

WEEKDAY_LABELS = {
    0: "segunda feira",
    1: "terca feira",
    2: "quarta feira",
    3: "quinta feira",
    4: "sexta feira",
    5: "sabado",
    6: "domingo",
}


def _normalize_text(value):
    normalized = unicodedata.normalize("NFKD", value or "")
    without_accents = "".join(
        char for char in normalized if not unicodedata.combining(char)
    )
    return re.sub(r"\s+", " ", without_accents.strip().lower())


def _only_digits(value):
    return re.sub(r"\D", "", value or "")


def _clean_phone_candidate(value):
    digits = _only_digits(value)
    if len(digits) < 10:
        return ""
    if len(digits) > 11:
        digits = digits[-11:]
    return digits


def _extract_phone_from_text(text):
    raw_text = text or ""
    direct_matches = re.findall(r"(?:\d[\s().-]*){10,13}", raw_text)
    for match in direct_matches:
        candidate = _clean_phone_candidate(match)
        if candidate:
            return candidate

    lowered = _normalize_text(raw_text)
    marker_match = re.search(r"\b(?:telefone|whatsapp|zap|celular|fone|numero)\b", lowered)
    segment = lowered[marker_match.end():] if marker_match else lowered
    tokens = re.findall(r"\d+|[a-z]+", segment)
    digits = []

    for token in tokens:
        if token.isdigit():
            digits.extend(list(token))
        elif token in PHONE_WORDS:
            digits.append(PHONE_WORDS[token])
        elif token == "e" and digits:
            continue
        elif digits:
            break

        if len(digits) >= 11:
            break

    return _clean_phone_candidate("".join(digits))


def _parse_cliente_name(text):
    lowered = _normalize_text(text)
    match = re.search(r"\b(?:cliente|nome)\s+(?:o|a|do|da|de)?\s*([a-z ]{2,80})", lowered)
    if not match:
        return ""

    name = match.group(1)
    stop_match = re.search(
        r"\b(?:telefone|whatsapp|zap|celular|fone|servico|serviço|corte|barba|unha|massagem|sobrancelha|com|na|no|para|hoje|amanha|segunda|terca|terça|quarta|quinta|sexta|sabado|sábado|domingo|dia|data|as|horas?)\b",
        name,
    )
    if stop_match:
        name = name[:stop_match.start()]

    name = re.sub(r"\s+", " ", name).strip(" .:-")
    if len(name) < 2:
        return ""
    return name[:80].title()


def _date_for_next_weekday(target_weekday):
    today = timezone.localdate()
    days_ahead = target_weekday - today.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return today + timedelta(days=days_ahead)


def _parse_date_from_text(text):
    lowered = _normalize_text(text)
    today = timezone.localdate()

    if "amanha" in lowered:
        return today + timedelta(days=1)
    if "hoje" in lowered:
        return today

    for label, weekday in sorted(WEEKDAY_NAMES.items(), key=lambda item: len(item[0]), reverse=True):
        if re.search(rf"\b{re.escape(_normalize_text(label))}\b", lowered):
            return _date_for_next_weekday(weekday)

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


def _build_date_suggestions():
    today = timezone.localdate()
    suggestions = ["hoje", "amanha"]
    for days_ahead in range(1, 7):
        label = WEEKDAY_LABELS[(today + timedelta(days=days_ahead)).weekday()]
        if label not in suggestions:
            suggestions.append(label)
    return suggestions


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


def _resolve_cliente_by_name(empresa, name):
    normalized_name = _normalize_text(name)
    if not normalized_name:
        return None

    clientes = list(Pessoa.objects.filter(empresa=empresa).order_by("nome"))
    for cliente in clientes:
        if _normalize_text(cliente.nome) == normalized_name:
            return cliente

    if len(normalized_name) < 3:
        return None

    matches = [
        cliente
        for cliente in clientes
        if normalized_name in _normalize_text(cliente.nome)
    ]
    if len(matches) == 1:
        return matches[0]
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


def _cliente_info(cliente=None, telefone="", cadastrado=False):
    if cliente:
        return {
            "cadastrado": cadastrado,
            "id": cliente.id,
            "nome": cliente.nome,
            "telefone": cliente.telefone,
            "email": cliente.email,
            "documento": cliente.documento_formatado(),
            "campos_pendentes": cliente.campos_cadastro_pendentes(),
        }

    return {
        "cadastrado": False,
        "id": None,
        "nome": "",
        "telefone": telefone,
        "email": "",
        "documento": "",
        "campos_pendentes": ["cadastro do cliente"],
    }


def _cliente_status_prefix(cliente_info, announced=False):
    if announced or not cliente_info or not cliente_info.get("telefone"):
        return ""

    if cliente_info.get("cadastrado"):
        pendentes = cliente_info.get("campos_pendentes") or []
        if pendentes:
            return (
                f"Cliente encontrado: {cliente_info['nome']}. "
                f"Cadastro com pendencias: {', '.join(pendentes)}. "
            )
        return f"Cliente encontrado: {cliente_info['nome']}. "

    return "Cliente nao cadastrado. Vou deixar o agendamento como pendente para completar o cadastro antes da confirmacao. "


def _with_prefix(response, prefix):
    if prefix:
        response["resposta"] = f"{prefix}{response['resposta']}"
    return response


def _upsert_cliente(empresa, telefone, nome):
    cliente = Pessoa.objects.filter(empresa=empresa, telefone=telefone).first()
    if cliente:
        if nome and not cliente.nome:
            cliente.nome = nome
            cliente.save(update_fields=["nome"])
        return cliente, True
    return Pessoa.objects.create(
        empresa=empresa,
        nome=nome or "Cliente nao cadastrado",
        telefone=telefone,
        email="",
        documento="",
        observacoes="Cadastro criado automaticamente pelo assistente de agendamento por audio.",
    ), False


def _build_service_suggestions(empresa):
    return list(Servico.objects.filter(empresa=empresa, ativo=True).order_by("nome").values_list("nome", flat=True)[:5])


def _build_profissional_suggestions(empresa):
    return list(Profissional.objects.filter(empresa=empresa, ativo=True).order_by("nome").values_list("nome", flat=True)[:5])


def handle_ai_scheduling_message(empresa, telefone, mensagem, contexto=None):
    context = dict(contexto or {})
    booking = dict(context.get("booking") or {})
    text = _normalize_text(mensagem)
    telefone = _clean_phone_candidate(telefone) or booking.get("telefone") or _extract_phone_from_text(mensagem)

    possible_name = _parse_cliente_name(mensagem)
    if possible_name and not booking.get("nome_cliente"):
        booking["nome_cliente"] = possible_name

    cliente = None
    if telefone:
        cliente = Pessoa.objects.filter(empresa=empresa, telefone=telefone).first()
    if cliente is None and booking.get("cliente_id"):
        cliente = Pessoa.objects.filter(empresa=empresa, pk=booking["cliente_id"]).first()
    if cliente is None and booking.get("nome_cliente"):
        cliente = _resolve_cliente_by_name(empresa, booking["nome_cliente"])
        if cliente and not telefone:
            telefone = cliente.telefone

    if telefone:
        booking["telefone"] = telefone

    cliente_cadastrado = cliente is not None
    if cliente:
        booking["cliente_id"] = cliente.id
        booking["nome_cliente"] = cliente.nome
        booking["telefone"] = cliente.telefone
        telefone = cliente.telefone

    cliente_info = _cliente_info(cliente, telefone=telefone, cadastrado=cliente_cadastrado)
    prefix = _cliente_status_prefix(cliente_info, booking.get("cliente_status_informado"))
    if prefix:
        booking["cliente_status_informado"] = True

    def finish(response):
        context["booking"] = booking
        response["contexto"] = context
        response["telefone"] = telefone
        response["cliente_info"] = cliente_info
        return _with_prefix(response, prefix)

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

    if not telefone:
        context["booking"] = booking
        cliente_hint = ""
        if booking.get("nome_cliente"):
            cliente_hint = f"Nao encontrei cadastro para {booking['nome_cliente']}. "
        return {
            "resposta": f"{cliente_hint}Fale ou digite o telefone do cliente para continuar o agendamento.",
            "contexto": context,
            "sugestoes": [],
            "acao": "pedir_telefone",
            "telefone": "",
            "cliente_info": _cliente_info(),
        }

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
        return finish({
            "resposta": "Qual servico voce quer agendar?",
            "sugestoes": _build_service_suggestions(empresa),
            "acao": "pedir_servico",
        })

    if not booking.get("profissional_id"):
        return finish({
            "resposta": "Com qual profissional voce prefere agendar?",
            "sugestoes": _build_profissional_suggestions(empresa),
            "acao": "pedir_profissional",
        })

    if not booking.get("data"):
        return finish({
            "resposta": "Qual data voce quer? Pode falar hoje, amanha, sexta feira ou uma data como 15/04.",
            "sugestoes": _build_date_suggestions(),
            "acao": "pedir_data",
        })

    try:
        selected_date = forms.DateField().clean(booking["data"])
    except ValidationError:
        booking.pop("data", None)
        return finish({
            "resposta": "Nao entendi a data. Fale um dia da semana, amanha, ou uma data como 15/04.",
            "sugestoes": _build_date_suggestions(),
            "acao": "pedir_data",
        })
    slots = list_available_slots(
        empresa=empresa,
        profissional=profissional,
        servico=servico,
        data=selected_date,
    )
    slot_values = [slot.strftime("%H:%M") for slot in slots]

    filtered_values = _filter_slots_by_period(slot_values, booking.get("periodo", ""))
    if not filtered_values:
        return finish({
            "resposta": "Nao achei horarios livres nessa data. Quer tentar outro dia?",
            "sugestoes": [],
            "acao": "sem_horario",
        })

    selected_time = booking.get("hora")
    if selected_time and selected_time not in filtered_values:
        booking.pop("hora", None)
        selected_time = None

    if not selected_time:
        return finish({
            "resposta": (
                f"Tenho horarios para {selected_date.strftime('%d/%m/%Y')}. "
                "Escolha um horario e eu confirmo para voce."
            ),
            "sugestoes": filtered_values[:6],
            "acao": "pedir_horario",
        })

    if not wants_confirm:
        return finish({
            "resposta": (
                f"Confirma o agendamento de {servico.nome} com {profissional.nome} "
                f"em {selected_date.strftime('%d/%m/%Y')} as {selected_time}?"
            ),
            "sugestoes": ["confirmar", "trocar horario"],
            "acao": "confirmar_agendamento",
        })

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
            return finish({
                "resposta": "Esse horario acabou de ficar indisponivel. Escolha outro.",
                "sugestoes": slot_values_now[:6],
                "acao": "horario_indisponivel",
            })

        cliente, cliente_cadastrado = _upsert_cliente(empresa, telefone, booking.get("nome_cliente"))
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

    cliente_info = _cliente_info(cliente, telefone=telefone, cadastrado=cliente_cadastrado)
    pendencias = cliente_info.get("campos_pendentes") or []
    pendencia_texto = ""
    if pendencias:
        pendencia_texto = f" Antes de confirmar, complete: {', '.join(pendencias)}."

    context["booking"] = {}
    return _with_prefix({
        "resposta": (
            f"Agendamento criado como pendente: {servico.nome} com {profissional.nome} "
            f"em {selected_date.strftime('%d/%m/%Y')} as {selected_time}.{pendencia_texto}"
        ),
        "contexto": context,
        "sugestoes": [],
        "acao": "agendamento_criado",
        "agendamento_id": agendamento.id,
        "telefone": telefone,
        "cliente_info": cliente_info,
    }, prefix)
