from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth import logout
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, render, redirect
from django.http import JsonResponse, HttpResponse
from django.db import connection, transaction
from django.views.decorators.http import require_http_methods
from django.utils import timezone
import logging
import json
import re
from decimal import Decimal
from datetime import timedelta
import secrets
import stripe

from agendamentos.availability import acquire_schedule_lock, coerce_hold_token, find_schedule_conflict, list_available_slots
from agendamentos.models import PlanoMensal, Agendamento, SlotHold
from agendamentos.plans import list_monthly_available_slots
from empresas.business_profiles import get_business_profile
from empresas.models import Empresa
from empresas.permissions import is_global_admin
from empresas.tenancy import get_active_empresa
from empresas.tenancy import get_accessible_empresas
from pessoa.models import Pessoa
from profissionais.models import Profissional
from produtos.models import Produto
from servicos.models import Servico
from .models import ClientePortalOTP, ClientePortalPreferencia, PasswordRecoveryCode, StripeWebhookEvent
from .notifications import send_whatsapp_message, send_email_message

from .forms import (
    PasswordRecoveryConfirmForm,
    PasswordRecoveryRequestForm,
    PublicBookingForm,
)


logger = logging.getLogger(__name__)


def home(request):
    if request.user.is_authenticated:
        empresas = get_accessible_empresas(request)
        template = "core/cliente_portal.html"
        context = {"empresas": empresas}
    elif getattr(request, "resolver_match", None) and request.resolver_match.url_name == "home":
        template = "home.html"
        context = {}
    else:
        empresa_id = (request.GET.get("empresa") or "").strip()
        if empresa_id.isdigit():
            empresa = Empresa.objects.filter(pk=int(empresa_id)).first()
            if empresa:
                return redirect("cliente_empresa", empresa_id=empresa.id)

        template = "core/cliente_publico.html"
        context = {}
    return render(request, template, context)


def login_redirect(request):
    if not request.user.is_authenticated:
        return redirect("login")

    profissional = getattr(request.user, "profissional_profile", None)
    if profissional and not profissional.empresa.permite_acesso_profissional:
        logout(request)
        messages.error(
            request,
            "Esta empresa utiliza o plano somente administrador. Funcionarios nao possuem acesso ao sistema.",
        )
        return redirect("login")

    empresa = get_active_empresa(request)
    if empresa:
        return redirect("dashboard_home")

    return redirect("cadastro_empresa")


def _enforce_company_portal_access(request, empresa):
    if not request.user.is_authenticated:
        return None

    if is_global_admin(request.user):
        return None

    profissional = getattr(request.user, "profissional_profile", None)
    if profissional and profissional.empresa_id != empresa.id:
        return JsonResponse({"detail": "Acesso negado para portal de outra empresa."}, status=403)

    try:
        empresa_usuario = request.user.empresa
    except Empresa.DoesNotExist:
        empresa_usuario = None
    if empresa_usuario and empresa_usuario.id != empresa.id:
        return JsonResponse({"detail": "Acesso negado para portal de outra empresa."}, status=403)

    return None


def _portal_session_key(empresa_id):
    return f"portal_cliente_empresa_{empresa_id}"


def _get_portal_cliente(request, empresa):
    pessoa_id = request.session.get(_portal_session_key(empresa.id))
    if not pessoa_id:
        return None
    return Pessoa.objects.filter(pk=pessoa_id, empresa=empresa).first()


def _set_portal_cliente(request, empresa_id, pessoa_id):
    request.session[_portal_session_key(empresa_id)] = pessoa_id
    request.session.modified = True


def _clear_portal_cliente(request, empresa_id):
    request.session.pop(_portal_session_key(empresa_id), None)
    request.session.modified = True


def _cart_session_key(empresa_id):
    return f"portal_carrinho_empresa_{empresa_id}"


def _get_cart_data(request, empresa_id):
    raw = request.session.get(_cart_session_key(empresa_id), {})
    if not isinstance(raw, dict):
        return {}

    cleaned = {}
    for raw_produto_id, raw_quantidade in raw.items():
        try:
            produto_id = int(raw_produto_id)
            quantidade = int(raw_quantidade)
        except (TypeError, ValueError):
            continue

        if produto_id <= 0 or quantidade <= 0:
            continue

        cleaned[str(produto_id)] = quantidade

    return cleaned


def _save_cart_data(request, empresa_id, cart_data):
    normalized = {}
    for raw_produto_id, raw_quantidade in (cart_data or {}).items():
        try:
            produto_id = int(raw_produto_id)
            quantidade = int(raw_quantidade)
        except (TypeError, ValueError):
            continue

        if produto_id <= 0 or quantidade <= 0:
            continue

        normalized[str(produto_id)] = quantidade

    request.session[_cart_session_key(empresa_id)] = normalized
    request.session.modified = True


def _clear_cart_data(request, empresa_id):
    request.session.pop(_cart_session_key(empresa_id), None)
    request.session.modified = True


def _build_cart_payload(empresa, cart_data):
    produto_ids = []
    for raw_produto_id in (cart_data or {}).keys():
        try:
            produto_id = int(raw_produto_id)
        except (TypeError, ValueError):
            continue

        if produto_id > 0:
            produto_ids.append(produto_id)

    produtos = {
        produto.id: produto
        for produto in Produto.objects.filter(empresa=empresa, ativo=True, pk__in=produto_ids)
    }

    items = []
    normalized_cart = {}
    total_preco = Decimal("0")
    total_itens = 0

    for raw_produto_id, raw_quantidade in (cart_data or {}).items():
        try:
            produto_id = int(raw_produto_id)
            quantidade = int(raw_quantidade)
        except (TypeError, ValueError):
            continue

        if quantidade <= 0:
            continue

        produto = produtos.get(produto_id)
        if produto is None:
            continue

        estoque_disponivel = max(int(produto.estoque_disponivel), 0)
        if estoque_disponivel <= 0:
            continue

        quantidade_final = min(quantidade, estoque_disponivel)
        if quantidade_final <= 0:
            continue

        preco_total = produto.preco * quantidade_final

        normalized_cart[str(produto.id)] = quantidade_final
        total_itens += quantidade_final
        total_preco += preco_total
        items.append({
            "produto_id": produto.id,
            "nome": produto.nome,
            "quantidade": quantidade_final,
            "preco": str(produto.preco),
            "preco_total": str(preco_total),
            "estoque_disponivel": estoque_disponivel,
        })

    return {
        "itens": items,
        "total_itens": total_itens,
        "total_preco": str(total_preco),
        "cart": normalized_cart,
    }


