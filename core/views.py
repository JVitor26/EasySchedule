from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth import logout
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, render, redirect
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.db.models import Count
from django.utils import timezone
import json
import re
from datetime import timedelta
import secrets

from agendamentos.availability import list_available_slots
from agendamentos.models import Pagamento, PlanoMensal, AgendamentoProduto, Agendamento
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
from .models import ClientePortalOTP, ClientePortalPreferencia, PasswordRecoveryCode
from .notifications import send_whatsapp_message, send_email_message

from .forms import (
    PasswordRecoveryConfirmForm,
    PasswordRecoveryRequestForm,
    PublicBookingForm,
    PublicCheckoutForm,
)


def home(request):
    if request.user.is_authenticated:
        empresas = get_accessible_empresas(request)
        template = "core/cliente_portal.html"
        context = {"empresas": empresas}
    elif getattr(request, "resolver_match", None) and request.resolver_match.url_name == "home":
        template = "home.html"
        context = {}
    else:
        empresas = Empresa.objects.all().order_by("nome")
        template = "core/cliente_publico.html"
        context = {"empresas": empresas}
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


def _cart_session_key(empresa_id):
    return f"carrinho_empresa_{empresa_id}"


def _get_company_cart(request, empresa_id):
    key = _cart_session_key(empresa_id)
    carrinho = request.session.get(key)
    if not isinstance(carrinho, dict):
        carrinho = {}
        request.session[key] = carrinho
    return carrinho, key


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


def empresa_detail(request, empresa_id):
    empresa = get_object_or_404(Empresa, pk=empresa_id)
    access_denied = _enforce_company_portal_access(request, empresa)
    if access_denied:
        return access_denied

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
                request.session.pop(_cart_session_key(empresa.id), None)
                request.session.modified = True
                form = PublicBookingForm(empresa=empresa, initial={
                    "nome": success_client.nome,
                    "email": success_client.email,
                    "telefone": success_client.telefone,
                    "documento": success_client.documento,
                    "data_nascimento": success_client.data_nascimento,
                })
    else:
        form = PublicBookingForm(empresa=empresa)

    # Produtos mais vendidos (top 3)
    top_produtos = (
        Produto.objects
        .filter(empresa=empresa, ativo=True, destaque_publico=True)
        .annotate(vendas=Count('agendamentos'))
        .order_by('-vendas', 'nome')
        [:3]
    )

    context = {
        "empresa": empresa,
        "profile": profile,
        "form": form,
        "cliente_portal_autenticado": bool(_get_portal_cliente(request, empresa)),
        "servicos": Servico.objects.filter(empresa=empresa, ativo=True).order_by("nome"),
        "produtos": top_produtos,
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


# ============ VIEWS DE PRODUTOS E CARRINHO ============

def loja_produtos(request, empresa_id):
    """Página de loja de produtos para o cliente"""
    empresa = get_object_or_404(Empresa, pk=empresa_id)
    access_denied = _enforce_company_portal_access(request, empresa)
    if access_denied:
        return access_denied

    profile = get_business_profile(empresa.tipo)
    categoria = request.GET.get("categoria", "")
    busca = request.GET.get("busca", "")
    
    produtos = Produto.objects.filter(
        empresa=empresa,
        ativo=True,
        destaque_publico=True,
    )
    
    if categoria:
        produtos = produtos.filter(categoria=categoria)
    if busca:
        produtos = produtos.filter(nome__icontains=busca) | produtos.filter(descricao__icontains=busca)
    
    categorias = Produto.objects.filter(
        empresa=empresa,
        ativo=True,
        destaque_publico=True,
    ).values_list("categoria", flat=True).distinct().filter(categoria__gt="")
    
    context = {
        "empresa": empresa,
        "profile": profile,
        "produtos": produtos.order_by("nome"),
        "categorias": sorted(set(categorias)),
        "categoria_selecionada": categoria,
        "busca": busca,
    }
    return render(request, "core/loja_produtos.html", context)


@require_http_methods(["POST"])
def api_carrinho_adicionar(request, empresa_id):
    """API para adicionar produto ao carrinho (sessão ou temporário)"""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"status": "erro", "message": "JSON inválido"}, status=400)
    
    empresa = get_object_or_404(Empresa, pk=empresa_id)
    access_denied = _enforce_company_portal_access(request, empresa)
    if access_denied:
        return access_denied

    produto_id = data.get("produto_id")
    quantidade = int(data.get("quantidade", 1))
    
    if quantidade <= 0:
        return JsonResponse({"status": "erro", "message": "Quantidade deve ser maior que 0"}, status=400)
    
    produto = get_object_or_404(Produto, pk=produto_id, empresa=empresa, ativo=True)
    
    # Verificar estoque disponível
    if produto.estoque_disponivel < quantidade:
        return JsonResponse({
            "status": "erro",
            "message": f"Estoque insuficiente. Disponível: {produto.estoque_disponivel}"
        }, status=400)
    
    # Gerenciar carrinho na sessão
    carrinho, carrinho_key = _get_company_cart(request, empresa.id)
    produto_id_str = str(produto_id)
    
    if produto_id_str in carrinho:
        total = carrinho[produto_id_str]["quantidade"] + quantidade
        if total > produto.estoque_disponivel:
            return JsonResponse({
                "status": "erro",
                "message": f"Estoque insuficiente para essa quantidade. Disponível: {produto.estoque_disponivel}"
            }, status=400)
        carrinho[produto_id_str]["quantidade"] = total
    else:
        carrinho[produto_id_str] = {
            "quantidade": quantidade,
            "preco": str(produto.preco),
            "nome": produto.nome,
        }
    
    request.session[carrinho_key] = carrinho
    request.session.modified = True
    
    total_itens = sum(item["quantidade"] for item in carrinho.values())
    
    return JsonResponse({
        "status": "sucesso",
        "message": f"{produto.nome} adicionado ao carrinho",
        "total_itens": total_itens,
        "carrinho": carrinho,
    })


