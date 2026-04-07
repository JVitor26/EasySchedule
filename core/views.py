from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, render
from django.http import JsonResponse

from agendamentos.availability import list_available_slots
from agendamentos.models import Pagamento, PlanoMensal
from agendamentos.plans import list_monthly_available_slots
from empresas.business_profiles import get_business_profile
from empresas.models import Empresa
from profissionais.models import Profissional
from produtos.models import Produto
from servicos.models import Servico

from .forms import PublicBookingForm, PublicCheckoutForm


def home(request):
    empresas = Empresa.objects.all().order_by("nome")
    return render(request, "core/cliente_home.html", {"empresas": empresas})


def empresa_detail(request, empresa_id):
    empresa = get_object_or_404(Empresa, pk=empresa_id)
    profile = get_business_profile(empresa.tipo)
    success_booking = None
    success_client = None
    success_payment = None
    success_plan = None

    if request.method == "POST":
        form = PublicBookingForm(request.POST, empresa=empresa)
        if form.is_valid():
            try:
                result = form.save()
            except ValidationError:
                pass
            else:
                success_booking = result["agendamento"]
                success_client = result["cliente"]
                success_payment = result["pagamento"]
                success_plan = result["plano"]
                form = PublicBookingForm(empresa=empresa, initial={
                    "nome": success_client.nome,
                    "email": success_client.email,
                    "telefone": success_client.telefone,
                    "documento": success_client.documento,
                    "data_nascimento": success_client.data_nascimento,
                })
    else:
        form = PublicBookingForm(empresa=empresa)

    context = {
        "empresa": empresa,
        "profile": profile,
        "form": form,
        "servicos": Servico.objects.filter(empresa=empresa, ativo=True).order_by("nome"),
        "produtos": Produto.objects.filter(
            empresa=empresa,
            ativo=True,
            destaque_publico=True,
        ).order_by("nome"),
        "profissionais": Profissional.objects.filter(empresa=empresa, ativo=True).order_by("nome"),
        "success_booking": success_booking,
        "success_client": success_client,
        "success_payment": success_payment,
        "success_plan": success_plan,
    }
    return render(request, "core/cliente_empresa.html", context)


def _is_checkout_paid(cobranca):
    if hasattr(cobranca, "pagamento_status"):
        return cobranca.pagamento_status == "pago"
    return cobranca.status == "pago"


def _render_checkout(request, cobranca, *, checkout_kind, agendamento=None, plano=None):
    payment_success = False

    if request.method == "POST" and not _is_checkout_paid(cobranca):
        form = PublicCheckoutForm(request.POST, cobranca=cobranca)
        if form.is_valid():
            form.save()
            payment_success = True
            messages.success(request, "Pagamento registrado com sucesso.")
            form = PublicCheckoutForm(cobranca=cobranca)
    else:
        form = PublicCheckoutForm(cobranca=cobranca)
        payment_success = _is_checkout_paid(cobranca)

    return render(request, "core/cliente_pagamento.html", {
        "empresa": cobranca.empresa,
        "checkout": cobranca,
        "checkout_kind": checkout_kind,
        "checkout_total": getattr(cobranca, "valor_mensal", None) or getattr(cobranca, "valor", None),
        "agendamento": agendamento,
        "plano": plano,
        "cliente": cobranca.cliente,
        "form": form,
        "payment_success": payment_success,
    })


def payment_detail(request, token):
    pagamento = get_object_or_404(
        Pagamento.objects.select_related(
            "empresa",
            "agendamento",
            "cliente",
            "agendamento__servico",
            "agendamento__profissional",
        ),
        referencia_publica=token,
    )

    return _render_checkout(
        request,
        pagamento,
        checkout_kind="avulso",
        agendamento=pagamento.agendamento,
    )


def plan_payment_detail(request, token):
    plano = get_object_or_404(
        PlanoMensal.objects.select_related(
            "empresa",
            "cliente",
            "servico",
            "profissional",
        ),
        referencia_publica=token,
    )

    return _render_checkout(
        request,
        plano,
        checkout_kind="plano",
        agendamento=plano.first_occurrence,
        plano=plano,
    )


def available_slots_api(request, empresa_id):
    empresa = get_object_or_404(Empresa, pk=empresa_id)
    servico_id = request.GET.get("servico")
    profissional_id = request.GET.get("profissional")
    booking_type = request.GET.get("tipo_reserva") or "avulso"

    servico = Servico.objects.filter(empresa=empresa, ativo=True, pk=servico_id).first() if servico_id else None
    profissional = Profissional.objects.filter(empresa=empresa, ativo=True, pk=profissional_id).first() if profissional_id else None

    if booking_type == "pacote_mensal":
        mes_referencia = request.GET.get("mes_referencia")
        dia_semana = request.GET.get("dia_semana")

        try:
            selected_month = forms.DateField().clean(mes_referencia) if mes_referencia else None
        except Exception:
            selected_month = None

        try:
            selected_weekday = int(dia_semana) if dia_semana not in (None, "") else None
        except (TypeError, ValueError):
            selected_weekday = None

        if not all([servico, profissional, selected_month]) or selected_weekday is None:
            return JsonResponse({
                "slots": [],
                "message": "Selecione servico, profissional, mes e dia da semana.",
            })

        slots, occurrence_dates = list_monthly_available_slots(
            empresa=empresa,
            profissional=profissional,
            servico=servico,
            month_reference=selected_month,
            weekday=selected_weekday,
        )

        payload = {
            "slots": [{"value": slot.strftime("%H:%M"), "label": slot.strftime("%H:%M")} for slot in slots],
            "message": (
                f"Pacote com {len(occurrence_dates)} encontro(s) no mes. Escolha um horario livre em todas as semanas."
                if slots else
                "Nenhum horario fixo ficou livre em todas as semanas desse pacote."
            ),
        }
        return JsonResponse(payload)

    data = request.GET.get("data")

    try:
        selected_date = forms.DateField().clean(data) if data else None
    except Exception:
        selected_date = None

    if not all([servico, profissional, selected_date]):
        return JsonResponse({"slots": [], "message": "Selecione servico, profissional e data."})

    slots = list_available_slots(
        empresa=empresa,
        profissional=profissional,
        servico=servico,
        data=selected_date,
    )

    payload = {
        "slots": [{"value": slot.strftime("%H:%M"), "label": slot.strftime("%H:%M")} for slot in slots],
        "message": "Horarios disponiveis carregados." if slots else "Nenhum horario livre para essa combinacao.",
    }
    return JsonResponse(payload)