def _normalize_phone(value):
    return re.sub(r"\D", "", value or "")


def _build_numeric_code(length=6):
    return "".join(secrets.choice("0123456789") for _ in range(length))


def _mask_destination(value):
    if not value:
        return ""
    if "@" in value:
        local, _, domain = value.partition("@")
        local_masked = f"{local[:2]}***" if len(local) > 2 else "***"
        return f"{local_masked}@{domain}"

    digits = _normalize_phone(value)
    if len(digits) < 4:
        return "***"
    return f"***{digits[-4:]}"


def _find_internal_user(identifier):
    UserModel = get_user_model()
    identifier = (identifier or "").strip().lower()
    phone = _normalize_phone(identifier)

    if "@" in identifier:
        user = UserModel.objects.filter(username=identifier).first()
        if user:
            return user

        user = UserModel.objects.filter(email__iexact=identifier).first()
        if user:
            return user

        profissional = Profissional.objects.select_related("usuario").filter(
            email__iexact=identifier,
            usuario__isnull=False,
        ).first()
        if profissional:
            return profissional.usuario

    if phone:
        profissional = Profissional.objects.select_related("usuario").filter(
            telefone=phone,
            usuario__isnull=False,
        ).first()
        if profissional:
            return profissional.usuario

        empresa = Empresa.objects.select_related("usuario").filter(whatsapp=phone).first()
        if empresa:
            return empresa.usuario

    return None


def _find_portal_cliente_by_identifier(empresa, identifier):
    identifier = (identifier or "").strip().lower()
    phone = _normalize_phone(identifier)

    if phone:
        cliente = Pessoa.objects.filter(empresa=empresa, telefone=phone).first()
        if cliente:
            return cliente

    if "@" in identifier:
        return Pessoa.objects.filter(empresa=empresa, email=identifier).first()

    return None


def _get_internal_destination(user, channel):
    if channel == "email":
        if user.email:
            return user.email.strip().lower()

        profissional = getattr(user, "profissional_profile", None)
        if profissional and profissional.email:
            return profissional.email.strip().lower()

        username = getattr(user, "username", "")
        return username.strip().lower() if "@" in username else ""

    profissional = getattr(user, "profissional_profile", None)
    if profissional and profissional.telefone:
        return _normalize_phone(profissional.telefone)

    try:
        empresa = user.empresa
    except Empresa.DoesNotExist:
        empresa = None

    return _normalize_phone(getattr(empresa, "whatsapp", ""))


def _dispatch_recovery_code(account_type, destination, channel, code, empresa=None):
    company_name = getattr(empresa, "nome", "EasySchedule")
    if account_type == "internal":
        subject = f"Recuperacao de senha - {company_name}"
        message = f"Seu codigo EasySchedule para recuperar a senha e {code}. Valido por 10 minutos."
    else:
        subject = f"Codigo do portal - {company_name}"
        message = f"Seu codigo para redefinir a senha do portal de {company_name} e {code}. Valido por 10 minutos."

    if channel == "whatsapp":
        send_whatsapp_message(destination, message)
    else:
        send_email_message(destination, subject, message)


def _can_client_change_appointment(agendamento):
    hoje = timezone.localdate()
    return agendamento.status not in ("cancelado", "finalizado") and agendamento.data >= hoje


def empresa_catalogo(request, empresa_id):
    empresa = get_object_or_404(Empresa, pk=empresa_id)
    access_denied = _enforce_company_portal_access(request, empresa)
    if access_denied:
        return access_denied

    profile = get_business_profile(empresa.tipo)

    context = {
        "empresa": empresa,
        "profile": profile,
        "servicos": Servico.objects.filter(empresa=empresa, ativo=True).order_by("nome"),
        "profissionais": Profissional.objects.filter(empresa=empresa, ativo=True).order_by("nome"),
        "produtos_count": Produto.objects.filter(empresa=empresa, ativo=True).count(),
    }
    return render(request, "core/catalogo_empresa.html", context)


def loja_produtos(request, empresa_id):
    empresa = get_object_or_404(Empresa, pk=empresa_id)
    access_denied = _enforce_company_portal_access(request, empresa)
    if access_denied:
        return access_denied

    profile = get_business_profile(empresa.tipo)
    busca = (request.GET.get("busca") or "").strip()
    categoria_selecionada = (request.GET.get("categoria") or "").strip()

    produtos = Produto.objects.filter(empresa=empresa, ativo=True).order_by("nome")
    if busca:
        produtos = produtos.filter(nome__icontains=busca)
    if categoria_selecionada:
        produtos = produtos.filter(categoria=categoria_selecionada)

    categorias = (
        Produto.objects.filter(empresa=empresa, ativo=True)
        .exclude(categoria="")
        .order_by("categoria")
        .values_list("categoria", flat=True)
        .distinct()
    )

    cart_payload = _build_cart_payload(empresa, _get_cart_data(request, empresa.id))
    _save_cart_data(request, empresa.id, cart_payload["cart"])

    return render(request, "core/loja_produtos.html", {
        "empresa": empresa,
        "profile": profile,
        "produtos": produtos,
        "busca": busca,
        "categoria_selecionada": categoria_selecionada,
        "categorias": categorias,
        "cart_total_items": cart_payload["total_itens"],
    })