@require_http_methods(["POST"])
def api_carrinho_remover(request, empresa_id):
    """API para remover produto do carrinho"""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"status": "erro", "message": "JSON inválido"}, status=400)
    
    empresa = get_object_or_404(Empresa, pk=empresa_id)
    access_denied = _enforce_company_portal_access(request, empresa)
    if access_denied:
        return access_denied

    produto_id = str(data.get("produto_id"))
    carrinho, carrinho_key = _get_company_cart(request, empresa.id)
    
    if produto_id in carrinho:
        nome_produto = carrinho[produto_id]["nome"]
        del carrinho[produto_id]
        request.session[carrinho_key] = carrinho
        request.session.modified = True
        total_itens = sum(item["quantidade"] for item in carrinho.values())
        
        return JsonResponse({
            "status": "sucesso",
            "message": f"{nome_produto} removido do carrinho",
            "total_itens": total_itens,
            "carrinho": carrinho,
        })
    
    return JsonResponse({"status": "erro", "message": "Produto não encontrado no carrinho"}, status=404)


@require_http_methods(["POST"])
def api_carrinho_atualizar(request, empresa_id):
    """API para atualizar quantidade de produto no carrinho"""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"status": "erro", "message": "JSON inválido"}, status=400)
    
    empresa = get_object_or_404(Empresa, pk=empresa_id)
    access_denied = _enforce_company_portal_access(request, empresa)
    if access_denied:
        return access_denied

    produto_id = str(data.get("produto_id"))
    quantidade = int(data.get("quantidade", 0))
    
    if quantidade <= 0:
        return JsonResponse({"status": "erro", "message": "Quantidade deve ser maior que 0"}, status=400)
    
    produto = get_object_or_404(Produto, pk=int(produto_id), empresa=empresa, ativo=True)
    
    if produto.estoque_disponivel < quantidade:
        return JsonResponse({
            "status": "erro",
            "message": f"Estoque insuficiente. Disponível: {produto.estoque_disponivel}"
        }, status=400)
    
    carrinho, carrinho_key = _get_company_cart(request, empresa.id)
    
    if produto_id in carrinho:
        carrinho[produto_id]["quantidade"] = quantidade
        request.session[carrinho_key] = carrinho
        request.session.modified = True
        total_itens = sum(item["quantidade"] for item in carrinho.values())
        
        return JsonResponse({
            "status": "sucesso",
            "message": "Quantidade atualizada",
            "total_itens": total_itens,
            "carrinho": carrinho,
        })
    
    return JsonResponse({"status": "erro", "message": "Produto não encontrado no carrinho"}, status=404)


