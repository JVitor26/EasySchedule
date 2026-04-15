import secrets
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.utils import timezone

from .models import ClienteFidelidade, FidelidadeMovimento, ProgramaFidelidade


def _to_points(value):
    if value <= 0:
        return 0
    return int(Decimal(value).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _generate_referral_code(empresa_id):
    while True:
        code = f"E{empresa_id}-{secrets.token_hex(3).upper()}"
        if not ClienteFidelidade.objects.filter(codigo_indicacao=code).exists():
            return code


def get_or_create_cliente_fidelidade(empresa, cliente):
    conta, _ = ClienteFidelidade.objects.get_or_create(
        empresa=empresa,
        cliente=cliente,
    )
    if not conta.codigo_indicacao:
        conta.codigo_indicacao = _generate_referral_code(empresa.id)
        conta.save(update_fields=["codigo_indicacao", "atualizado_em"])
    return conta


def apply_referral_code(empresa, cliente, codigo):
    conta = get_or_create_cliente_fidelidade(empresa, cliente)
    if conta.indicador_id:
        return False, "Este cliente ja esta vinculado a uma indicacao."

    codigo = (codigo or "").strip().upper()
    if not codigo:
        return False, "Informe um codigo de indicacao valido."

    origem = (
        ClienteFidelidade.objects
        .select_related("cliente")
        .filter(empresa=empresa, codigo_indicacao=codigo)
        .exclude(cliente=cliente)
        .first()
    )
    if origem is None:
        return False, "Codigo de indicacao nao encontrado para esta empresa."

    conta.indicador = origem.cliente
    conta.save(update_fields=["indicador", "atualizado_em"])
    return True, f"Indicacao registrada por {origem.cliente.nome}."


@transaction.atomic
def award_points_for_finalized_appointment(agendamento):
    programa = ProgramaFidelidade.objects.filter(empresa=agendamento.empresa, ativo=True).first()
    if programa is None:
        return

    cliente_conta = get_or_create_cliente_fidelidade(agendamento.empresa, agendamento.cliente)
    reference_id = f"agendamento:{agendamento.id}"

    already_scored = FidelidadeMovimento.objects.filter(
        empresa=agendamento.empresa,
        cliente_fidelidade=cliente_conta,
        origem="agendamento",
        referencia_id=reference_id,
    ).exists()
    if already_scored:
        return

    valor = Decimal(agendamento.servico.preco or 0)
    base_points = _to_points(valor * Decimal(programa.pontos_por_real))
    if base_points > 0:
        cliente_conta.pontos_totais += base_points
        cliente_conta.pontos_disponiveis += base_points
        cliente_conta.save(update_fields=["pontos_totais", "pontos_disponiveis", "atualizado_em"])
        FidelidadeMovimento.objects.create(
            empresa=agendamento.empresa,
            cliente_fidelidade=cliente_conta,
            origem="agendamento",
            descricao="Pontos por atendimento finalizado",
            pontos=base_points,
            referencia_id=reference_id,
        )

    if not cliente_conta.indicador_id:
        return

    first_finalized = not agendamento.__class__.objects.filter(
        empresa=agendamento.empresa,
        cliente=agendamento.cliente,
        status="finalizado",
    ).exclude(pk=agendamento.pk).exists()
    if not first_finalized:
        return

    if valor < Decimal(programa.ticket_minimo_indicacao or 0):
        return

    indicador_conta = get_or_create_cliente_fidelidade(agendamento.empresa, cliente_conta.indicador)
    referral_reference = f"indicacao:{agendamento.id}:{cliente_conta.id}"
    if FidelidadeMovimento.objects.filter(
        empresa=agendamento.empresa,
        cliente_fidelidade=indicador_conta,
        origem="indicacao",
        referencia_id=referral_reference,
    ).exists():
        return

    bonus_points = _to_points(
        Decimal(programa.pontos_bonus_indicacao)
        + (Decimal(base_points) * Decimal(programa.multiplicador_indicacao))
    )
    if bonus_points <= 0:
        return

    indicador_conta.pontos_totais += bonus_points
    indicador_conta.pontos_disponiveis += bonus_points
    indicador_conta.save(update_fields=["pontos_totais", "pontos_disponiveis", "atualizado_em"])

    FidelidadeMovimento.objects.create(
        empresa=agendamento.empresa,
        cliente_fidelidade=indicador_conta,
        origem="indicacao",
        descricao=f"Bonus por indicacao convertida ({agendamento.cliente.nome})",
        pontos=bonus_points,
        referencia_id=referral_reference,
    )


def nps_score_from_queryset(queryset):
    total = queryset.count()
    if total == 0:
        return 0

    promoters = queryset.filter(nota__gte=9).count()
    detractors = queryset.filter(nota__lte=6).count()
    return int(round(((promoters - detractors) / total) * 100))


def build_reengagement_candidates(empresa, days_without_return=35, limit=20):
    from agendamentos.models import Agendamento

    base = (
        Agendamento.objects
        .filter(empresa=empresa, status__in=["finalizado", "no_show"])
        .select_related("cliente")
        .order_by("cliente_id", "-data", "-hora")
    )

    last_by_client = {}
    for appointment in base:
        if appointment.cliente_id not in last_by_client:
            last_by_client[appointment.cliente_id] = appointment

    candidates = []
    today = timezone.localdate()
    for last in last_by_client.values():
        if (today - last.data).days < days_without_return:
            continue
        has_upcoming = Agendamento.objects.filter(
            empresa=empresa,
            cliente_id=last.cliente_id,
            data__gte=today,
            status__in=["pendente", "confirmado"],
        ).exists()
        if has_upcoming:
            continue

        candidates.append({
            "cliente_id": last.cliente_id,
            "cliente_nome": last.cliente.nome,
            "telefone": last.cliente.telefone,
            "dias_sem_retorno": (today - last.data).days,
            "ultima_data": last.data,
            "ultimo_servico": last.servico.nome,
        })

    candidates.sort(key=lambda item: item["dias_sem_retorno"], reverse=True)
    return candidates[:limit]

