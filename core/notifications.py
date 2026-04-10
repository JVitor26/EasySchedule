import json
import urllib.request
from urllib.parse import urljoin

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

from agendamentos.models import NotificacaoProfissional


def _company_monogram(company_name):
    tokens = [
        token
        for token in "".join(char if char.isalnum() else " " for char in (company_name or "")).split()
        if token
    ]
    if len(tokens) >= 2:
        return (tokens[0][0] + tokens[1][0]).upper()
    if tokens:
        return tokens[0][:2].upper()
    return "ES"


def _normalize_hex_color(value):
    raw = (value or "").strip().lower()
    if not raw:
        return ""

    if not raw.startswith("#"):
        raw = f"#{raw}"

    if len(raw) != 7:
        return ""

    hex_digits = "0123456789abcdef"
    if all(char in hex_digits for char in raw[1:]):
        return raw

    return ""


def _booking_email_theme(profile_key):
    themes = {
        "default": {
            "primary": "#0f4c81",
            "secondary": "#188fa7",
            "page_bg": "#f5f8fc",
            "card_border": "#e5eaf3",
            "surface": "#f9fbff",
            "line": "#e8eef9",
            "muted": "#64748b",
            "body_text": "#1f2937",
        },
        "barbearia": {
            "primary": "#0b3a61",
            "secondary": "#0e7490",
            "page_bg": "#eff6fb",
            "card_border": "#dbe7f2",
            "surface": "#f6fbff",
            "line": "#dce8f4",
            "muted": "#5b6f85",
            "body_text": "#17212b",
        },
        "manicure": {
            "primary": "#b4235f",
            "secondary": "#f25f9b",
            "page_bg": "#fff4f8",
            "card_border": "#f8dbe8",
            "surface": "#fff9fb",
            "line": "#f6d8e6",
            "muted": "#8d5a71",
            "body_text": "#2f1d27",
        },
        "salao_beleza": {
            "primary": "#9a3412",
            "secondary": "#f97316",
            "page_bg": "#fff7ed",
            "card_border": "#fde6d0",
            "surface": "#fffaf5",
            "line": "#fde6d0",
            "muted": "#8a5b3f",
            "body_text": "#2c1d14",
        },
        "estetica": {
            "primary": "#0f766e",
            "secondary": "#14b8a6",
            "page_bg": "#f0fdfa",
            "card_border": "#ccece7",
            "surface": "#f7fffd",
            "line": "#d4f1ec",
            "muted": "#4d7d77",
            "body_text": "#18312e",
        },
        "clinica": {
            "primary": "#1d4ed8",
            "secondary": "#38bdf8",
            "page_bg": "#eff6ff",
            "card_border": "#dbe9ff",
            "surface": "#f7fbff",
            "line": "#dbe9ff",
            "muted": "#516f9f",
            "body_text": "#18253d",
        },
        "tatuagem": {
            "primary": "#111827",
            "secondary": "#ea580c",
            "page_bg": "#f7f7f8",
            "card_border": "#e4e4e7",
            "surface": "#fafafa",
            "line": "#e4e4e7",
            "muted": "#6b7280",
            "body_text": "#111827",
        },
        "petshop": {
            "primary": "#166534",
            "secondary": "#f59e0b",
            "page_bg": "#f7fee7",
            "card_border": "#e2f2bf",
            "surface": "#fbffef",
            "line": "#e2f2bf",
            "muted": "#63704c",
            "body_text": "#1d2a13",
        },
    }
    return themes.get(profile_key, themes["default"])


def _resolve_company_logo_url(empresa):
    for attr in ("logo", "logo_url", "imagem", "avatar"):
        value = getattr(empresa, attr, "")
        if not value:
            continue

        if hasattr(value, "url"):
            try:
                value = value.url
            except Exception:
                continue

        value = str(value).strip()
        if not value:
            continue

        if value.startswith(("http://", "https://", "data:")):
            return value

        base_url = getattr(settings, "STRIPE_DOMAIN_URL", "").strip()
        if base_url:
            return urljoin(f"{base_url.rstrip('/')}/", value.lstrip("/"))

        return value

    return ""


def _booking_message_for_customer(agendamento):
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


def _booking_message_for_professional(agendamento):
    return (
        "Voce recebeu um novo agendamento.\n"
        f"Empresa: {agendamento.empresa.nome}\n"
        f"Cliente: {agendamento.cliente.nome}\n"
        f"Servico: {agendamento.servico.nome}\n"
        f"Data: {agendamento.data.strftime('%d/%m/%Y')}\n"
        f"Hora: {agendamento.hora.strftime('%H:%M')}\n"
        f"Status: {agendamento.get_status_display()}\n"
        "Acesse a agenda para acompanhar os detalhes."
    )