def api_carrinho_listar(request, empresa_id):
    """API para listar itens do carrinho"""
    empresa = get_object_or_404(Empresa, pk=empresa_id)
    access_denied = _enforce_company_portal_access(request, empresa)
    if access_denied:
        return access_denied

    carrinho, carrinho_key = _get_company_cart(request, empresa.id)
    
    # Enriquecer carrinho com dados do banco
    itens = []
    total_preco = 0
    ids_invalidos = []
    
    for produto_id_str, item in carrinho.items():
        try:
            produto = Produto.objects.get(pk=int(produto_id_str), empresa=empresa)
            preco_total = float(item["preco"]) * item["quantidade"]
            itens.append({
                "produto_id": int(produto_id_str),
                "nome": produto.nome,
                "preco": str(produto.preco),
                "quantidade": item["quantidade"],
                "preco_total": str(preco_total),
                "estoque_disponivel": produto.estoque_disponivel,
            })
            total_preco += preco_total
        except Produto.DoesNotExist:
            ids_invalidos.append(produto_id_str)
    for pid in ids_invalidos:
        del carrinho[pid]
    
    request.session[carrinho_key] = carrinho
    request.session.modified = True
    
    return JsonResponse({
        "status": "sucesso",
        "itens": itens,
        "total_itens": sum(item["quantidade"] for item in itens),
        "total_preco": str(total_preco),
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
        pagamento = ag.payment_record
        payment_url = ""
        if pagamento and pagamento.status != "pago":
            payment_url = f"/cliente/pagamento/{pagamento.referencia_publica}/"

        payload.append({
            "id": ag.id,
            "servico": ag.servico.nome,
            "profissional": ag.profissional.nome,
            "data": ag.data.strftime("%d/%m/%Y"),
            "hora": ag.hora.strftime("%H:%M"),
            "status": ag.get_status_display(),
            "status_raw": ag.status,
            "tipo": "Proximo" if ag.data >= hoje else "Historico",
            "valor": str(ag.servico.preco),
            "pagamento_status": pagamento.get_status_display() if pagamento else "-",
            "pagamento_url": payment_url,
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

    pagamento = agendamento.payment_record
    if pagamento and pagamento.status == "pendente":
        pagamento.status = "cancelado"
        pagamento.save(update_fields=["status", "atualizado_em"])

    for item in agendamento.produtos.filter(pagamento_status="reservado"):
        item.desfazer_reserva()

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


# ============================================
# 💳 STRIPE CHECKOUT & PAYMENT INTEGRATION
# ============================================

@require_http_methods(["GET", "POST"])
def stripe_checkout_agendamento_api(request, pagamento_id):
	"""
	Create a Stripe Checkout Session for a single appointment payment.
	GET: Returns checkout URL
	"""
	from .stripe_helpers import create_checkout_session, StripeCheckoutError
	
	pagamento = get_object_or_404(Pagamento, pk=pagamento_id)
	
	if request.method == "GET":
		try:
			result = create_checkout_session(
				pagamento,
				payment_type="agendamento",
				request=request
			)
			
			return JsonResponse({
				"status": "sucesso",
				"session_id": result["session_id"],
				"checkout_url": result["checkout_url"],
				"public_key": settings.STRIPE_PUBLIC_KEY,
			})
		except StripeCheckoutError as e:
			return JsonResponse({"status": "erro", "message": str(e)}, status=400)
		except Exception as e:
			return JsonResponse({"status": "erro", "message": f"Erro ao criar checkout: {str(e)}"}, status=500)
	
	# POST: Update payment after checkout
	if pagamento.status == "pago":
		return JsonResponse({"status": "sucesso", "message": "Pagamento já foi processado"})
	
	return JsonResponse({"status": "info", "message": "Aguardando confirmação do Stripe"})


@require_http_methods(["GET", "POST"])
def stripe_checkout_plano_api(request, plano_id):
	"""
	Create a Stripe Checkout Session for a monthly subscription payment.
	GET: Returns checkout URL  
	"""
	from .stripe_helpers import create_checkout_session, StripeCheckoutError
	
	plano = get_object_or_404(PlanoMensal, pk=plano_id)
	
	if request.method == "GET":
		try:
			result = create_checkout_session(
				plano,
				payment_type="plano",
				request=request
			)
			
			return JsonResponse({
				"status": "sucesso",
				"session_id": result["session_id"],
				"checkout_url": result["checkout_url"],
				"public_key": settings.STRIPE_PUBLIC_KEY,
			})
		except StripeCheckoutError as e:
			return JsonResponse({"status": "erro", "message": str(e)}, status=400)
		except Exception as e:
			return JsonResponse({"status": "erro", "message": f"Erro ao criar checkout: {str(e)}"}, status=500)
	
	# POST: Update payment after checkout
	if plano.pagamento_status == "pago":
		return JsonResponse({"status": "sucesso", "message": "Pagamento já foi processado"})
	
	return JsonResponse({"status": "info", "message": "Aguardando confirmação do Stripe"})


@require_http_methods(["POST"])
def stripe_webhook(request):
	"""
	Handle Stripe webhook events.
	Events:
	- checkout.session.completed: Payment successful
	- payment_intent.payment_failed: Payment failed
	"""
	import stripe
	from .stripe_helpers import (
		handle_checkout_session_completed,
		handle_payment_intent_failed,
	)
	
	payload = request.body
	sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
	
	try:
		event = stripe.Webhook.construct_event(
			payload,
			sig_header,
			settings.STRIPE_WEBHOOK_SECRET
		)
	except ValueError:
		return HttpResponse(status=400)
	except stripe.error.SignatureVerificationError:
		return HttpResponse(status=400)
	
	# Handle events
	if event['type'] == 'checkout.session.completed':
		session_id = event['data']['object']['id']
		result = handle_checkout_session_completed(session_id)
		if not result.get('success'):
			return JsonResponse(result, status=400)
	
	elif event['type'] == 'payment_intent.payment_failed':
		payment_intent_id = event['data']['object']['id']
		result = handle_payment_intent_failed(payment_intent_id)
		if not result.get('success'):
			return JsonResponse(result, status=400)
	
	return HttpResponse(status=200)


@require_http_methods(["GET"])
def stripe_checkout_success(request):
	"""
	Redirect page after successful Stripe checkout.
	Syncs payment status with Stripe and confirms locally.
	"""
	from .stripe_helpers import retrieve_checkout_session, sync_payment_with_stripe
	from core.models import StripeTransaction
	
	session_id = request.GET.get('session_id')
	if not session_id:
		messages.warning(request, "Sessão de checkout não encontrada.")
		return redirect('home')
	
	# Retrieve session
	session = retrieve_checkout_session(session_id)
	if not session:
		messages.error(request, "Sessão de checkout inválida.")
		return redirect('home')
	
	# Find StripeTransaction
	stripe_tx = StripeTransaction.objects.filter(stripe_session_id=session_id).first()
	if not stripe_tx:
		messages.error(request, "Transação não encontrada.")
		return redirect('home')
	
	# Sync payment if successful
	if session.payment_status == "paid":
		if stripe_tx.object_type == "agendamento":
			pagamento = Pagamento.objects.filter(agendamento_id=stripe_tx.object_id).first()
			if pagamento:
				sync_payment_with_stripe(pagamento, "agendamento")
				messages.success(request, "Pagamento confirmado com sucesso!")
				return redirect('payment_detail', token=pagamento.referencia_publica)
		
		elif stripe_tx.object_type == "plano":
			plano = PlanoMensal.objects.filter(id=stripe_tx.object_id).first()
			if plano:
				sync_payment_with_stripe(plano, "plano")
				messages.success(request, "Pagamento do plano confirmado!")
				return redirect('plan_payment_detail', token=plano.referencia_publica)
	
	messages.info(request, "Continuando processamento do pagamento...")
	return JsonResponse({"status": "processing", "session_id": session_id})


@require_http_methods(["GET"])
def stripe_checkout_cancel(request):
	"""
	Redirect page when customer cancels Stripe checkout.
	"""
	session_id = request.GET.get('session_id')
	item_type = request.GET.get('type', 'agendamento')
	
	messages.warning(request, "Você cancelou o checkout. Seu pagamento foi preservado.")
	
	if item_type == "agendamento":
		return redirect('home')
	elif item_type == "plano":
		return redirect('home')
	
	return redirect('home')


def service_worker_js(_request):
        content = """
const CACHE_NAME = 'easyschedule-pwa-v1';
const URLS = ['/', '/cliente/', '/static/css/theme.css'];

self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => cache.addAll(URLS)).then(() => self.skipWaiting())
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
    event.respondWith(
        caches.match(event.request).then((cached) => {
            if (cached) return cached;
            return fetch(event.request).then((response) => {
                const clone = response.clone();
                caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
                return response;
            }).catch(() => caches.match('/cliente/'));
        })
    );
});
"""
        return HttpResponse(content, content_type="application/javascript")