@require_http_methods(["GET"])
def api_carrinho_listar(request, empresa_id):
    empresa = get_object_or_404(Empresa, pk=empresa_id)
    access_denied = _enforce_company_portal_access(request, empresa)
    if access_denied:
        return access_denied

    payload = _build_cart_payload(empresa, _get_cart_data(request, empresa.id))
    _save_cart_data(request, empresa.id, payload["cart"])

    return JsonResponse({
        "status": "sucesso",
        "itens": payload["itens"],
        "total_itens": payload["total_itens"],
        "total_preco": payload["total_preco"],
    })


@require_http_methods(["POST"])
def api_carrinho_adicionar(request, empresa_id):
    empresa = get_object_or_404(Empresa, pk=empresa_id)
    access_denied = _enforce_company_portal_access(request, empresa)
    if access_denied:
        return access_denied

    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"status": "erro", "message": "JSON invalido."}, status=400)

    try:
        produto_id = int(data.get("produto_id"))
        quantidade = int(data.get("quantidade", 1))
    except (TypeError, ValueError):
        return JsonResponse({"status": "erro", "message": "Produto ou quantidade invalida."}, status=400)

    if quantidade <= 0:
        return JsonResponse({"status": "erro", "message": "A quantidade deve ser maior que zero."}, status=400)

    produto = Produto.objects.filter(empresa=empresa, ativo=True, pk=produto_id).first()
    if not produto:
        return JsonResponse({"status": "erro", "message": "Produto nao encontrado nesta empresa."}, status=404)

    estoque_disponivel = max(int(produto.estoque_disponivel), 0)
    if estoque_disponivel <= 0:
        return JsonResponse({"status": "erro", "message": "Produto sem estoque disponivel."}, status=400)

    cart_data = _get_cart_data(request, empresa.id)
    quantidade_atual = int(cart_data.get(str(produto.id), 0))
    quantidade_final = quantidade_atual + quantidade

    if quantidade_final > estoque_disponivel:
        return JsonResponse({
            "status": "erro",
            "message": f"Estoque insuficiente. Restam {estoque_disponivel} unidade(s).",
        }, status=400)

    cart_data[str(produto.id)] = quantidade_final
    _save_cart_data(request, empresa.id, cart_data)

    payload = _build_cart_payload(empresa, _get_cart_data(request, empresa.id))
    _save_cart_data(request, empresa.id, payload["cart"])

    return JsonResponse({
        "status": "sucesso",
        "message": "Produto adicionado ao carrinho.",
        "itens": payload["itens"],
        "total_itens": payload["total_itens"],
        "total_preco": payload["total_preco"],
    })


@require_http_methods(["POST"])
def api_carrinho_remover(request, empresa_id):
    empresa = get_object_or_404(Empresa, pk=empresa_id)
    access_denied = _enforce_company_portal_access(request, empresa)
    if access_denied:
        return access_denied

    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"status": "erro", "message": "JSON invalido."}, status=400)

    try:
        produto_id = int(data.get("produto_id"))
    except (TypeError, ValueError):
        return JsonResponse({"status": "erro", "message": "Produto invalido."}, status=400)

    cart_data = _get_cart_data(request, empresa.id)
    cart_data.pop(str(produto_id), None)
    _save_cart_data(request, empresa.id, cart_data)

    payload = _build_cart_payload(empresa, _get_cart_data(request, empresa.id))
    _save_cart_data(request, empresa.id, payload["cart"])

    return JsonResponse({
        "status": "sucesso",
        "message": "Produto removido do carrinho.",
        "itens": payload["itens"],
        "total_itens": payload["total_itens"],
        "total_preco": payload["total_preco"],
    })


@require_http_methods(["POST"])
def api_carrinho_atualizar(request, empresa_id):
    empresa = get_object_or_404(Empresa, pk=empresa_id)
    access_denied = _enforce_company_portal_access(request, empresa)
    if access_denied:
        return access_denied

    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"status": "erro", "message": "JSON invalido."}, status=400)

    try:
        produto_id = int(data.get("produto_id"))
        quantidade = int(data.get("quantidade", 0))
    except (TypeError, ValueError):
        return JsonResponse({"status": "erro", "message": "Produto ou quantidade invalida."}, status=400)

    produto = Produto.objects.filter(empresa=empresa, ativo=True, pk=produto_id).first()
    if not produto:
        return JsonResponse({"status": "erro", "message": "Produto nao encontrado nesta empresa."}, status=404)

    cart_data = _get_cart_data(request, empresa.id)
    if quantidade <= 0:
        cart_data.pop(str(produto.id), None)
    else:
        estoque_disponivel = max(int(produto.estoque_disponivel), 0)
        if quantidade > estoque_disponivel:
            return JsonResponse({
                "status": "erro",
                "message": f"Estoque insuficiente. Restam {estoque_disponivel} unidade(s).",
            }, status=400)
        cart_data[str(produto.id)] = quantidade

    _save_cart_data(request, empresa.id, cart_data)
    payload = _build_cart_payload(empresa, _get_cart_data(request, empresa.id))
    _save_cart_data(request, empresa.id, payload["cart"])

    return JsonResponse({
        "status": "sucesso",
        "message": "Carrinho atualizado.",
        "itens": payload["itens"],
        "total_itens": payload["total_itens"],
        "total_preco": payload["total_preco"],
    })


