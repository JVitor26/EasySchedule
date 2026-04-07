import re
import unicodedata
from copy import deepcopy


DEFAULT_BUSINESS_TYPE = "outro"

BUSINESS_TYPE_ORDER = [
    "barbearia",
    "manicure",
    "salao_beleza",
    "estetica",
    "clinica",
    "tatuagem",
    "petshop",
    "outro",
]


BUSINESS_TYPE_ALIASES = {
    "barber_shop": "barbearia",
    "barber": "barbearia",
    "nail_designer": "manicure",
    "nail_studio": "manicure",
    "salao": "salao_beleza",
    "salao_de_beleza": "salao_beleza",
    "salao_beleza": "salao_beleza",
    "beauty_salon": "salao_beleza",
    "clinica_estetica": "estetica",
    "estudio_de_tatuagem": "tatuagem",
    "tattoo": "tatuagem",
    "studio": "outro",
}


BUSINESS_PROFILES = {
    "outro": {
        "key": "outro",
        "label": "Negocio de servicos",
        "company_name_label": "Nome da empresa",
        "company_name_placeholder": "Ex.: Studio Bela Vista",
        "owner_name_label": "Nome completo do responsavel",
        "document_label": "CPF ou CNPJ",
        "registration_title": "Crie sua operacao de agendamentos",
        "registration_subtitle": "Configure sua empresa e depois personalize a agenda do seu jeito.",
        "registration_highlight": "Vamos preparar formularios flexiveis para o seu tipo de atendimento.",
        "preview_points": [
            "Agenda organizada por profissional",
            "Formularios prontos para clientes, servicos e horarios",
            "Base inicial para adaptar o fluxo do seu negocio",
        ],
        "client_term_singular": "Cliente",
        "client_term_plural": "Clientes",
        "client_name_label": "Nome do cliente",
        "client_name_placeholder": "Ex.: Maria Silva",
        "client_notes_label": "Observacoes do cliente",
        "client_notes_placeholder": "Informacoes relevantes para o atendimento.",
        "professional_term_singular": "Profissional",
        "professional_term_plural": "Profissionais",
        "professional_name_label": "Nome do profissional",
        "professional_name_placeholder": "Ex.: Ana Souza",
        "specialty_label": "Especialidade",
        "specialty_placeholder": "Ex.: Atendimento geral",
        "service_term_singular": "Servico",
        "service_term_plural": "Servicos",
        "service_name_label": "Nome do servico",
        "service_name_placeholder": "Ex.: Atendimento completo",
        "service_category_label": "Categoria",
        "service_description_label": "Descricao do servico",
        "service_description_placeholder": "Descreva o que esta incluso no atendimento.",
        "service_categories": [
            ("atendimento", "Atendimento"),
            ("pacote", "Pacote"),
            ("retorno", "Retorno"),
            ("avulso", "Avulso"),
            ("outro", "Outro"),
        ],
        "appointment_term_singular": "Agendamento",
        "appointment_term_plural": "Agendamentos",
        "appointment_notes_label": "Observacoes do atendimento",
        "appointment_notes_placeholder": "Adicione detalhes importantes para a agenda.",
        "appointment_page_hint": "Organize o horario, o profissional e o servico do atendimento.",
    },
    "barbearia": {
        "key": "barbearia",
        "label": "Barbearia",
        "company_name_label": "Nome da barbearia",
        "company_name_placeholder": "Ex.: Barbearia Dom Corte",
        "registration_title": "Monte sua barbearia online",
        "registration_subtitle": "Cadastre a barbearia e prepare a agenda com barbeiros, cortes e combos.",
        "registration_highlight": "O sistema vai falar a linguagem de barbearia desde o primeiro cadastro.",
        "preview_points": [
            "Agenda por barbeiro e horario",
            "Categorias prontas para corte, barba e combo",
            "Formularios com exemplos do dia a dia da barbearia",
        ],
        "professional_term_singular": "Barbeiro",
        "professional_term_plural": "Barbeiros",
        "professional_name_label": "Nome do barbeiro",
        "professional_name_placeholder": "Ex.: Rafael Fade",
        "specialty_label": "Especialidade do barbeiro",
        "specialty_placeholder": "Ex.: Fade, barba, acabamento",
        "service_name_label": "Nome do servico",
        "service_name_placeholder": "Ex.: Corte degradê",
        "service_description_label": "Descricao do servico",
        "service_description_placeholder": "Ex.: corte, lavagem e finalizacao.",
        "service_categories": [
            ("corte", "Corte"),
            ("barba", "Barba"),
            ("acabamento", "Acabamento"),
            ("combo", "Combo"),
            ("tratamento", "Tratamento"),
        ],
        "appointment_notes_label": "Observacoes do atendimento",
        "appointment_notes_placeholder": "Ex.: cliente prefere acabamento na navalha.",
        "appointment_page_hint": "Organize os horarios do barbeiro e os servicos da barbearia.",
    },
    "manicure": {
        "key": "manicure",
        "label": "Manicure",
        "company_name_label": "Nome do studio",
        "company_name_placeholder": "Ex.: Studio das Unhas",
        "registration_title": "Monte seu studio de manicure",
        "registration_subtitle": "Cadastre a agenda do espaco com manicures, esmaltes e procedimentos.",
        "registration_highlight": "Os formularios vao refletir o fluxo de manicure e nail design.",
        "preview_points": [
            "Agenda por manicure e horario",
            "Categorias prontas para maos, pes e alongamento",
            "Campos com exemplos para esmaltação, gel e nail art",
        ],
        "professional_term_singular": "Manicure",
        "professional_term_plural": "Manicures",
        "professional_name_label": "Nome da manicure",
        "professional_name_placeholder": "Ex.: Juliana Nail Designer",
        "specialty_label": "Especialidade da manicure",
        "specialty_placeholder": "Ex.: alongamento, blindagem, nail art",
        "service_name_label": "Nome do procedimento",
        "service_name_placeholder": "Ex.: Manutencao de gel",
        "service_description_label": "Descricao do procedimento",
        "service_description_placeholder": "Ex.: cuticulagem, esmaltação e finalizacao.",
        "service_categories": [
            ("maos", "Maos"),
            ("pes", "Pes"),
            ("alongamento", "Alongamento"),
            ("esmaltacao", "Esmaltacao"),
            ("spa", "Spa dos pes"),
        ],
        "appointment_notes_label": "Observacoes da sessao",
        "appointment_notes_placeholder": "Ex.: prefere esmalte nude e formato almond.",
        "appointment_page_hint": "Organize a sessao da manicure com o procedimento e o tempo ideal.",
    },
    "salao_beleza": {
        "key": "salao_beleza",
        "label": "Salao de beleza",
        "company_name_label": "Nome do salao",
        "company_name_placeholder": "Ex.: Salao Bella Forma",
        "registration_title": "Monte o seu salao de beleza",
        "registration_subtitle": "Cadastre a operacao do salao com profissionais, servicos e agenda por horario.",
        "registration_highlight": "Tudo preparado para cabelo, maquiagem, estetica e atendimento recorrente.",
        "preview_points": [
            "Agenda por profissional e horario",
            "Categorias para cabelo, maquiagem e estetica",
            "Formularios mais alinhados ao fluxo do salao",
        ],
        "service_categories": [
            ("cabelo", "Cabelo"),
            ("maquiagem", "Maquiagem"),
            ("estetica", "Estetica"),
            ("tratamento", "Tratamento"),
            ("combo", "Combo"),
        ],
        "service_name_placeholder": "Ex.: Escova modelada",
        "specialty_placeholder": "Ex.: coloracao, penteado, maquiagem",
    },
    "estetica": {
        "key": "estetica",
        "label": "Clinica de estetica",
        "company_name_label": "Nome da clinica",
        "company_name_placeholder": "Ex.: Clinica Aura",
        "registration_title": "Estruture sua clinica de estetica",
        "registration_subtitle": "Prepare a agenda da clinica com procedimentos, sessoes e equipe especializada.",
        "registration_highlight": "O fluxo fica mais alinhado a procedimentos, retorno e recorrencia.",
        "preview_points": [
            "Agenda por profissional e procedimento",
            "Categorias para facial, corporal e sessao avulsa",
            "Campos com linguagem de clinica de estetica",
        ],
        "service_categories": [
            ("facial", "Facial"),
            ("corporal", "Corporal"),
            ("depilacao", "Depilacao"),
            ("laser", "Laser"),
            ("retorno", "Retorno"),
        ],
        "service_name_placeholder": "Ex.: Limpeza de pele profunda",
        "specialty_placeholder": "Ex.: facial, corporal, depilacao",
        "appointment_notes_placeholder": "Ex.: retorno em 15 dias / evitar exposicao solar.",
    },
    "clinica": {
        "key": "clinica",
        "label": "Clinica",
        "company_name_label": "Nome da clinica",
        "company_name_placeholder": "Ex.: Clinica Vida Leve",
        "registration_title": "Organize a agenda da sua clinica",
        "registration_subtitle": "Cadastre a equipe, os atendimentos e os servicos para operar com mais clareza.",
        "registration_highlight": "A base fica pronta para consultas, retornos e acompanhamento.",
        "preview_points": [
            "Agenda por profissional e consulta",
            "Categorias para consulta, retorno e procedimento",
            "Formularios com linguagem mais clinica",
        ],
        "service_categories": [
            ("consulta", "Consulta"),
            ("retorno", "Retorno"),
            ("avaliacao", "Avaliacao"),
            ("procedimento", "Procedimento"),
            ("exame", "Exame"),
        ],
        "service_name_placeholder": "Ex.: Consulta inicial",
        "appointment_notes_placeholder": "Ex.: levar exames anteriores.",
    },
    "tatuagem": {
        "key": "tatuagem",
        "label": "Estudio de tatuagem",
        "company_name_label": "Nome do estudio",
        "company_name_placeholder": "Ex.: Estudio Black Ink",
        "registration_title": "Monte seu estudio de tatuagem",
        "registration_subtitle": "Cadastre tatuadores, sessoes e tipos de trabalho com uma agenda mais alinhada.",
        "registration_highlight": "O formulario ja nasce com linguagem de sessao, arte e retorno.",
        "preview_points": [
            "Agenda por tatuador",
            "Categorias para flash, sessao e retoque",
            "Campos prontos para observacoes de arte e preparo",
        ],
        "professional_term_singular": "Tatuador",
        "professional_term_plural": "Tatuadores",
        "professional_name_label": "Nome do tatuador",
        "professional_name_placeholder": "Ex.: Lucas Old School",
        "specialty_label": "Estilo principal",
        "specialty_placeholder": "Ex.: blackwork, fine line, old school",
        "service_name_label": "Nome da sessao",
        "service_name_placeholder": "Ex.: Tatuagem media",
        "service_description_label": "Descricao da sessao",
        "service_description_placeholder": "Ex.: arte exclusiva com ate 12 cm.",
        "service_categories": [
            ("flash", "Flash"),
            ("autoral", "Autoral"),
            ("retoque", "Retoque"),
            ("consultoria", "Consultoria"),
            ("sessao", "Sessao"),
        ],
        "appointment_notes_label": "Observacoes da sessao",
        "appointment_notes_placeholder": "Ex.: jejum nao necessario / arte aprovada.",
        "appointment_page_hint": "Organize a sessao, o tatuador e o tipo de trabalho previsto.",
    },
    "petshop": {
        "key": "petshop",
        "label": "Pet shop",
        "company_name_label": "Nome do pet shop",
        "company_name_placeholder": "Ex.: Pet Shop Reino Animal",
        "registration_title": "Estruture a agenda do seu pet shop",
        "registration_subtitle": "Cadastre banhos, tosas e atendimentos com uma base pronta para o dia a dia.",
        "registration_highlight": "Os formularios ficam mais proximos do fluxo de banho, tosa e cuidado animal.",
        "preview_points": [
            "Agenda por profissional e horario",
            "Categorias para banho, tosa e pacotes",
            "Campos prontos para observacoes do atendimento",
        ],
        "client_term_singular": "Tutor",
        "client_term_plural": "Tutores",
        "client_name_label": "Nome do tutor",
        "client_name_placeholder": "Ex.: Carla Souza",
        "service_categories": [
            ("banho", "Banho"),
            ("tosa", "Tosa"),
            ("hidratacao", "Hidratacao"),
            ("pacote", "Pacote"),
            ("consulta", "Consulta"),
        ],
        "service_name_placeholder": "Ex.: Banho e tosa completa",
        "appointment_notes_placeholder": "Ex.: animal sensivel em secador.",
    },
}