def _booking_whatsapp_message_for_customer(agendamento):
    empresa = agendamento.empresa
    profile_label = empresa.business_profile.get("label", "Operacao")
    logo_url = _resolve_company_logo_url(empresa)

    lines = [
        f"{empresa.nome} | Confirmacao de agendamento",
        f"Segmento: {profile_label}",
        f"Servico: {agendamento.servico.nome}",
        f"Profissional: {agendamento.profissional.nome}",
        f"Data: {agendamento.data.strftime('%d/%m/%Y')}",
        f"Hora: {agendamento.hora.strftime('%H:%M')}",
        f"Status: {agendamento.get_status_display()}",
        "Nos vemos em breve!",
    ]

    if logo_url:
        lines.append(f"Logo: {logo_url}")

    return "\n".join(lines)


def _booking_whatsapp_message_for_professional(agendamento):
    empresa = agendamento.empresa
    profile_label = empresa.business_profile.get("label", "Operacao")
    logo_url = _resolve_company_logo_url(empresa)

    lines = [
        f"{empresa.nome} | Novo agendamento recebido",
        f"Segmento: {profile_label}",
        f"Cliente: {agendamento.cliente.nome}",
        f"Servico: {agendamento.servico.nome}",
        f"Data: {agendamento.data.strftime('%d/%m/%Y')}",
        f"Hora: {agendamento.hora.strftime('%H:%M')}",
        f"Status: {agendamento.get_status_display()}",
        "Acesse a agenda para acompanhar os detalhes.",
    ]

    if logo_url:
        lines.append(f"Logo: {logo_url}")

    return "\n".join(lines)


def _booking_email_context(agendamento):
    profile = agendamento.empresa.business_profile
    theme = _booking_email_theme(profile.get("key"))
    custom_primary = _normalize_hex_color(getattr(agendamento.empresa, "cor_primaria", ""))
    custom_secondary = _normalize_hex_color(getattr(agendamento.empresa, "cor_secundaria", ""))

    if custom_primary:
        theme["primary"] = custom_primary
    if custom_secondary:
        theme["secondary"] = custom_secondary

    return {
        "empresa_nome": agendamento.empresa.nome,
        "empresa_logo_url": _resolve_company_logo_url(agendamento.empresa),
        "empresa_monograma": _company_monogram(agendamento.empresa.nome),
        "empresa_tipo_label": profile.get("label", "Operacao"),
        "cliente_nome": agendamento.cliente.nome,
        "servico_nome": agendamento.servico.nome,
        "profissional_nome": agendamento.profissional.nome,
        "data": agendamento.data.strftime("%d/%m/%Y"),
        "hora": agendamento.hora.strftime("%H:%M"),
        "status": agendamento.get_status_display(),
        "brand_primary": theme["primary"],
        "brand_secondary": theme["secondary"],
        "brand_page_bg": theme["page_bg"],
        "brand_card_border": theme["card_border"],
        "brand_surface": theme["surface"],
        "brand_line": theme["line"],
        "brand_muted": theme["muted"],
        "brand_body_text": theme["body_text"],
    }


def _render_email_html(template_name, context):
    try:
        return render_to_string(template_name, context)
    except Exception:
        # Falha de template nao pode quebrar o fluxo do agendamento.
        return None


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


def _send_email(email, subject, message, html_message=None):
    if not email:
        return
    try:
        send_mail(
            subject,
            message,
            getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@easyschedule.local"),
            [email],
            fail_silently=True,
            html_message=html_message,
        )
    except Exception:
        return


def send_whatsapp_message(phone, message):
    _send_whatsapp(phone, message)


def send_email_message(email, subject, message):
    _send_email(email, subject, message)


def notify_booking_created(agendamento):
    customer_message = _booking_message_for_customer(agendamento)
    customer_whatsapp_message = _booking_whatsapp_message_for_customer(agendamento)
    customer_subject = f"Confirmacao do seu agendamento - {agendamento.empresa.nome}"
    professional_message = _booking_message_for_professional(agendamento)
    professional_whatsapp_message = _booking_whatsapp_message_for_professional(agendamento)
    professional_subject = f"Novo agendamento recebido - {agendamento.empresa.nome}"
    context = _booking_email_context(agendamento)

    customer_html_message = _render_email_html(
        "core/emails/booking_confirmation_customer.html",
        context,
    )
    professional_html_message = _render_email_html(
        "core/emails/booking_confirmation_professional.html",
        context,
    )

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
        _send_email(
            agendamento.cliente.email,
            customer_subject,
            customer_message,
            html_message=customer_html_message,
        )
    if prefer_whatsapp:
        _send_whatsapp(agendamento.cliente.telefone, customer_whatsapp_message)

    _send_email(
        agendamento.profissional.email,
        professional_subject,
        professional_message,
        html_message=professional_html_message,
    )
    _send_whatsapp(agendamento.profissional.telefone, professional_whatsapp_message)

    NotificacaoProfissional.objects.create(
        profissional=agendamento.profissional,
        agendamento=agendamento,
        titulo="Novo agendamento recebido",
        mensagem=professional_whatsapp_message,
    )