def empresa_detail(request, empresa_id):
    empresa = get_object_or_404(Empresa, pk=empresa_id)
    access_denied = _enforce_company_portal_access(request, empresa)
    if access_denied:
        return access_denied

    if not request.session.session_key:
        request.session.create()

    profile = get_business_profile(empresa.tipo)
    success_booking = None
    success_client = None
    success_payment = None
    success_plan = None
    booking_error_message = ""

    if request.method == "POST":
        form = PublicBookingForm(request.POST, empresa=empresa, session_key=request.session.session_key)
        if form.is_valid():
            try:
                result = form.save()
            except ValidationError:
                booking_error_message = "Nao foi possivel concluir sua reserva agora. Verifique os campos destacados e tente novamente."
                messages.error(request, booking_error_message)
            else:
                success_booking = result["agendamento"]
                success_client = result["cliente"]
                success_plan = result["plano"]
                _set_portal_cliente(request, empresa.id, success_client.id)
                _clear_cart_data(request, empresa.id)
                request.session.modified = True

                if success_plan:
                    messages.success(request, "Pacote mensal criado com sucesso. Seus agendamentos ja estao disponiveis em Meus agendamentos.")
                else:
                    messages.success(request, "Reserva criada com sucesso. Confira os detalhes em Meus agendamentos.")

                form = PublicBookingForm(empresa=empresa, initial={
                    "nome": success_client.nome,
                    "email": success_client.email,
                    "telefone": success_client.telefone,
                    "documento": success_client.documento,
                    "data_nascimento": success_client.data_nascimento,
                }, session_key=request.session.session_key)
        else:
            booking_error_message = "Nao foi possivel concluir sua reserva. Revise os campos obrigatorios e tente novamente."
            messages.error(request, booking_error_message)
    else:
        form = PublicBookingForm(empresa=empresa, session_key=request.session.session_key)

    # Produtos em destaque (top 3)
    top_produtos = (
        Produto.objects
        .filter(empresa=empresa, ativo=True, destaque_publico=True)
        .order_by('nome')
        [:3]
    )
    cart_payload = _build_cart_payload(empresa, _get_cart_data(request, empresa.id))
    _save_cart_data(request, empresa.id, cart_payload["cart"])

    context = {
        "empresa": empresa,
        "profile": profile,
        "form": form,
        "cliente_portal_autenticado": bool(_get_portal_cliente(request, empresa)),
        "servicos": Servico.objects.filter(empresa=empresa, ativo=True).order_by("nome"),
        "produtos": top_produtos,
        "produtos_total": Produto.objects.filter(empresa=empresa, ativo=True).count(),
        "cart_total_items": cart_payload["total_itens"],
        "profissionais": Profissional.objects.filter(empresa=empresa, ativo=True).order_by("nome"),
        "success_booking": success_booking,
        "success_client": success_client,
        "success_plan": success_plan,
        "booking_error_message": booking_error_message,
    }
    return render(request, "core/cliente_empresa.html", context)


def password_recovery_request(request):
    initial = {}
    if request.GET.get("tipo") == "cliente":
        initial["account_type"] = "client"
    if request.user.is_authenticated:
        messages.warning(request, "Voce ja esta autenticado. Use o menu da conta para trocar sua senha.")
        return redirect("dashboard_home")

    empresa_id = request.GET.get("empresa")
    if empresa_id and empresa_id.isdigit():
        empresa = Empresa.objects.filter(pk=int(empresa_id)).first()
        if empresa:
            initial["empresa"] = empresa

    if request.method == "POST":
        form = PasswordRecoveryRequestForm(request.POST)
        if form.is_valid():
            account_type = form.cleaned_data["account_type"]
            channel = form.cleaned_data["channel"]
            identifier = form.cleaned_data["identifier"]
            empresa = form.cleaned_data.get("empresa")

            target_user = None
            target_cliente = None
            destination = ""
            company = empresa

            if account_type == "internal":
                target_user = _find_internal_user(identifier)
                if not target_user:
                    form.add_error("identifier", "Conta interna nao encontrada com este email ou WhatsApp.")
                else:
                    destination = _get_internal_destination(target_user, channel)
                    try:
                        company = target_user.empresa
                    except Empresa.DoesNotExist:
                        company = getattr(getattr(target_user, "profissional_profile", None), "empresa", None)
                    if not destination:
                        form.add_error("channel", f"Esta conta nao possui {channel} cadastrado para recuperacao.")
            else:
                target_cliente = _find_portal_cliente_by_identifier(empresa, identifier)
                if not target_cliente:
                    form.add_error("identifier", "Cliente nao encontrado nesta empresa.")
                elif channel == "email" and not target_cliente.email:
                    form.add_error("channel", "Este cliente nao possui email cadastrado.")
                elif channel == "whatsapp" and not target_cliente.telefone:
                    form.add_error("channel", "Este cliente nao possui WhatsApp cadastrado.")
                else:
                    destination = target_cliente.email if channel == "email" else target_cliente.telefone

            if not form.errors:
                code = _build_numeric_code()
                recovery = PasswordRecoveryCode.objects.create(
                    account_type=account_type,
                    canal=channel,
                    codigo=code,
                    expira_em=timezone.now() + timedelta(minutes=10),
                    user=target_user,
                    cliente=target_cliente,
                    empresa=company,
                )
                _dispatch_recovery_code(account_type, destination, channel, code, company)
                request.session["password_recovery_id"] = recovery.id
                request.session.modified = True
                messages.success(request, f"Codigo enviado para {_mask_destination(destination)}.")
                return redirect("password_recovery_confirm")
    else:
        form = PasswordRecoveryRequestForm(initial=initial)

    return render(request, "registration/password_recovery_request.html", {"form": form})


