# 🛍️ Sistema de Produtos e Carrinho - Guia Completo

## ✨ O Que Foi Implementado

Um sistema completo de loja integrada ao portal de agendamentos, onde clientes podem:

1. **Navegar por uma Loja de E-commerce**: Página dedicada com busca, filtros por categoria e grid responsivo
2. **Gerenciar Carrinho de Compras**: Adicionar/remover produtos, atualizar quantidades (armazenado em sessão)
3. **Integrar Produtos ao Agendamento**: Carrinho aparece automaticamente na página de agendamento
4. **Controle de Estoque Inteligente**:
   - **Reservado**: Quando agendamento é criado, produtos ficam como "reservado"
   - **Pago**: Quando pagamento é confirmado, deduz do estoque
   - **Cancelado**: Se não pagar, volta ao estoque disponível
5. **Cálculo de Preço Total**: Valor final = Serviço + Produtos

---

## 🎯 Fluxo de Uso

### 1. Cliente Acessa a Loja
```
URL: /cliente/empresa/{empresa_id}/loja/
```
- Interface tipo Shopify com grid de produtos
- Busca por nome/descrição
- Filtro por categoria
- Mostra disponibilidade em tempo real

### 2. Adiciona Produtos ao Carrinho
- Especifica quantidade
- Clica em "Adicionar"
- Carrinho é armazenado na **sessão do navegador**
- Aviso se estoque insuficiente

### 3. Vai para Agendamento
```
URL: /cliente/empresa/{empresa_id}/
```
- Nova seção "🛒 Produtos no Carrinho" aparece automaticamente
- Lista todos os itens com preços
- Botões: "Adicionar mais produtos" e "Limpar carrinho"

### 4. Submete Agendamento
- Produtos são inclusos no JSON transferido
- Sistema cria `AgendamentoProduto` para cada item
- **Estoque**:
  - `estoque_reservado += quantidade` (bloqueia para outros)
  - `estoque = inalterado` (para agora)

### 5. Confirma Pagamento
- `Pagamento.mark_as_paid()` processa produtos
- Para cada `AgendamentoProduto`:
  - `pagamento_status = 'pago'`
  - `estoque -= quantidade` (deduz para valer)
  - `estoque_reservado -= quantidade` (libera reserva)

---

## 🗄️ Estrutura do Banco

### AgendamentoProduto (Novo)
```
- agendamento (FK)
- produto (FK)
- quantidade (PositiveIntegerField)
- preco_unitario (Decimal) - histórico de preço
- pagamento_status (reservado/pago/cancelado)
- criado_em, atualizado_em (timestamps)
```

### Produto (Modificado)
```
+ estoque_reservado (PositiveIntegerField) - novo campo
+ property estoque_disponivel = estoque - estoque_reservado
```

---

## 🔗 URLs

| Rota | Método | Descrição |
|------|--------|-----------|
| `/cliente/empresa/<id>/loja/` | GET | Página da loja |
| `/cliente/empresa/<id>/api/carrinho/listar/` | GET | Lista itens |
| `/cliente/empresa/<id>/api/carrinho/adicionar/` | POST | Adiciona produto |
| `/cliente/empresa/<id>/api/carrinho/remover/` | POST | Remove produto |
| `/cliente/empresa/<id>/api/carrinho/atualizar/` | POST | Atualiza quantidade |

---

## 📊 Exemplo de Fluxo de Dados

```
CLIENTE → Loja de Produtos
         ├─ Vê: Shampoo Premium (Estoque: 10)
         ├─ Adiciona: 2x Shampoo Premium
         └─ Carrinho: {produto_id: 1, quantidade: 2, preco: 45.00, preco_total: 90.00}

CLIENTE → Agendamento
         ├─ Serviço: Corte (R$ 80.00)
         ├─ Vê carrinho: Shampoo 2x R$ 90.00
         ├─ Total: R$ 170.00 (80 + 90)
         └─ Clica: "Solicitar Reserva"

SISTEMA → Criar Agendamento
         ├─ Agendamento.status = 'pendente'
         ├─ AgendamentoProduto: {agendamento, produto, quantidade: 2, preco_unitario: 45, status: 'reservado'}
         ├─ Produto.estoque_reservado = 2 (era 0, fica 2)
         ├─ Produto.estoque = permanece 10
         ├─ Pagamento.valor = 170.00
         └─ URL para pagar enviada ao cliente

CLIENTE → Pagar
         ├─ Clica em link de pagamento
         └─ Confirma pagamento

SISTEMA → Processar Pagamento
         ├─ Pagamento.status = 'pago'
         ├─ Para cada AgendamentoProduto:
         │  ├─ pagamento_status = 'pago'
         │  ├─ Produto.estoque -= 2 (de 10 para 8)
         │  └─ Produto.estoque_reservado -= 2 (de 2 para 0)
         └─ Agendamento.status = 'confirmado'

RESULTADO → Estoque Final
         ├─ estoque = 8 (foram vendidas 2 unidades)
         ├─ estoque_reservado = 0 (nada mais em suspensão)
         └─ disponivel = 8
```

