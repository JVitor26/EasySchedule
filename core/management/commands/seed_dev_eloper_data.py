from __future__ import annotations

import random
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from agendamentos.models import Agendamento, PlanoMensal
from empresas.models import Empresa
from pessoa.models import Pessoa
from profissionais.models import Profissional
from produtos.models import Produto, VendaProduto
from servicos.models import Servico


class Command(BaseCommand):
    help = "Cria uma massa de dados robusta para a empresa dev.eloper/JV."

    def add_arguments(self, parser):
        parser.add_argument(
            "--empresa",
            default="Dev.eloper/JV",
            help="Nome da empresa para receber a massa de dados.",
        )
        parser.add_argument(
            "--seed",
            type=int,
            default=20260410,
            help="Seed para geração determinística dos dados.",
        )

    def handle(self, *args, **options):
        empresa_nome = (options["empresa"] or "").strip()
        if not empresa_nome:
            raise CommandError("Informe um nome de empresa válido em --empresa.")

        random.seed(options["seed"])

        empresa = Empresa.objects.filter(nome__iexact=empresa_nome).first()
        if not empresa:
            raise CommandError(
                f"Empresa '{empresa_nome}' não encontrada. "
                "Crie a empresa antes de executar este comando."
            )

        self.stdout.write(f"Gerando massa para empresa {empresa.id} - {empresa.nome}")

        servicos = self._seed_servicos(empresa)
        profissionais = self._seed_profissionais(empresa)
        clientes = self._seed_clientes(empresa, total=96)
        produtos = self._seed_produtos(empresa)
        self._seed_vendas(empresa, clientes, produtos, total=180)
        self._seed_planos_mensais(empresa, clientes, profissionais, servicos, total=36)
        self._seed_agendamentos(empresa, clientes, profissionais, servicos, total=360)

        self.stdout.write(self.style.SUCCESS("Massa da dev.eloper/JV criada com sucesso."))
        self.stdout.write(
            "Resumo -> "
            f"Clientes: {Pessoa.objects.filter(empresa=empresa).count()} | "
            f"Profissionais: {Profissional.objects.filter(empresa=empresa).count()} | "
            f"Serviços: {Servico.objects.filter(empresa=empresa).count()} | "
            f"Produtos: {Produto.objects.filter(empresa=empresa).count()} | "
            f"Vendas: {VendaProduto.objects.filter(empresa=empresa).count()} | "
            f"Planos: {PlanoMensal.objects.filter(empresa=empresa).count()} | "
            f"Agendamentos: {Agendamento.objects.filter(empresa=empresa).count()}"
        )

    def _seed_servicos(self, empresa: Empresa):
        servicos_data = [
            ("Corte Feminino Premium", "Cabelo", 120, "129.90", "#ec4899"),
            ("Corte Masculino Degradê", "Barbearia", 45, "69.90", "#3b82f6"),
            ("Escova Modelada", "Cabelo", 60, "79.90", "#f59e0b"),
            ("Coloração Global", "Cabelo", 150, "249.90", "#8b5cf6"),
            ("Hidratação Profunda", "Tratamentos", 50, "89.90", "#22c55e"),
            ("Design de Sobrancelhas", "Estética", 35, "49.90", "#f97316"),
            ("Manicure Completa", "Unhas", 40, "39.90", "#ef4444"),
            ("Pedicure Spa", "Unhas", 50, "54.90", "#14b8a6"),
            ("Limpeza de Pele", "Estética", 75, "129.90", "#06b6d4"),
            ("Massagem Relaxante", "Bem-estar", 60, "149.90", "#6366f1"),
            ("Depilação Completa", "Estética", 80, "159.90", "#a855f7"),
            ("Pacote Noiva Express", "Pacotes", 180, "499.90", "#e11d48"),
        ]
        result = []
        for nome, categoria, tempo, preco, cor in servicos_data:
            servico, _ = Servico.objects.update_or_create(
                empresa=empresa,
                nome=nome,
                defaults={
                    "categoria": categoria,
                    "descricao": f"{nome} - atendimento premium da {empresa.nome}.",
                    "tempo": tempo,
                    "preco": Decimal(preco),
                    "cor": cor,
                    "ativo": True,
                },
            )
            result.append(servico)
        return result

    def _seed_profissionais(self, empresa: Empresa):
        profissionais_data = [
            ("Ana Martins", "Cabelereira Sênior"),
            ("Bruno Costa", "Barbeiro"),
            ("Carla Souza", "Esteticista"),
            ("Diego Lima", "Massoterapeuta"),
            ("Elaine Rocha", "Manicure"),
            ("Felipe Nunes", "Colorista"),
            ("Gabriela Alves", "Designer de sobrancelhas"),
            ("Henrique Melo", "Especialista em noivas"),
        ]
        result = []
        for idx, (nome, especialidade) in enumerate(profissionais_data, start=1):
            profissional, _ = Profissional.objects.update_or_create(
                empresa=empresa,
                nome=nome,
                defaults={
                    "especialidade": especialidade,
                    "telefone": f"1199000{idx:04d}",
                    "email": f"prof{idx}@developer.local",
                    "cpf": f"0000000{idx:04d}",
                    "ativo": True,
                    "acessos_modulos": [],
                },
            )
            result.append(profissional)
        return result

    def _seed_clientes(self, empresa: Empresa, total: int):
        first_names = [
            "Lucas", "Mariana", "Pedro", "Juliana", "Rafael", "Amanda", "Thiago", "Fernanda",
            "Mateus", "Camila", "André", "Bianca", "Guilherme", "Patrícia", "Leonardo", "Aline",
            "Vinicius", "Larissa", "Ricardo", "Natália", "Eduardo", "Bruna", "Daniel", "Tatiane",
        ]
        last_names = [
            "Silva", "Souza", "Oliveira", "Santos", "Lima", "Costa", "Pereira", "Almeida",
            "Ribeiro", "Carvalho", "Gomes", "Martins", "Araújo", "Moura", "Dias", "Ferreira",
        ]
        bairros = [
            "Centro", "Jardins", "Vila Nova", "Zona Sul", "Boa Vista", "Parque das Flores",
            "Recanto Verde", "Alto da Serra",
        ]

        result = []
        for i in range(1, total + 1):
            nome = f"{random.choice(first_names)} {random.choice(last_names)}"
            cliente, _ = Pessoa.objects.update_or_create(
                empresa=empresa,
                email=f"cliente{i:03d}@developer.cliente",
                defaults={
                    "nome": nome,
                    "telefone": f"1198{i:07d}",
                    "documento": f"{10000000000 + i}",
                    "data_nascimento": date(1980 + (i % 25), (i % 12) + 1, (i % 27) + 1),
                    "endereco": f"Rua {nome.split()[0]}, {i} - {random.choice(bairros)}",
                    "observacoes": "Cliente importado para cenário de demonstração.",
                },
            )
            result.append(cliente)
        return result

    def _seed_produtos(self, empresa: Empresa):
        produtos_data = [
            ("Shampoo Reconstrutor", "Cabelo", "79.90", "38.00", 120),
            ("Condicionador Nutritivo", "Cabelo", "74.90", "34.00", 100),
            ("Máscara Hidratante", "Cabelo", "89.90", "45.00", 95),
            ("Óleo Capilar Premium", "Cabelo", "99.90", "52.00", 80),
            ("Pomada Modeladora", "Barbearia", "49.90", "21.00", 140),
            ("Balm Pós-Barba", "Barbearia", "39.90", "17.00", 110),
            ("Sérum Facial", "Skincare", "119.90", "63.00", 70),
            ("Protetor Solar Toque Seco", "Skincare", "69.90", "31.00", 130),
            ("Esfoliante Corporal", "Bem-estar", "59.90", "26.00", 90),
            ("Creme para Mãos", "Bem-estar", "34.90", "15.00", 160),
            ("Esmalte Gel Ruby", "Unhas", "24.90", "9.00", 200),
            ("Kit Spa dos Pés", "Unhas", "44.90", "19.00", 120),
            ("Leave-in Proteção Térmica", "Cabelo", "64.90", "29.00", 110),
            ("Ampola de Brilho", "Cabelo", "29.90", "12.00", 220),
            ("Kit Noiva Glow", "Pacotes", "189.90", "97.00", 40),
        ]
        result = []
        for idx, (nome, categoria, venda, compra, estoque) in enumerate(produtos_data, start=1):
            produto, _ = Produto.objects.update_or_create(
                empresa=empresa,
                nome=nome,
                defaults={
                    "categoria": categoria,
                    "descricao": f"{nome} da linha exclusiva da {empresa.nome}.",
                    "especificacoes": "Produto profissional para uso diário.",
                    "preco": Decimal(venda),
                    "valor_compra": Decimal(compra),
                    "custo": Decimal(compra),
                    "valor_venda": Decimal(venda),
                    "estoque": estoque,
                    "estoque_reservado": random.randint(0, max(1, estoque // 20)),
                    "ativo": True,
                    "destaque_publico": True,
                },
            )
            if not produto.foto:
                svg = self._build_product_svg(nome, idx)
                produto.foto.save(
                    f"developer_produto_{idx:02d}.svg",
                    ContentFile(svg.encode("utf-8")),
                    save=True,
                )
            result.append(produto)
        return result

    def _seed_vendas(self, empresa: Empresa, clientes, produtos, total: int):
        hoje = timezone.localdate()
        for idx in range(1, total + 1):
            produto = random.choice(produtos)
            cliente = random.choice(clientes)
            data_venda = hoje - timedelta(days=random.randint(0, 220))
            pago = random.random() < 0.82
            entrega_offset = random.randint(-5, 20)
            venda_ref = f"V{idx:04d}"

            VendaProduto.objects.update_or_create(
                empresa=empresa,
                produto=produto,
                cliente=cliente,
                data_venda=data_venda,
                observacoes=f"Venda seed {venda_ref}",
                defaults={
                    "valor_venda": produto.valor_venda,
                    "data_pagamento": data_venda + timedelta(days=random.randint(0, 6)) if pago else None,
                    "data_entrega": data_venda + timedelta(days=entrega_offset),
                },
            )

    def _seed_planos_mensais(self, empresa: Empresa, clientes, profissionais, servicos, total: int):
        today = timezone.localdate()
        month_base = date(today.year, today.month, 1)
        metodos = ["pix", "cartao", ""]
        status_choices = ["pendente", "ativo", "cancelado"]
        pagamento_choices = ["pendente", "pago", "cancelado", "expirado"]

        for idx in range(1, total + 1):
            cliente = clientes[idx % len(clientes)]
            servico = servicos[idx % len(servicos)]
            profissional = profissionais[idx % len(profissionais)]
            mes_referencia = self._add_months(month_base, idx % 5)
            dia_semana = idx % 7
            hora = time(hour=8 + (idx % 10), minute=0 if idx % 2 == 0 else 30)
            valor = Decimal(servico.preco) * Decimal("4")

            status = random.choice(status_choices)
            pagamento_status = random.choice(pagamento_choices)
            if status == "ativo" and pagamento_status == "pendente":
                pagamento_status = "pago"

            pago_em = None
            if pagamento_status == "pago":
                pago_em = timezone.make_aware(
                    datetime.combine(mes_referencia + timedelta(days=random.randint(0, 12)), time(12, 0))
                )

            PlanoMensal.objects.update_or_create(
                empresa=empresa,
                cliente=cliente,
                servico=servico,
                profissional=profissional,
                mes_referencia=mes_referencia,
                hora=hora,
                defaults={
                    "dia_semana": dia_semana,
                    "observacoes": f"Plano mensal seed PM{idx:03d}",
                    "status": status,
                    "pagamento_status": pagamento_status,
                    "metodo_pagamento": random.choice(metodos),
                    "valor_mensal": valor,
                    "quantidade_encontros": random.randint(4, 8),
                    "detalhes_pagamento": "Cobrança recorrente de demonstração.",
                    "pago_em": pago_em,
                },
            )

    def _seed_agendamentos(self, empresa: Empresa, clientes, profissionais, servicos, total: int):
        hoje = timezone.localdate()
        status_choices = ["pendente", "confirmado", "cancelado", "finalizado", "no_show"]
        metodo_choices = ["pix", "cartao", "dinheiro", "transferencia", ""]
        pagamento_choices = ["pendente", "pago", "cancelado"]
        horarios = [time(h, m) for h in range(8, 20) for m in (0, 30)]

        existentes = set(
            Agendamento.objects.filter(empresa=empresa).values_list(
                "cliente_id", "servico_id", "profissional_id", "data", "hora"
            )
        )
        novos = []
        tentativas = 0
        alvo = total

        while len(novos) < alvo and tentativas < alvo * 8:
            tentativas += 1
            cliente = random.choice(clientes)
            servico = random.choice(servicos)
            profissional = random.choice(profissionais)
            data_agendamento = hoje + timedelta(days=random.randint(-120, 140))
            hora = random.choice(horarios)
            chave = (cliente.id, servico.id, profissional.id, data_agendamento, hora)
            if chave in existentes:
                continue

            status = random.choice(status_choices)
            pagamento_status = random.choice(pagamento_choices)
            metodo = random.choice(metodo_choices)

            if status in {"finalizado", "no_show"} and data_agendamento > hoje:
                data_agendamento = hoje - timedelta(days=random.randint(1, 80))
            if status in {"pendente", "confirmado"} and data_agendamento < hoje:
                data_agendamento = hoje + timedelta(days=random.randint(1, 90))
            if pagamento_status == "pago" and not metodo:
                metodo = random.choice(["pix", "cartao", "dinheiro"])
            if status == "cancelado":
                pagamento_status = "cancelado"

            novos.append(
                Agendamento(
                    empresa=empresa,
                    cliente=cliente,
                    servico=servico,
                    profissional=profissional,
                    data=data_agendamento,
                    hora=hora,
                    observacoes="Agendamento seed dev.eloper/JV",
                    status=status,
                    metodo_pagamento=metodo,
                    pagamento_status=pagamento_status,
                )
            )
            existentes.add(chave)

        if novos:
            Agendamento.objects.bulk_create(novos, batch_size=200)

    def _build_product_svg(self, nome: str, idx: int) -> str:
        palette = ["#2563eb", "#22c55e", "#f59e0b", "#e11d48", "#8b5cf6", "#06b6d4"]
        color = palette[idx % len(palette)]
        safe_name = nome.replace("&", "e")
        return (
            "<svg xmlns='http://www.w3.org/2000/svg' width='720' height='720'>"
            f"<rect width='100%' height='100%' fill='{color}'/>"
            "<rect x='36' y='36' width='648' height='648' fill='white' opacity='0.14'/>"
            f"<text x='50%' y='50%' dominant-baseline='middle' text-anchor='middle' "
            "font-size='42' fill='white' font-family='Arial'>"
            f"{safe_name}</text>"
            "</svg>"
        )

    def _add_months(self, month_start: date, months_to_add: int) -> date:
        month_index = (month_start.month - 1) + months_to_add
        year = month_start.year + month_index // 12
        month = (month_index % 12) + 1
        return date(year, month, 1)