def password_recovery_confirm(request):
    recovery_id = request.session.get("password_recovery_id")
    recovery = PasswordRecoveryCode.objects.filter(pk=recovery_id).select_related("user", "cliente", "empresa").first()
    if request.user.is_authenticated:
        messages.warning(request, "Voce ja esta autenticado. Use o menu da conta para trocar sua senha.")
        return redirect("dashboard_home")

    if not recovery or not recovery.disponivel:
        request.session.pop("password_recovery_id", None)
        messages.warning(request, "Solicite um novo codigo para continuar.")
        return redirect("password_recovery_request")

    if recovery.account_type == "internal":
        destination = _get_internal_destination(recovery.user, recovery.canal)
    else:
        destination = recovery.cliente.email if recovery.canal == "email" else recovery.cliente.telefone

    if request.method == "POST":
        form = PasswordRecoveryConfirmForm(request.POST)
        if form.is_valid():
            if form.cleaned_data["code"] != recovery.codigo:
                form.add_error("code", "Codigo invalido ou expirado.")
            else:
                new_password = form.cleaned_data["new_password1"]
                if recovery.account_type == "internal" and recovery.user:
                    recovery.user.set_password(new_password)
                    recovery.user.save(update_fields=["password"])
                    messages.success(request, "Senha atualizada com sucesso. Faça login para continuar.")
                    redirect_target = redirect("login")
                elif recovery.account_type == "client" and recovery.cliente:
                    recovery.cliente.set_portal_password(new_password)
                    recovery.cliente.save(update_fields=["portal_password", "portal_password_updated_at"])
                    _set_portal_cliente(request, recovery.empresa_id, recovery.cliente_id)
                    messages.success(request, "Senha do portal atualizada com sucesso.")
                    redirect_target = redirect("cliente_empresa", empresa_id=recovery.empresa_id)
                else:
                    form.add_error(None, "Nao foi possivel concluir a recuperacao desta conta.")
                    redirect_target = None

                if redirect_target is not None:
                    recovery.usado_em = timezone.now()
                    recovery.save(update_fields=["usado_em"])
                    request.session.pop("password_recovery_id", None)
                    return redirect_target
    else:
        form = PasswordRecoveryConfirmForm()

    return render(request, "registration/password_recovery_confirm.html", {
        "form": form,
        "recovery": recovery,
        "masked_destination": _mask_destination(destination),
    })


def available_slots_api(request, empresa_id):
    empresa = get_object_or_404(Empresa, pk=empresa_id)
    access_denied = _enforce_company_portal_access(request, empresa)
    if access_denied:
        return access_denied

    servico_id = request.GET.get("servico")
    profissional_id = request.GET.get("profissional")
    hold_token = request.GET.get("hold_token")
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
        exclude_hold_token=hold_token,
    )

    payload = {
        "slots": [{"value": slot.strftime("%H:%M"), "label": slot.strftime("%H:%M")} for slot in slots],
        "message": "Horarios disponiveis carregados." if slots else "Nenhum horario livre para essa combinacao.",
    }
    return JsonResponse(payload)


@require_http_methods(["POST"])
def slot_hold_api(request, empresa_id):
    empresa = get_object_or_404(Empresa, pk=empresa_id)
    access_denied = _enforce_company_portal_access(request, empresa)
    if access_denied:
        return access_denied

    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"status": "erro", "message": "JSON invalido."}, status=400)

    servico_id = payload.get("servico")
    profissional_id = payload.get("profissional")
    data_raw = payload.get("data")
    hora_raw = payload.get("hora")
    hold_token = coerce_hold_token((payload.get("hold_token") or "").strip())

    if not all([servico_id, profissional_id, data_raw, hora_raw]):
        return JsonResponse({"status": "erro", "message": "Preencha servico, profissional, data e horario."}, status=400)

    servico = Servico.objects.filter(empresa=empresa, ativo=True, pk=servico_id).first()
    profissional = Profissional.objects.filter(empresa=empresa, ativo=True, pk=profissional_id).first()
    if not servico or not profissional:
        return JsonResponse({"status": "erro", "message": "Servico ou profissional invalido."}, status=400)

    try:
        data = forms.DateField().clean(data_raw)
        hora = forms.TimeField().clean(hora_raw)
    except ValidationError:
        return JsonResponse({"status": "erro", "message": "Data ou horario invalido."}, status=400)

    if data < timezone.localdate():
        return JsonResponse({"status": "erro", "message": "Nao e possivel reservar horario em data passada."}, status=400)

    if not request.session.session_key:
        request.session.create()
    session_key = request.session.session_key or ""

    hold_minutes = max(int(getattr(settings, "SLOT_HOLD_MINUTES", 10)), 1)
    reservado_ate = timezone.now() + timedelta(minutes=hold_minutes)

    with transaction.atomic():
        acquire_schedule_lock(empresa=empresa, profissional=profissional, data=data)

        SlotHold.objects.filter(status="active", reservado_ate__lte=timezone.now()).update(status="expired")

        conflito = find_schedule_conflict(
            empresa=empresa,
            profissional=profissional,
            servico=servico,
            data=data,
            hora=hora,
            exclude_hold_token=hold_token,
        )
        if conflito:
            if conflito.__class__.__name__ == "SlotHold":
                message = "Esse horario foi reservado temporariamente por outro cliente."
            else:
                message = "Esse horario acabou de ser ocupado."
            return JsonResponse({"status": "erro", "message": message}, status=409)

        hold = None
        if hold_token:
            hold = SlotHold.objects.select_for_update().filter(
                token=hold_token,
                empresa=empresa,
                session_key=session_key,
            ).first()

        if hold is None:
            hold = SlotHold(
                empresa=empresa,
                profissional=profissional,
                servico=servico,
                data=data,
                hora=hora,
                reservado_ate=reservado_ate,
                status="active",
                session_key=session_key,
            )
        else:
            hold.profissional = profissional
            hold.servico = servico
            hold.data = data
            hold.hora = hora
            hold.reservado_ate = reservado_ate
            hold.status = "active"

        hold.save()

        SlotHold.objects.filter(
            empresa=empresa,
            session_key=session_key,
            status="active",
        ).exclude(pk=hold.pk).update(status="released")

    return JsonResponse({
        "status": "sucesso",
        "hold_token": str(hold.token),
        "expires_at": hold.reservado_ate.isoformat(),
        "ttl_seconds": hold_minutes * 60,
        "message": f"Horario reservado por {hold_minutes} minutos.",
    })


