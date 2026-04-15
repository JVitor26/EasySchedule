from datetime import datetime, timedelta
from urllib.parse import urljoin

from django.conf import settings
from django.utils import timezone

from agendamentos.models import Agendamento
from core.loyalty import build_reengagement_candidates
from core.models import ClientePortalPreferencia
from core.notifications import send_email_message, send_whatsapp_message


def _portal_url(empresa):
    path = f"/cliente/empresa/{empresa.portal_token}/#meus-agendamentos"
    base_url = getattr(settings, "STRIPE_DOMAIN_URL", "").strip()
    if base_url:
        return urljoin(f"{base_url.rstrip('/')}/", path.lstrip("/"))
    return path


def _dispatch_window(empresa, start_dt, end_dt, janela):
    sent = 0
    appointments = Agendamento.objects.filter(
        empresa=empresa,
        status__in=["pendente", "confirmado"],
        data__gte=start_dt.date(),
        data__lte=end_dt.date(),
    ).select_related("cliente", "servico", "profissional")

    for agendamento in appointments:
        appointment_dt = timezone.make_aware(
            datetime.combine(agendamento.data, agendamento.hora),
            timezone.get_current_timezone(),
        )
        if not (start_dt <= appointment_dt <= end_dt):
            continue

        pref, _ = ClientePortalPreferencia.objects.get_or_create(
            empresa=agendamento.empresa,
            cliente=agendamento.cliente,
        )
        if janela == "24h" and not pref.receber_lembrete_24h:
            continue
        if janela == "2h" and not pref.receber_lembrete_2h:
            continue

        msg = (
            f"Lembrete {janela} - {agendamento.empresa.nome}\n"
            f"{agendamento.servico.nome} com {agendamento.profissional.nome}\n"
            f"{agendamento.data.strftime('%d/%m/%Y')} às {agendamento.hora.strftime('%H:%M')}\n"
            f"Confirmar, reagendar ou cancelar: {_portal_url(agendamento.empresa)}"
        )
        if pref.receber_whatsapp and agendamento.cliente.telefone:
            send_whatsapp_message(agendamento.cliente.telefone, msg)
            sent += 1
        if pref.receber_email and agendamento.cliente.email:
            send_email_message(agendamento.cliente.email, f"Lembrete {janela} - {agendamento.empresa.nome}", msg)
            sent += 1

    return sent


def run_reminders_for_empresa(empresa, janela=None):
    now = timezone.localtime()
    sent_24h = 0
    sent_2h = 0
    if janela in (None, "24h"):
        sent_24h = _dispatch_window(
            empresa=empresa,
            start_dt=now + timedelta(hours=23, minutes=30),
            end_dt=now + timedelta(hours=24, minutes=30),
            janela="24h",
        )
    if janela in (None, "2h"):
        sent_2h = _dispatch_window(
            empresa=empresa,
            start_dt=now + timedelta(hours=1, minutes=30),
            end_dt=now + timedelta(hours=2, minutes=30),
            janela="2h",
        )
    return {"24h": sent_24h, "2h": sent_2h}


def run_reengagement_for_empresa(empresa, limit=30):
    candidates = build_reengagement_candidates(empresa=empresa, days_without_return=35, limit=limit)
    sent = 0
    for item in candidates:
        message = (
            f"{empresa.nome}: sentimos sua falta.\n"
            f"Seu último atendimento foi há {item['dias_sem_retorno']} dias.\n"
            f"Agende novamente aqui: {_portal_url(empresa)}"
        )
        if item.get("telefone"):
            send_whatsapp_message(item["telefone"], message)
            sent += 1
    return {"candidatos": len(candidates), "enviados": sent}