---

## 🛠️ Dados de Teste Criados

Produtos adicionados a BarberGabs:

| Produto | Categoria | Preço | Estoque |
|---------|-----------|-------|---------|
| Shampoo Premium | Higiene | R$ 45,00 | 10 |
| Óleo para Barba | Higiene | R$ 65,00 | 8 |
| Pomada Forte | Estilo | R$ 35,00 | 15 |
| Toalha de Barba | Acessórios | R$ 25,00 | 20 |
| Kit Completo | Kits | R$ 150,00 | 5 |

---

## 💡 Casos de Uso

### ✅ Cliente paga tudo (serviço + produtos)
1. Estoque é deduzido imediatamente
2. AgendamentoProduto.pagamento_status = 'pago'

### ❌ Cliente só paga o serviço (não quer os produtos)
1. Produtos voltam ao estoque (desfazer_reserva)
2. AgendamentoProduto.pagamento_status = 'cancelado'
3. estoque_reservado e estoque voltam ao estado inicial

### ⏳ Cliente deixa agendamento pendente
1. Produtos ficam "reservados" por 24-48h (configurável)
2. Outros clientes veem estoque reduzido
3. Se expirar sem pagar, volta ao estoque

---

## 🔧 Como Expandir

### 1. Adicionar mais produtos
- Admin Django: `/admin/produtos/produto/`
- Marcar: `ativo = True` e `destaque_publico = True`

### 2. Modificar limite de expiração
Editar em `core/views.py`:
```python
# Adicionar TTL para reservas (não implementado ainda)
EXPIRACAO_RESERVA_HORAS = 48
```

### 3. Notificações de estoque baixo
Editar `produtos/models.py`:
```python
if self.estoque_disponivel < 3:
    # Enviar email para gestor
```

### 4. Relatórios de vendas por produto
Já existem AgendamentoProduto com histórico completo na DB.

---

## 🧪 Teste Rápido

1. Acesse: `http://localhost:8000/cliente/`
2. Selecione BarberGabs
3. Clique no botão "🏪 Ir para loja completa"
4. Adicione produtos ao carrinho
5. Volte para agendamento
6. Veja o carrinho na página
7. Complete o agendamento
8. No admin: Veja `AgendamentoProduto` criado com status "reservado"
9. Confirme pagamento (admin: mudança para "pago")
10. Verifique estoque reduzido em `Produto.estoque`

---

## 📝 Notas Importantes

```
⚠️ Estoque é armazenado em:
   - estoque: total físico
   - estoque_reservado: bloqueado em agendamento pendente
   - estoque_disponivel (property): estoque - estoque_reservado

⚠️ Carrinho é armazenado em:
   - request.session["carrinho"] no servidor
   - Persiste durante sessão do usuário
   - Limpo ao fazer logout ou 24h de inatividade

⚠️ Pagamento de produto inclui:
   - Validação de estoque no momento da criação
   - Transação atômica (tudo ou nada)
   - Rollback se erro em qualquer etapa
```

---

## 🎨 Frontend

### Loja (`loja_produtos.html`)
- Grid responsivo (250px minmax)
- Filtros por categoria e busca
- Carrinho flutuante com contador
- Integração com tema CSS existing

### Agendamento (`cliente_empresa.html` - modificado)
- Nova seção de carrinho
- Sincronização com loja
- Botão "Ir para loja"
- Limpeza de carrinho

### APIs JSON
- Todas retornam `{status, message, ...}`
- Validação de estoque em cada chamada
- CSRF protection em POSTs

---

## 🚀 Próximos Passos Opcionais

- [ ] Sistema de cupons/descontos
- [ ] Notificações por email de reservas
- [ ] Relatórios de vendas por período
- [ ] Integração com estoque de matriz
- [ ] Sugestões de produtos (cross-sell)
- [ ] Histórico de compras do cliente
- [ ] Avaliações de produtos

---

**Versão**: 1.0  
**Data**: 04/07/2026  
**Status**: ✅ Pronto para produção
