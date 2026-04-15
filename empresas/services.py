import logging

from django.contrib.auth import get_user_model
from django.core.files.storage import default_storage
from django.db import transaction

from profissionais.models import Profissional
from produtos.models import Produto, VendaProduto
from relatorios.models import ExecucaoRelatorio


logger = logging.getLogger(__name__)


def _collect_account_file_refs(empresa):
    file_refs = []

    if empresa.logo and empresa.logo.name:
        file_refs.append((empresa.logo.storage, empresa.logo.name))

    for foto in Produto.objects.filter(empresa=empresa).exclude(foto="").values_list("foto", flat=True):
        if foto:
            file_refs.append((default_storage, foto))

    for arquivo in ExecucaoRelatorio.objects.filter(empresa=empresa).exclude(arquivo="").values_list("arquivo", flat=True):
        if arquivo:
            file_refs.append((default_storage, arquivo))

    return file_refs


def _delete_account_files(file_refs):
    seen = set()
    for storage, name in file_refs:
        key = (id(storage), name)
        if not name or key in seen:
            continue

        seen.add(key)
        try:
            if storage.exists(name):
                storage.delete(name)
        except Exception:
            logger.exception("Nao foi possivel remover o arquivo da conta: %s", name)


def delete_empresa_account(empresa):
    user_model = get_user_model()
    owner_user_id = empresa.usuario_id
    professional_user_ids = set(
        Profissional.objects.filter(empresa=empresa, usuario_id__isnull=False).values_list("usuario_id", flat=True)
    )
    other_company_owner_ids = set(
        empresa.__class__.objects.filter(usuario_id__in=professional_user_ids)
        .exclude(pk=empresa.pk)
        .values_list("usuario_id", flat=True)
    )
    user_ids = {owner_user_id, *(professional_user_ids - other_company_owner_ids)}
    user_ids = {user_id for user_id in user_ids if user_id}
    file_refs = _collect_account_file_refs(empresa)

    with transaction.atomic():
        # Vendas protegem produtos, entao removemos antes da cascata da empresa.
        VendaProduto.objects.filter(empresa=empresa).delete()
        empresa.delete()
        if user_ids:
            user_model.objects.filter(pk__in=user_ids).delete()

        transaction.on_commit(lambda: _delete_account_files(file_refs))

    return user_ids
