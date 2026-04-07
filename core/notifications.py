import json
import urllib.request

from django.conf import settings
from django.core.mail import send_mail

from agendamentos.models import NotificacaoProfissional


def _booking_message(agendamento):
    empresa = agendamento.empresa
    profile_label = empresa.business_profile.get("label", "Operacao")
    intro = f"{profile_label} - Experiencia confirmada para voce."
    return (
        f"{intro}\n"
        f"Empresa: {empresa.nome}\n"
        f"Cliente: {agendamento.cliente.nome}\n"
        f"Servico: {agendamento.servico.nome}\n"
        f"Profissional: {agendamento.profissional.nome}\n"
        f"Data: {agendamento.data.strftime('%d/%m/%Y')}\n"
        f"Hora: {agendamento.hora.strftime('%H:%M')}\n"
        f"Status: {agendamento.get_status_display()}\n"
        "Nos vemos em breve!"
    )


def _send_whatsapp(phone, message):
    webhook_url = getattr(settings, "WHATSAPP_WEBHOOK_URL", "")
    if not webhook_url or not phone:
        return

    payload = json.dumps({"phone": phone, "message": message}).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5):
            pass
    except Exception:
        # Falha de envio externo nao pode quebrar o fluxo do agendamento.
        return


def _send_email(email, subject, message):
    if not email:
        return
    try:
        send_mail(
            subject,
            message,
            getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@easyschedule.local"),
            [email],
            fail_silently=True,
        )
    except Exception:
        return


def send_whatsapp_message(phone, message):
    _send_whatsapp(phone, message)


def send_email_message(email, subject, message):
    _send_email(email, subject, message)


def notify_booking_created(agendamento):
    message = _booking_message(agendamento)
    subject = f"Confirmacao de agendamento - {agendamento.empresa.nome}"

    prefer_whatsapp = True
    prefer_email = True
    try:
        from .models import ClientePortalPreferencia

        pref = ClientePortalPreferencia.objects.filter(
            empresa=agendamento.empresa,
            cliente=agendamento.cliente,
        ).first()
        if pref:
            prefer_whatsapp = pref.receber_whatsapp
            prefer_email = pref.receber_email
    except Exception:
        pass

    if prefer_email:
        _send_email(agendamento.cliente.email, subject, message)
    if prefer_whatsapp:
        _send_whatsapp(agendamento.cliente.telefone, message)

    prof_message = (
        f"Novo agendamento com {agendamento.cliente.nome} em "
        f"{agendamento.data.strftime('%d/%m/%Y')} as {agendamento.hora.strftime('%H:%M')}"
    )
    _send_email(agendamento.profissional.email, subject, message)
    _send_whatsapp(agendamento.profissional.telefone, prof_message)

    NotificacaoProfissional.objects.create(
        profissional=agendamento.profissional,
        agendamento=agendamento,
        titulo="Novo agendamento recebido",
        mensagem=prof_message,
    )
