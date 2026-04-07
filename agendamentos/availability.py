from datetime import datetime, time, timedelta

from django.utils import timezone

AGENDA_START_TIME = time(8, 0)
AGENDA_END_TIME = time(20, 0)
AGENDA_SLOT_INTERVAL_MINUTES = 30
BLOCKING_STATUSES = {"pendente", "confirmado", "finalizado"}


def get_service_duration_minutes(servico):
    duration = getattr(servico, "tempo", 0) or 0
    return max(int(duration), AGENDA_SLOT_INTERVAL_MINUTES)


def round_up_to_next_slot(moment):
    minute = moment.minute
    remainder = minute % AGENDA_SLOT_INTERVAL_MINUTES

    if remainder:
        moment += timedelta(minutes=AGENDA_SLOT_INTERVAL_MINUTES - remainder)

    return moment.replace(second=0, microsecond=0)


def coerce_time_value(value):
    if isinstance(value, time):
        return value.replace(second=0, microsecond=0)

    if isinstance(value, str):
        for time_format in ("%H:%M", "%H:%M:%S"):
            try:
                return datetime.strptime(value, time_format).time()
            except ValueError:
                continue

    return None


def list_available_slots(
    empresa,
    profissional,
    servico,
    data,
    exclude_agendamento_id=None,
    exclude_agendamento_ids=None,
):
    from .models import Agendamento

    if not empresa or not profissional or not servico or not data:
        return []

    duration = get_service_duration_minutes(servico)
    day_start = datetime.combine(data, AGENDA_START_TIME)
    day_end = datetime.combine(data, AGENDA_END_TIME)
    latest_start = day_end - timedelta(minutes=duration)

    if latest_start < day_start:
        return []

    now = timezone.localtime(timezone.now())
    if data < timezone.localdate():
        return []

    first_slot = day_start
    if data == timezone.localdate():
        first_slot = max(first_slot, round_up_to_next_slot(now))

    queryset = Agendamento.objects.filter(
        empresa=empresa,
        profissional=profissional,
        data=data,
        status__in=BLOCKING_STATUSES,
    ).select_related("servico")

    excluded_ids = set(exclude_agendamento_ids or [])
    if exclude_agendamento_id:
        excluded_ids.add(exclude_agendamento_id)
    if excluded_ids:
        queryset = queryset.exclude(pk__in=excluded_ids)

    occupied_ranges = []
    for agendamento in queryset:
        start = datetime.combine(data, agendamento.hora)
        end = start + timedelta(minutes=get_service_duration_minutes(agendamento.servico))
        occupied_ranges.append((start, end))

    current = first_slot
    available_slots = []

    while current <= latest_start:
        candidate_end = current + timedelta(minutes=duration)
        overlaps = any(
            current < occupied_end and candidate_end > occupied_start
            for occupied_start, occupied_end in occupied_ranges
        )

        if not overlaps:
            available_slots.append(current.time().replace(second=0, microsecond=0))

        current += timedelta(minutes=AGENDA_SLOT_INTERVAL_MINUTES)

    return available_slots


def find_schedule_conflict(
    empresa,
    profissional,
    servico,
    data,
    hora,
    exclude_agendamento_id=None,
    exclude_agendamento_ids=None,
):
    from .models import Agendamento

    if not empresa or not profissional or not servico or not data or not hora:
        return None

    hora = coerce_time_value(hora)
    if hora is None:
        return None

    duration = get_service_duration_minutes(servico)
    candidate_start = datetime.combine(data, hora)
    candidate_end = candidate_start + timedelta(minutes=duration)

    queryset = Agendamento.objects.filter(
        empresa=empresa,
        profissional=profissional,
        data=data,
        status__in=BLOCKING_STATUSES,
    ).select_related("servico")

    excluded_ids = set(exclude_agendamento_ids or [])
    if exclude_agendamento_id:
        excluded_ids.add(exclude_agendamento_id)
    if excluded_ids:
        queryset = queryset.exclude(pk__in=excluded_ids)

    for agendamento in queryset:
        start = datetime.combine(data, agendamento.hora)
        end = start + timedelta(minutes=get_service_duration_minutes(agendamento.servico))
        if candidate_start < end and candidate_end > start:
            return agendamento

    return None
