# 🔐 Credenciais de Admin - EasySchedule

## Login Local
- **URL**: http://localhost:8000/admin/
- **Username**: `admin`
- **Senha**: definida localmente (nao versionada)
- **Email**: admin@easyschedule.com

---

## 📸 Solução Permanente para Perda de Imagens em Deploy

Você estava perdendo imagens após deploy porque o Render usa **disco efêmero** (apagado a cada redeploy) por padrão.

### ✅ O que foi configurado:

1. **Detecção Automática de Disco Persistente** (`settings.py` linhas 201-232)
   - O Django procura por disco persistente em ordem:
     - `MEDIA_ROOT` (variável de ambiente explícita)
     - `RENDER_MEDIA_ROOT` (para Render)
     - `RENDER_DISK_PATH` (disco montado no Render)
     - `/var/data/media` (padrão do Render)
     - Fallback local: `./media/`

2. **Validação no Build** (`build.sh` linhas 24-28)
   - Se no **Render** e disco persistente não encontrado → **FALHA EXPLÍCITA**
   - Isso evita fazer deploy sem saber que vai perder dados

3. **Flag de Verificação** (`settings.py` linha 173)
   - `MEDIA_PERSISTENCE_REQUIRED_ON_RENDER=true` força erro se disco não estiver disponível

### 🚀 Para Deploy no Render:

**1. Configure disco persistente na plataforma Render:**
   - Acesse seu serviço no Render Dashboard
   - Disk → Add Persistent Disk
   - Mount path: `/var/data` (ou outro caminho)
   - Size: conforme necessário

**2. Ou configure variáveis de ambiente:**
   ```
   RENDER_DISK_PATH=/var/data
   MEDIA_ROOT=/var/data/media
   ```

**3. Deploy:**
   ```bash
   git push
   # Render verá que disco é requerido
   # Build falha automaticamente se não estiver disponível
   # Imagens nunca mais são perdidas!
   ```

### 📦 Backup de Imagens Antigas

Se você tinha imagens antes disso, elas podem estar em:
- `./media/` (local, não sincronizado)
- S3/CloudFlare (se estava usando)

Para migrar para disco persistente:
```bash
# Local → Render
# Comprimir media/
tar -czf media_backup.tar.gz media/

# Fazer upload via Render dashboard ou SFTP
# Ou usar: render-deploy com volumes compartilhados
```

---

## 🔒 Segurança

- **Stripe Keys (TEST)**: Configuradas em `.env` (não sincronizadas)
- **Admin Password**: Regenerada com 16 caracteres aleatórios
- **Django DEBUG**: False em produção (controlado por variável de ambiente)

---

## 📋 Próximas Ações Recomendadas

1. ✅ Testar login com `admin` e a senha definida localmente
2. ✅ Configurar disco persistente no Render (settings → Disks)
3. ✅ Fazer deploy e verificar se disco foi montado
4. ✅ Fazer upload de imagens de teste
5. ✅ Redeploy e confirmar que imagens persistiram

---

**Gerado em**: 2026-04-10 às 18:49 UTC
