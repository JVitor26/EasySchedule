from django import forms
from django.core.exceptions import ValidationError

from empresas.business_profiles import get_business_profile
from pessoa.models import Pessoa
from profissionais.models import Profissional
from servicos.models import Servico

from .models import Agendamento, PlanoMensal
from .plans import WEEKDAY_CHOICES


class AgendamentoForm(forms.ModelForm):
    def __init__(self, *args, empresa=None, **kwargs):
        super().__init__(*args, **kwargs)
        profile = get_business_profile(getattr(empresa, "tipo", None))

        self.fields["cliente"].queryset = Pessoa.objects.none()
        self.fields["servico"].queryset = Servico.objects.none()
        self.fields["profissional"].queryset = Profissional.objects.none()

        self.fields["cliente"].label = profile["client_term_singular"]
        self.fields["servico"].label = profile["service_term_singular"]
        self.fields["profissional"].label = profile["professional_term_singular"]
        self.fields["data"].label = f"Data do {profile['appointment_term_singular'].lower()}"
        self.fields["hora"].label = "Horario"
        self.fields["observacoes"].label = profile["appointment_notes_label"]
        self.fields["observacoes"].widget.attrs["placeholder"] = profile["appointment_notes_placeholder"]
        self.fields["status"].label = f"Status do {profile['appointment_term_singular'].lower()}"

        if empresa is not None:
            self.fields["cliente"].queryset = Pessoa.objects.filter(empresa=empresa).order_by("nome")
            self.fields["servico"].queryset = Servico.objects.filter(empresa=empresa).order_by("nome")
            self.fields["profissional"].queryset = Profissional.objects.filter(
                empresa=empresa,
                ativo=True,
            ).order_by("nome")

    class Meta:
        model = Agendamento
        fields = [
            "cliente",
            "servico",
            "profissional",
            "data",
            "hora",
            "observacoes",
            "status",
        ]
        widgets = {
            "data": forms.DateInput(attrs={"type": "date"}),
            "hora": forms.TimeInput(attrs={"type": "time"}),
            "observacoes": forms.Textarea(attrs={"rows": 3}),
        }

    def clean(self):
        cleaned_data = super().clean()
        try:
            self.instance.clean()
        except ValidationError as exc:
            for field, messages in exc.message_dict.items():
                for message in messages:
                    self.add_error(field if field in self.fields else None, message)
        return cleaned_data


class PlanoMensalForm(forms.ModelForm):
    registrar_pagamento_agora = forms.BooleanField(required=False)
    metodo_pagamento_inicial = forms.ChoiceField(
        required=False,
        choices=[("", "Selecione")] + list(PlanoMensal.METODO_PAGAMENTO_CHOICES),
    )

    def __init__(self, *args, empresa=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.empresa = empresa
        profile = get_business_profile(getattr(empresa, "tipo", None))

        self.fields["cliente"].queryset = Pessoa.objects.none()
        self.fields["servico"].queryset = Servico.objects.none()
        self.fields["profissional"].queryset = Profissional.objects.none()

        self.fields["cliente"].label = profile["client_term_singular"]
        self.fields["servico"].label = profile["service_term_singular"]
        self.fields["profissional"].label = profile["professional_term_singular"]
        self.fields["mes_referencia"].label = "Mes de referencia do pacote"
        self.fields["dia_semana"].label = "Dia fixo da semana"
        self.fields["hora"].label = "Horario fixo"
        self.fields["observacoes"].label = profile["appointment_notes_label"]
        self.fields["observacoes"].widget.attrs["placeholder"] = (
            "Observacoes que devem valer para todos os encontros do pacote."
        )
        self.fields["registrar_pagamento_agora"].label = (
            "Registrar o pagamento do pacote agora e marcar o mes inteiro como pago."
        )
        self.fields["metodo_pagamento_inicial"].label = "Metodo do pagamento inicial"

        if self.instance.pk:
            self.fields["metodo_pagamento_inicial"].initial = self.instance.metodo_pagamento

        if empresa is not None:
            self.fields["cliente"].queryset = Pessoa.objects.filter(empresa=empresa).order_by("nome")
            self.fields["servico"].queryset = Servico.objects.filter(empresa=empresa, ativo=True).order_by("nome")
            self.fields["profissional"].queryset = Profissional.objects.filter(
                empresa=empresa,
                ativo=True,
            ).order_by("nome")

    class Meta:
        model = PlanoMensal
        fields = [
            "cliente",
            "servico",
            "profissional",
            "mes_referencia",
            "dia_semana",
            "hora",
            "observacoes",
        ]
        widgets = {
            "mes_referencia": forms.DateInput(attrs={"type": "date"}),
            "dia_semana": forms.Select(choices=WEEKDAY_CHOICES),
            "hora": forms.TimeInput(attrs={"type": "time"}),
            "observacoes": forms.Textarea(attrs={"rows": 3}),
        }

    def clean(self):
        cleaned_data = super().clean()

        registrar_pagamento = cleaned_data.get("registrar_pagamento_agora")
        metodo_pagamento = cleaned_data.get("metodo_pagamento_inicial")

        if registrar_pagamento and not metodo_pagamento:
            self.add_error(
                "metodo_pagamento_inicial",
                "Escolha o metodo para registrar o pagamento inicial do pacote.",
            )

        if not self.empresa:
            return cleaned_data

        self.instance.empresa = self.empresa
        for field_name in self.Meta.fields:
            if field_name in cleaned_data:
                setattr(self.instance, field_name, cleaned_data[field_name])

        try:
            self.instance.clean()
        except ValidationError as exc:
            for field, messages in exc.message_dict.items():
                for message in messages:
                    self.add_error(field if field in self.fields else None, message)

        return cleaned_data

    def save(self, commit=True):
        plano = super().save(commit=False)
        plano.empresa = self.empresa
        if not plano.status:
            plano.status = "pendente"
        if not plano.pagamento_status:
            plano.pagamento_status = "pendente"

        if commit:
            plano.save()
            plano.sync_schedule()

            if self.cleaned_data.get("registrar_pagamento_agora"):
                plano.mark_as_paid(
                    metodo=self.cleaned_data["metodo_pagamento_inicial"],
                    detalhes="Pagamento inicial registrado na area interna.",
                )

        return plano