@require_http_methods(["POST"])
def portal_enviar_otp_api(request, empresa_id):
    empresa = get_object_or_404(Empresa, pk=empresa_id)
    access_denied = _enforce_company_portal_access(request, empresa)
    if access_denied:
        return access_denied

    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"status": "erro", "message": "JSON inválido."}, status=400)

    telefone = re.sub(r"\D", "", data.get("telefone", ""))
    email = (data.get("email") or "").strip().lower()
    canal = data.get("canal") or ("whatsapp" if telefone else "email")

    if not telefone and not email:
        return JsonResponse({"status": "erro", "message": "Informe telefone ou email para receber o código."}, status=400)

    cliente = None
    if telefone:
        cliente = Pessoa.objects.filter(empresa=empresa, telefone=telefone).first()
    if not cliente and email:
        cliente = Pessoa.objects.filter(empresa=empresa, email=email).first()

    if not cliente:
        return JsonResponse({"status": "erro", "message": "Cliente não encontrado nesta empresa."}, status=404)

    if canal == "email" and not cliente.email:
        return JsonResponse({"status": "erro", "message": "Este cliente não possui email cadastrado."}, status=400)

    codigo = "".join(secrets.choice("0123456789") for _ in range(6))
    otp = ClientePortalOTP.objects.create(
        empresa=empresa,
        cliente=cliente,
        canal=canal,
        codigo=codigo,
        expira_em=timezone.now() + timedelta(minutes=10),
    )

    mensagem = f"Seu código EasySchedule ({empresa.nome}) é {codigo}. Valido por 10 minutos."
    if canal == "whatsapp":
        send_whatsapp_message(cliente.telefone, mensagem)
        destino = cliente.telefone
    else:
        send_email_message(cliente.email, f"Código de acesso - {empresa.nome}", mensagem)
        destino = cliente.email

    payload = {
        "status": "sucesso",
        "message": "Código enviado com sucesso.",
        "canal": canal,
        "destino": destino,
        "otp_id": otp.id,
    }
    if settings.DEBUG:
        payload["dev_code"] = codigo
    return JsonResponse(payload)


@require_http_methods(["POST"])
def portal_validar_otp_api(request, empresa_id):
    empresa = get_object_or_404(Empresa, pk=empresa_id)
    access_denied = _enforce_company_portal_access(request, empresa)
    if access_denied:
        return access_denied

    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"status": "erro", "message": "JSON inválido."}, status=400)

    codigo = re.sub(r"\D", "", data.get("codigo", ""))
    otp_id = data.get("otp_id")
    if len(codigo) != 6 or not otp_id:
        return JsonResponse({"status": "erro", "message": "Código inválido."}, status=400)

    otp = ClientePortalOTP.objects.filter(pk=otp_id, empresa=empresa).select_related("cliente").first()
    if not otp or otp.codigo != codigo or not otp.disponivel:
        return JsonResponse({"status": "erro", "message": "Código inválido ou expirado."}, status=400)

    otp.usado_em = timezone.now()
    otp.save(update_fields=["usado_em"])
    _set_portal_cliente(request, empresa.id, otp.cliente_id)

    ClientePortalPreferencia.objects.get_or_create(empresa=empresa, cliente=otp.cliente)

    return JsonResponse({
        "status": "sucesso",
        "message": "Acesso liberado ao portal do cliente.",
        "cliente": {
            "nome": otp.cliente.nome,
            "telefone": otp.cliente.telefone,
            "email": otp.cliente.email or "",
        }
    })


@require_http_methods(["POST"])
def portal_password_login_api(request, empresa_id):
    empresa = get_object_or_404(Empresa, pk=empresa_id)
    access_denied = _enforce_company_portal_access(request, empresa)
    if access_denied:
        return access_denied

    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"status": "erro", "message": "JSON inválido."}, status=400)

    identifier = (data.get("identifier") or "").strip().lower()
    password = data.get("password") or ""

    if not identifier or not password:
        return JsonResponse({"status": "erro", "message": "Informe email ou WhatsApp e sua senha."}, status=400)

    cliente = _find_portal_cliente_by_identifier(empresa, identifier)
    if not cliente:
        return JsonResponse({"status": "erro", "message": "Cliente não encontrado nesta empresa."}, status=404)

    if not cliente.has_portal_password:
        return JsonResponse({
            "status": "erro",
            "message": "Voce ainda nao definiu senha para o portal. Use o codigo rapido ou recupere a senha.",
        }, status=400)

    if not cliente.check_portal_password(password):
        return JsonResponse({"status": "erro", "message": "Senha incorreta."}, status=400)

    _set_portal_cliente(request, empresa.id, cliente.id)
    ClientePortalPreferencia.objects.get_or_create(empresa=empresa, cliente=cliente)

    return JsonResponse({
        "status": "sucesso",
        "message": "Acesso liberado ao portal do cliente.",
        "cliente": {
            "nome": cliente.nome,
            "telefone": cliente.telefone,
            "email": cliente.email or "",
        }
    })


@require_http_methods(["POST"])
def portal_logout_api(request, empresa_id):
    _clear_portal_cliente(request, empresa_id)
    return JsonResponse({"status": "sucesso"})


