from .models import AuditLog


def log_audit_event(
    *,
    empresa,
    acao,
    request=None,
    entidade="",
    entidade_id="",
    detalhes=None,
    ator_usuario=None,
    ator_cliente=None,
):
    ip = None
    if request is not None:
        ip = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip() or request.META.get("REMOTE_ADDR")

    AuditLog.objects.create(
        empresa=empresa,
        ator_usuario=ator_usuario,
        ator_cliente=ator_cliente,
        acao=acao,
        entidade=entidade or "",
        entidade_id=str(entidade_id or ""),
        detalhes=detalhes or {},
        endereco_ip=ip or None,
    )
