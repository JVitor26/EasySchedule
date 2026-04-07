from django.contrib.auth import get_user_model
from empresas.models import Empresa

User = get_user_model()

# Criar ou obter usuário de teste
user, created = User.objects.get_or_create(
    email='teste@easyschedule.com',
    defaults={
        'username': 'teste_user',
        'first_name': 'Teste',
        'last_name': 'User'
    }
)

if created:
    user.set_password('123456')
    user.save()
    print(f"✓ Usuário criado: {user.email} | Senha: 123456")
else:
    user.set_password('123456')
    user.save()
    print(f"✓ Usuário atualizado: {user.email}")

# Listar empresas
empresas = Empresa.objects.all()
print(f"\n✓ Empresas no sistema: {empresas.count()}")
for emp in empresas[:3]:
    print(f"  - {emp.nome} (ID: {emp.id})")