@require_http_methods(["POST"])
def cliente_agendamentos_api(request, empresa_id):
    empresa = get_object_or_404(Empresa, pk=empresa_id)
    access_denied = _enforce_company_portal_access(request, empresa)
    if access_denied:
        return access_denied

    cliente = _get_portal_cliente(request, empresa)
    if cliente is None:
        try:
            data = json.loads(request.body or "{}")
        except json.JSONDecodeError:
            return JsonResponse({"status": "erro", "message": "JSON inválido."}, status=400)

        telefone = re.sub(r"\D", "", data.get("telefone", ""))
        documento = re.sub(r"\D", "", data.get("documento", ""))
        if not telefone:
            return JsonResponse({"status": "erro", "message": "Faça login no portal para consultar sem repetir seus dados."}, status=401)

        cliente = Pessoa.objects.filter(empresa=empresa, telefone=telefone).first()
        if not cliente:
            return JsonResponse({"status": "sucesso", "cliente": None, "agendamentos": []})
        if documento and (cliente.documento or "") != documento:
            return JsonResponse({"status": "erro", "message": "Documento não confere para este telefone."}, status=403)

        _set_portal_cliente(request, empresa.id, cliente.id)

    hoje = timezone.localdate()
    agendamentos = (
        Agendamento.objects.filter(empresa=empresa, cliente=cliente)
        .select_related("servico", "profissional")
        .order_by("-data", "-hora")[:20]
    )

    payload = []
    for ag in agendamentos:
        payload.append({
            "id": ag.id,
            "servico": ag.servico.nome,
            "profissional": ag.profissional.nome,
            "data": ag.data.strftime("%d/%m/%Y"),
            "hora": ag.hora.strftime("%H:%M"),
            "status": ag.get_status_display(),
            "status_raw": ag.status,
            "pagamento_status": ag.get_pagamento_status_display(),
            "pagamento_url": "",
            "tipo": "Proximo" if ag.data >= hoje else "Historico",
            "valor": str(ag.servico.preco),
            "can_change": _can_client_change_appointment(ag),
            "agendamento_iso_date": ag.data.isoformat(),
            "agendamento_hour": ag.hora.strftime("%H:%M"),
        })

    return JsonResponse({
        "status": "sucesso",
        "cliente": {
            "id": cliente.id,
            "nome": cliente.nome,
            "telefone": cliente.telefone,
            "email": cliente.email or "",
            "documento": cliente.documento or "",
        },
        "agendamentos": payload,
    })


@require_http_methods(["POST"])
def cliente_agendamento_cancelar_api(request, empresa_id, agendamento_id):
    empresa = get_object_or_404(Empresa, pk=empresa_id)
    cliente = _get_portal_cliente(request, empresa)
    if not cliente:
        return JsonResponse({"status": "erro", "message": "Faça login no portal para cancelar."}, status=401)

    agendamento = get_object_or_404(Agendamento, pk=agendamento_id, empresa=empresa, cliente=cliente)
    if not _can_client_change_appointment(agendamento):
        return JsonResponse({"status": "erro", "message": "Este agendamento não pode mais ser cancelado."}, status=400)

    agendamento.status = "cancelado"
    agendamento.save(update_fields=["status"])

    return JsonResponse({"status": "sucesso", "message": "Agendamento cancelado com sucesso."})


@require_http_methods(["POST"])
def cliente_agendamento_remarcar_api(request, empresa_id, agendamento_id):
    empresa = get_object_or_404(Empresa, pk=empresa_id)
    cliente = _get_portal_cliente(request, empresa)
    if not cliente:
        return JsonResponse({"status": "erro", "message": "Faça login no portal para remarcar."}, status=401)

    agendamento = get_object_or_404(Agendamento, pk=agendamento_id, empresa=empresa, cliente=cliente)
    if not _can_client_change_appointment(agendamento):
        return JsonResponse({"status": "erro", "message": "Este agendamento não pode mais ser remarcado."}, status=400)

    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"status": "erro", "message": "JSON inválido."}, status=400)

    nova_data_raw = data.get("data")
    nova_hora_raw = data.get("hora")
    if not nova_data_raw or not nova_hora_raw:
        return JsonResponse({"status": "erro", "message": "Informe nova data e novo horário."}, status=400)

    try:
        nova_data = forms.DateField().clean(nova_data_raw)
        nova_hora = forms.TimeField().clean(nova_hora_raw)
    except ValidationError:
        return JsonResponse({"status": "erro", "message": "Data ou horário inválido."}, status=400)

    agendamento.data = nova_data
    agendamento.hora = nova_hora
    if agendamento.status == "cancelado":
        agendamento.status = "pendente"

    try:
        agendamento.full_clean()
        agendamento.save()
    except ValidationError as exc:
        msg = "; ".join([f"{k}: {', '.join(v)}" for k, v in exc.message_dict.items()]) if hasattr(exc, "message_dict") else str(exc)
        return JsonResponse({"status": "erro", "message": msg}, status=400)

    return JsonResponse({
        "status": "sucesso",
        "message": "Agendamento remarcado com sucesso.",
        "data": agendamento.data.strftime("%d/%m/%Y"),
        "hora": agendamento.hora.strftime("%H:%M"),
    })


