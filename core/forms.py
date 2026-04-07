import re

from django import forms
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from agendamentos.availability import list_available_slots
from agendamentos.models import Agendamento, Pagamento, PlanoMensal
from agendamentos.plans import (
    WEEKDAY_CHOICES,
    list_monthly_available_slots,
    list_monthly_occurrence_dates,
    normalize_month_reference,
)
from empresas.business_profiles import get_business_profile
from pessoa.models import Pessoa
from profissionais.models import Profissional
from servicos.models import Servico


BOOKING_TYPE_CHOICES = [
    ("avulso", "Somente um dia"),
    ("pacote_mensal", "Pacote mensal"),
]


class PublicBookingForm(forms.Form):
    nome = forms.CharField(max_length=255)
    email = forms.EmailField(required=False)
    telefone = forms.CharField(max_length=20)
    documento = forms.CharField(max_length=20, required=False)
    data_nascimento = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    tipo_reserva = forms.ChoiceField(
        choices=BOOKING_TYPE_CHOICES,
        initial="avulso",
        widget=forms.RadioSelect,
        required=False,
    )
    servico = forms.ModelChoiceField(queryset=Servico.objects.none())
    profissional = forms.ModelChoiceField(queryset=Profissional.objects.none())
    data = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    mes_referencia = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    dia_semana = forms.ChoiceField(required=False, choices=[("", "Selecione")] + list(WEEKDAY_CHOICES))
    hora = forms.ChoiceField(choices=(), required=True)
    observacoes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    def __init__(self, *args, empresa=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.empresa = empresa
        profile = get_business_profile(getattr(empresa, "tipo", None))

        self.fields["nome"].label = profile["client_name_label"]
        self.fields["nome"].widget.attrs["placeholder"] = profile["client_name_placeholder"]
        self.fields["email"].label = "Email (opcional)"
        self.fields["email"].widget.attrs["placeholder"] = "cliente@exemplo.com"
        self.fields["telefone"].label = "Whatsapp"
        self.fields["telefone"].widget.attrs["placeholder"] = "(65) 99999-9999"
        self.fields["documento"].label = "CPF (opcional)"
        self.fields["documento"].widget.attrs["placeholder"] = "Somente numeros"
        self.fields["data_nascimento"].label = "Data de nascimento (opcional)"
        self.fields["tipo_reserva"].label = "Como deseja contratar"
        self.fields["servico"].label = profile["service_term_singular"]
        self.fields["profissional"].label = profile["professional_term_singular"]
        self.fields["data"].label = f"Data do {profile['appointment_term_singular'].lower()}"
        self.fields["mes_referencia"].label = "Mes desejado para o pacote"
        self.fields["dia_semana"].label = "Dia fixo da semana"
        self.fields["hora"].label = "Horario disponivel"
        self.fields["observacoes"].label = profile["appointment_notes_label"]
        self.fields["observacoes"].widget.attrs["placeholder"] = profile["appointment_notes_placeholder"]

        if empresa is not None:
            self.fields["servico"].queryset = Servico.objects.filter(
                empresa=empresa,
                ativo=True,
            ).order_by("nome")
            self.fields["profissional"].queryset = Profissional.objects.filter(
                empresa=empresa,
                ativo=True,
            ).order_by("nome")

        self._configure_hour_choices()

    def _get_bound_value(self, field_name):
        if self.is_bound:
            return self.data.get(self.add_prefix(field_name))
        return self.initial.get(field_name)

    def _get_booking_type(self):
        value = self._get_bound_value("tipo_reserva")
        return value if value in dict(BOOKING_TYPE_CHOICES) else "avulso"

    def _get_selected_service(self):
        value = self._get_bound_value("servico")
        if not value:
            return None
        return self.fields["servico"].queryset.filter(pk=value).first()

    def _get_selected_professional(self):
        value = self._get_bound_value("profissional")
        if not value:
            return None
        return self.fields["profissional"].queryset.filter(pk=value).first()

    def _get_selected_date(self):
        value = self._get_bound_value("data")
        if not value:
            return None
        try:
            return forms.DateField().clean(value)
        except ValidationError:
            return None

    def _get_selected_month_reference(self):
        value = self._get_bound_value("mes_referencia")
        if not value:
            return None
        try:
            return normalize_month_reference(forms.DateField().clean(value))
        except ValidationError:
            return None

    def _get_selected_weekday(self):
        value = self._get_bound_value("dia_semana")
        if value in ("", None):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _configure_hour_choices(self):
        selected_service = self._get_selected_service()
        selected_professional = self._get_selected_professional()
        selected_date = self._get_selected_date()
        selected_month = self._get_selected_month_reference()
        selected_weekday = self._get_selected_weekday()
        selected_hour = self._get_bound_value("hora")
        booking_type = self._get_booking_type()

        choices = [("", "Preencha os dados para consultar os horarios")]

        if booking_type == "pacote_mensal":
            if selected_service and selected_professional and selected_month and selected_weekday is not None:
                slots, _occurrence_dates = list_monthly_available_slots(
                    empresa=self.empresa,
                    profissional=selected_professional,
                    servico=selected_service,
                    month_reference=selected_month,
                    weekday=selected_weekday,
                )
                choices = [("", "Selecione um horario fixo")]
                choices.extend((slot.strftime("%H:%M"), slot.strftime("%H:%M")) for slot in slots)
                if not slots:
                    choices = [("", "Nenhum horario fixo disponivel no mes")]
        else:
            if selected_service and selected_professional and selected_date:
                slots = list_available_slots(
                    empresa=self.empresa,
                    profissional=selected_professional,
                    servico=selected_service,
                    data=selected_date,
                )
                choices = [("", "Selecione um horario")]
                choices.extend((slot.strftime("%H:%M"), slot.strftime("%H:%M")) for slot in slots)

                if not slots:
                    choices = [("", "Nenhum horario disponivel")]

        if selected_hour and all(value != selected_hour for value, _label in choices):
            choices.append((selected_hour, selected_hour))

        self.fields["hora"].choices = choices

    def clean_documento(self):
        return re.sub(r"\D", "", self.cleaned_data.get("documento", ""))

    def clean_telefone(self):
        return re.sub(r"\D", "", self.cleaned_data["telefone"])

    def clean_email(self):
        return self.cleaned_data.get("email", "").strip().lower()

    def clean_tipo_reserva(self):
        tipo_reserva = self.cleaned_data.get("tipo_reserva") or "avulso"
        if tipo_reserva not in dict(BOOKING_TYPE_CHOICES):
            return "avulso"
        return tipo_reserva

    def clean_data(self):
        data = self.cleaned_data.get("data")
        if self.cleaned_data.get("tipo_reserva") == "avulso":
            if not data:
                raise forms.ValidationError("Escolha uma data para o agendamento.")
            if data < timezone.localdate():
                raise forms.ValidationError("Escolha uma data de hoje em diante.")
        return data

    def clean_mes_referencia(self):
        mes_referencia = self.cleaned_data.get("mes_referencia")
        if self.cleaned_data.get("tipo_reserva") == "pacote_mensal":
            if not mes_referencia:
                raise forms.ValidationError("Escolha um mes para o pacote mensal.")

            normalized_month = normalize_month_reference(mes_referencia)
            if normalized_month < normalize_month_reference(timezone.localdate()):
                raise forms.ValidationError("Escolha o mes atual ou um mes futuro para o pacote.")
            return normalized_month

        return mes_referencia

    def clean_dia_semana(self):
        dia_semana = self.cleaned_data.get("dia_semana")
        if self.cleaned_data.get("tipo_reserva") == "pacote_mensal":
            if dia_semana in (None, ""):
                raise forms.ValidationError("Escolha o dia fixo da semana para o pacote.")
            return int(dia_semana)
        return dia_semana

    def clean_hora(self):
        value = self.cleaned_data["hora"]
        if not value:
            raise forms.ValidationError("Selecione um horario disponivel.")
        return value

    def clean(self):
        cleaned_data = super().clean()

        booking_type = cleaned_data.get("tipo_reserva")
        servico = cleaned_data.get("servico")
        profissional = cleaned_data.get("profissional")
        hora = cleaned_data.get("hora")

        if booking_type == "pacote_mensal":
            mes_referencia = cleaned_data.get("mes_referencia")
            dia_semana = cleaned_data.get("dia_semana")

            if not all([servico, profissional, mes_referencia, hora]) or dia_semana in (None, ""):
                return cleaned_data

            available_slots, occurrence_dates = list_monthly_available_slots(
                empresa=self.empresa,
                profissional=profissional,
                servico=servico,
                month_reference=mes_referencia,
                weekday=dia_semana,
            )
            selected_slot = next(
                (slot for slot in available_slots if slot.strftime("%H:%M") == hora),
                None,
            )

            if not occurrence_dates:
                self.add_error(
                    "mes_referencia",
                    "Nao existem datas futuras disponiveis nesse mes para o dia escolhido.",
                )
                return cleaned_data

            if selected_slot is None:
                sugestoes = ", ".join(slot.strftime("%H:%M") for slot in available_slots[:6])
                if sugestoes:
                    self.add_error(
                        "hora",
                        "Esse horario fixo nao esta livre em todas as semanas do pacote. "
                        f"Horarios possiveis: {sugestoes}.",
                    )
                else:
                    self.add_error(
                        "hora",
                        "Nao restaram horarios fixos disponiveis para esse pacote mensal.",
                    )
            else:
                cleaned_data["hora_obj"] = selected_slot
                cleaned_data["plan_dates"] = list_monthly_occurrence_dates(
                    mes_referencia,
                    dia_semana,
                )

            return cleaned_data

        data = cleaned_data.get("data")
        if not all([servico, profissional, data, hora]):
            return cleaned_data

        available_slots = list_available_slots(
            empresa=self.empresa,
            profissional=profissional,
            servico=servico,
            data=data,
        )
        selected_slot = next(
            (slot for slot in available_slots if slot.strftime("%H:%M") == hora),
            None,
        )

        if selected_slot is None:
            sugestoes = ", ".join(slot.strftime("%H:%M") for slot in available_slots[:6])
            if sugestoes:
                self.add_error("hora", f"Esse horario acabou de ser ocupado. Horarios livres: {sugestoes}.")
            else:
                self.add_error("hora", "Nao restaram horarios disponiveis para essa data.")
        else:
            cleaned_data["hora_obj"] = selected_slot

        return cleaned_data

    def _get_or_create_cliente(self):
        email = self.cleaned_data["email"]
        documento = self.cleaned_data["documento"]
        telefone = self.cleaned_data["telefone"]

        cliente = Pessoa.objects.filter(empresa=self.empresa, email=email).first() if email else None
        if cliente is None and documento:
            cliente = Pessoa.objects.filter(empresa=self.empresa, documento=documento).first()
        if cliente is None and telefone:
            cliente = Pessoa.objects.filter(empresa=self.empresa, telefone=telefone).first()

        if cliente is None:
            cliente = Pessoa(empresa=self.empresa)

        cliente.nome = self.cleaned_data["nome"]
        cliente.telefone = telefone
        cliente.email = email if email or not cliente.pk else cliente.email
        cliente.documento = documento if documento or not cliente.pk else cliente.documento
        cliente.data_nascimento = (
            self.cleaned_data["data_nascimento"]
            if self.cleaned_data.get("data_nascimento") or not cliente.pk
            else cliente.data_nascimento
        )
        cliente.save()
        return cliente

    @transaction.atomic
    def save(self):
        cliente = self._get_or_create_cliente()
        booking_type = self.cleaned_data["tipo_reserva"]

        if booking_type == "pacote_mensal":
            plano = PlanoMensal(
                empresa=self.empresa,
                cliente=cliente,
                servico=self.cleaned_data["servico"],
                profissional=self.cleaned_data["profissional"],
                mes_referencia=self.cleaned_data["mes_referencia"],
                dia_semana=self.cleaned_data["dia_semana"],
                hora=self.cleaned_data["hora_obj"],
                observacoes=self.cleaned_data.get("observacoes", ""),
                status="pendente",
                pagamento_status="pendente",
            )
            try:
                plano.full_clean()
                plano.save()
                plano.sync_schedule()
            except ValidationError as exc:
                for field, messages in exc.message_dict.items():
                    form_field = field if field in self.fields else None
                    for message in messages:
                        self.add_error(form_field, message)
                raise

            return {
                "tipo_reserva": "pacote_mensal",
                "cliente": cliente,
                "agendamento": plano.first_occurrence,
                "pagamento": None,
                "plano": plano,
            }

        agendamento = Agendamento(
            empresa=self.empresa,
            cliente=cliente,
            servico=self.cleaned_data["servico"],
            profissional=self.cleaned_data["profissional"],
            data=self.cleaned_data["data"],
            hora=self.cleaned_data["hora_obj"],
            observacoes=self.cleaned_data.get("observacoes", ""),
            status="pendente",
        )
        try:
            agendamento.full_clean()
            agendamento.save()
        except ValidationError as exc:
            for field, messages in exc.message_dict.items():
                form_field = field if field in self.fields else None
                for message in messages:
                    self.add_error(form_field, message)
            raise

        pagamento = Pagamento.sync_for_agendamento(agendamento)
        return {
            "tipo_reserva": "avulso",
            "cliente": cliente,
            "agendamento": agendamento,
            "pagamento": pagamento,
            "plano": None,
        }


class PublicCheckoutForm(forms.Form):
    metodo = forms.ChoiceField(
        choices=Pagamento.METODO_CHOICES,
        widget=forms.RadioSelect,
        initial="pix",
    )
    nome_pagador = forms.CharField(max_length=100)
    ultimos_digitos = forms.CharField(max_length=4, required=False)
    aceitar_termos = forms.BooleanField(required=True)

    def __init__(self, *args, cobranca=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.cobranca = cobranca
        self.fields["metodo"].label = "Metodo de pagamento"
        self.fields["nome_pagador"].label = "Nome do pagador"
        self.fields["nome_pagador"].widget.attrs["placeholder"] = "Ex.: Maria Souza"
        self.fields["ultimos_digitos"].label = "Ultimos 4 digitos do cartao"
        self.fields["ultimos_digitos"].widget.attrs["placeholder"] = "1234"
        self.fields["aceitar_termos"].label = "Confirmo que desejo concluir o pagamento por este checkout."

        if cobranca is not None:
            if getattr(cobranca, "cliente_id", None):
                self.fields["nome_pagador"].initial = cobranca.cliente.nome

            metodo_atual = getattr(cobranca, "metodo", None) or getattr(cobranca, "metodo_pagamento", None)
            if metodo_atual:
                self.fields["metodo"].initial = metodo_atual

    def clean(self):
        cleaned_data = super().clean()
        metodo = cleaned_data.get("metodo")
        ultimos_digitos = cleaned_data.get("ultimos_digitos", "").strip()

        if metodo == "cartao":
            if not ultimos_digitos:
                self.add_error("ultimos_digitos", "Informe os ultimos 4 digitos do cartao.")
            elif not ultimos_digitos.isdigit() or len(ultimos_digitos) != 4:
                self.add_error("ultimos_digitos", "Use exatamente 4 numeros.")

        return cleaned_data

    @transaction.atomic
    def save(self):
        metodo = self.cleaned_data["metodo"]
        detalhes = f"Pagamento confirmado por {self.cleaned_data['nome_pagador']}"

        if metodo == "cartao":
            detalhes = f"{detalhes} no cartao final {self.cleaned_data['ultimos_digitos']}"

        self.cobranca.mark_as_paid(
            metodo=metodo,
            detalhes=detalhes,
        )
        return self.cobranca
