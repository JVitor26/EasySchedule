from django.contrib import admin

from .models import StripeWebhookEvent


@admin.register(StripeWebhookEvent)
class StripeWebhookEventAdmin(admin.ModelAdmin):
	list_display = ("event_id", "event_type", "processing_status", "livemode", "criado_em")
	list_filter = ("processing_status", "event_type", "livemode")
	search_fields = ("event_id", "event_type")