def cliente_minha_conta(request, empresa_id):
    empresa = get_object_or_404(Empresa, pk=empresa_id)
    access_denied = _enforce_company_portal_access(request, empresa)
    if access_denied:
        return access_denied

    cliente = _get_portal_cliente(request, empresa)
    if not cliente:
        messages.warning(request, "Faça login no portal do cliente para acessar sua conta.")
        return redirect("cliente_empresa", empresa_id=empresa.id)

    pref, _ = ClientePortalPreferencia.objects.get_or_create(empresa=empresa, cliente=cliente)

    if request.method == "POST":
        cliente.nome = (request.POST.get("nome") or cliente.nome).strip()
        cliente.email = (request.POST.get("email") or "").strip().lower()
        cliente.telefone = re.sub(r"\D", "", request.POST.get("telefone", cliente.telefone or ""))
        cliente.documento = re.sub(r"\D", "", request.POST.get("documento", cliente.documento or ""))

        senha_atual = request.POST.get("senha_atual", "")
        nova_senha = request.POST.get("nova_senha", "")
        confirmar_nova_senha = request.POST.get("confirmar_nova_senha", "")
        password_error = None

        if senha_atual or nova_senha or confirmar_nova_senha:
            if cliente.has_portal_password and not cliente.check_portal_password(senha_atual):
                password_error = "A senha atual do portal nao confere."
            elif len(nova_senha) < 6:
                password_error = "Use pelo menos 6 caracteres na nova senha do portal."
            elif nova_senha != confirmar_nova_senha:
                password_error = "As novas senhas do portal nao conferem."

        cliente.save()

        if password_error:
            messages.error(request, password_error)
        elif nova_senha:
            cliente.set_portal_password(nova_senha)
            cliente.save(update_fields=["portal_password", "portal_password_updated_at"])
            messages.success(request, "Senha do portal atualizada com sucesso.")

        pref.receber_whatsapp = request.POST.get("receber_whatsapp") == "on"
        pref.receber_email = request.POST.get("receber_email") == "on"
        pref.receber_marketing = request.POST.get("receber_marketing") == "on"
        pref.save()
        if not password_error:
            messages.success(request, "Sua conta foi atualizada com sucesso.")

    hoje = timezone.localdate()
    historico = (
        Agendamento.objects.filter(empresa=empresa, cliente=cliente)
        .select_related("servico", "profissional")
        .order_by("-data", "-hora")
    )
    proximos = historico.filter(data__gte=hoje, status__in=["pendente", "confirmado"])[:10]
    anteriores = historico.filter(data__lt=hoje)[:20]

    return render(request, "core/cliente_minha_conta.html", {
        "empresa": empresa,
        "profile": get_business_profile(empresa.tipo),
        "cliente": cliente,
        "preferencia": pref,
        "proximos_agendamentos": proximos,
        "historico_agendamentos": anteriores,
        "total_agendamentos": historico.count(),
        "cliente_has_portal_password": cliente.has_portal_password,
    })


def healthz(request):
    return JsonResponse({
        "status": "ok",
        "service": "easyschedule",
        "request_id": getattr(request, "request_id", "-"),
    })


def readyz(request):
    checks = {"database": "ok"}
    status = "ok"
    status_code = 200

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        checks["database"] = "error"
        status = "degraded"
        status_code = 503

    return JsonResponse({
        "status": status,
        "checks": checks,
        "request_id": getattr(request, "request_id", "-"),
    }, status=status_code)


@require_http_methods(["POST"])
def stripe_webhook(request):
    webhook_secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", "")
    if not webhook_secret or webhook_secret == "whsec_not_configured":
        return JsonResponse({"status": "erro", "message": "Webhook Stripe nao configurado."}, status=503)

    payload = request.body
    signature = request.META.get("HTTP_STRIPE_SIGNATURE", "")

    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=signature,
            secret=webhook_secret,
        )
    except ValueError:
        return JsonResponse({"status": "erro", "message": "Payload invalido."}, status=400)
    except stripe.error.SignatureVerificationError:
        return JsonResponse({"status": "erro", "message": "Assinatura invalida."}, status=400)

    event_payload = event.to_dict_recursive() if hasattr(event, "to_dict_recursive") else dict(event)
    event_id = event_payload.get("id")
    event_type = event_payload.get("type", "unknown")

    if not event_id:
        return JsonResponse({"status": "erro", "message": "Evento sem id."}, status=400)

    with transaction.atomic():
        webhook_event, created = StripeWebhookEvent.objects.get_or_create(
            event_id=event_id,
            defaults={
                "event_type": event_type,
                "livemode": bool(event_payload.get("livemode", False)),
                "processing_status": "processed",
                "payload": event_payload,
            },
        )

    if not created:
        return JsonResponse({"status": "ok", "result": "duplicate", "event_id": event_id})

    supported_event_types = {
        "checkout.session.completed",
        "checkout.session.async_payment_succeeded",
        "checkout.session.async_payment_failed",
    }

    if event_type not in supported_event_types:
        webhook_event.processing_status = "ignored"
        webhook_event.save(update_fields=["processing_status"])
        return JsonResponse({"status": "ok", "result": "ignored", "event_id": event_id})

    logger.info("Stripe webhook processado: %s", event_type)
    return JsonResponse({"status": "ok", "result": "processed", "event_id": event_id})

def service_worker_js(_request):
        content = """
const CACHE_NAME = 'easyschedule-pwa-v1';
const STATIC_URLS = ['/static/css/theme.css'];

self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_URLS)).then(() => self.skipWaiting())
    );
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))))
            .then(() => self.clients.claim())
    );
});

self.addEventListener('fetch', (event) => {
    if (event.request.method !== 'GET') return;

    const url = new URL(event.request.url);

    // Só faz cache de arquivos estáticos; tudo mais vai direto ao servidor
    if (url.pathname.startsWith('/static/')) {
        event.respondWith(
            caches.match(event.request).then((cached) => {
                if (cached) return cached;
                return fetch(event.request).then((response) => {
                    const clone = response.clone();
                    caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
                    return response;
                });
            })
        );
        return;
    }

    // Para páginas e dados: rede primeiro, cache só se offline
    event.respondWith(
        fetch(event.request).catch(() => caches.match(event.request))
    );
});
"""
        return HttpResponse(content, content_type="application/javascript")