def normalize_business_type(value):
    if not value:
        return DEFAULT_BUSINESS_TYPE

    normalized = unicodedata.normalize("NFKD", str(value))
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", normalized.lower()).strip("_")
    normalized = BUSINESS_TYPE_ALIASES.get(normalized, normalized)

    if normalized in BUSINESS_PROFILES:
        return normalized

    return DEFAULT_BUSINESS_TYPE


def get_business_profile(tipo=None):
    key = normalize_business_type(tipo)
    profile = deepcopy(BUSINESS_PROFILES[DEFAULT_BUSINESS_TYPE])
    profile.update(deepcopy(BUSINESS_PROFILES.get(key, {})))
    profile["key"] = key
    return profile


def get_business_type_choices():
    return [(key, BUSINESS_PROFILES[key]["label"]) for key in BUSINESS_TYPE_ORDER]


def get_registration_profiles_payload():
    payload = {}

    for key in BUSINESS_TYPE_ORDER:
        profile = get_business_profile(key)
        payload[key] = {
            "label": profile["label"],
            "registration_title": profile["registration_title"],
            "registration_subtitle": profile["registration_subtitle"],
            "registration_highlight": profile["registration_highlight"],
            "company_name_label": profile["company_name_label"],
            "company_name_placeholder": profile["company_name_placeholder"],
            "owner_name_label": profile["owner_name_label"],
            "document_label": profile["document_label"],
            "professional_term_plural": profile["professional_term_plural"],
            "service_term_plural": profile["service_term_plural"],
            "appointment_term_plural": profile["appointment_term_plural"],
            "preview_points": profile["preview_points"],
        }

    return payload
