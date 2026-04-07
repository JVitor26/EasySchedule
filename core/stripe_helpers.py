"""
Stripe Integration Helpers - Centralized Payment Model

This module provides utilities for Stripe integration.
Currently supports centralized model (all charges go to platform account).
Ready for migration to Stripe Connect (each company has own account).

API Docs: https://docs.stripe.com/api
Latest Version: 2026-03-25.dahlia
"""

import stripe
import json
from decimal import Decimal
from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from django.http import JsonResponse

from .models import StripeTransaction
from agendamentos.models import Pagamento, PlanoMensal


# Configure Stripe with API key and version
stripe.api_key = settings.STRIPE_SECRET_KEY
stripe.api_version = settings.STRIPE_API_VERSION


class StripeCheckoutError(Exception):
	"""Raised when Stripe Checkout creation fails"""
	pass


def create_checkout_session(
	payment_obj,
	payment_type: str = "agendamento",
	return_url: str = None,
	request=None,
) -> str:
	"""
	Create a Stripe Checkout Session for a payment or subscription.
	
	Args:
		payment_obj: Pagamento or PlanoMensal instance
		payment_type: "agendamento" or "plano"
		return_url: Full URL to return after checkout (post-payment)
		request: Django request object (to build URLs if return_url not provided)
	
	Returns:
		dict with 'session_id' and 'checkout_url'
		
	Raises:
		StripeCheckoutError: If session creation fails
	"""
	
	if payment_type == "agendamento":
		if not isinstance(payment_obj, Pagamento):
			raise ValueError("payment_obj must be Pagamento for agendamento type")
		session_type = "one-time"
		amount_cents = int(payment_obj.valor * 100)  # Stripe uses cents
		description = f"Agendamento #{payment_obj.agendamento.id} - {payment_obj.agendamento.servico.nome}"
		metadata = {
			"object_type": "agendamento",
			"object_id": payment_obj.agendamento.id,
			"pagamento_id": payment_obj.id,
			"empresa_id": payment_obj.empresa.id,
		}
		success_url = f"{return_url or _get_base_url(request)}/pagamento/{payment_obj.referencia_publica}/?session_id={{CHECKOUT_SESSION_ID}}"
		cancel_url = f"{return_url or _get_base_url(request)}/pagamento/{payment_obj.referencia_publica}/?canceled=true"
		
	elif payment_type == "plano":
		if not isinstance(payment_obj, PlanoMensal):
			raise ValueError("payment_obj must be PlanoMensal for plano type")
		session_type = "subscription"
		amount_cents = int(payment_obj.valor_mensal * 100)
		description = f"Plano Mensal - {payment_obj.servico.nome} ({payment_obj.quantidade_encontros}x/mês)"
		metadata = {
			"object_type": "plano",
			"object_id": payment_obj.id,
			"empresa_id": payment_obj.empresa.id,
		}
		success_url = f"{return_url or _get_base_url(request)}/plano/{payment_obj.referencia_publica}/?session_id={{CHECKOUT_SESSION_ID}}"
		cancel_url = f"{return_url or _get_base_url(request)}/plano/{payment_obj.referencia_publica}/?canceled=true"
	else:
		raise ValueError("payment_type must be 'agendamento' or 'plano'")

	try:
		session = stripe.checkout.Session.create(
			payment_method_types=["card", "boleto"],  # card (Visa/Mastercard), boleto (Brazil)
			mode="payment" if session_type == "one-time" else "subscription",
			line_items=[
				{
					"price_data": {
						"currency": settings.STRIPE_DEFAULT_CURRENCY or "brl",
						"product_data": {
							"name": description,
							"metadata": metadata,
						},
						"unit_amount": amount_cents,
					},
					"quantity": 1,
				}
			],
			customer_email=payment_obj.cliente.email or payment_obj.customer_email if hasattr(payment_obj, 'customer_email') else "",
			success_url=success_url,
			cancel_url=cancel_url,
			metadata=metadata,
		)
		
		# Store session ID in payment record
		payment_obj.stripe_session_id = session.id
		payment_obj.stripe_synced_at = timezone.now()
		payment_obj.save(update_fields=['stripe_session_id', 'stripe_synced_at'])
		
		# Create StripeTransaction record for tracking
		_create_stripe_transaction_from_session(payment_obj, session, payment_type)
		
		return {"session_id": session.id, "checkout_url": session.url}
		
	except stripe.error.CardError as e:
		raise StripeCheckoutError(f"Card error: {e.user_message}")
	except stripe.error.RateLimitError:
		raise StripeCheckoutError("Too many API requests. Please try again shortly.")
	except stripe.error.InvalidRequestError as e:
		raise StripeCheckoutError(f"Invalid request: {str(e)}")
	except stripe.error.AuthenticationError:
		raise StripeCheckoutError("Stripe API authentication failed")
	except stripe.error.APIConnectionError:
		raise StripeCheckoutError("Network error connecting to Stripe")
	except stripe.error.StripeError as e:
		raise StripeCheckoutError(f"Stripe error: {str(e)}")


def _create_stripe_transaction_from_session(payment_obj, session, payment_type: str):
	"""
	Create a StripeTransaction record from a Checkout Session.
	"""
	amount_total = Decimal(session.amount_total or 0) / 100  # Convert from cents to currency
	
	# Get customer email
	if payment_type == "agendamento":
		customer_email = payment_obj.cliente.email or ""
	elif payment_type == "plano":
		customer_email = payment_obj.cliente.email or ""
	else:
		customer_email = session.customer_email or ""
	
	# Get customer name
	if payment_type in ["agendamento", "plano"]:
		customer_name = payment_obj.cliente.nome or ""
	else:
		customer_name = ""
	
	StripeTransaction.objects.update_or_create(
		stripe_session_id=session.id,
		defaults={
			"empresa": payment_obj.empresa,
			"object_type": payment_type,
			"object_id": payment_obj.id if payment_type == "plano" else payment_obj.agendamento.id,
			"amount_total": amount_total,
			"currency": (session.currency or "brl").upper(),
			"status": "pending",
			"customer_email": customer_email,
			"customer_name": customer_name,
		}
	)


def retrieve_checkout_session(session_id: str):
	"""
	Retrieve Stripe Checkout Session details.
	
	Returns:
		Stripe Session object
	"""
	try:
		return stripe.checkout.Session.retrieve(session_id)
	except stripe.error.InvalidRequestError:
		return None


def sync_payment_with_stripe(payment_obj, payment_type: str = "agendamento"):
	"""
	Sync a payment status with Stripe based on session ID.
	If payment is successful in Stripe, mark it as paid locally.
	
	Returns:
		Updated payment object or None if session not found
	"""
	if not payment_obj.stripe_session_id:
		return None
	
	session = retrieve_checkout_session(payment_obj.stripe_session_id)
	if not session:
		return None
	
	# Update StripeTransaction record
	stripe_tx = StripeTransaction.objects.filter(
		stripe_session_id=session.id
	).first()
	
	if stripe_tx:
		if session.payment_status == "paid":
			stripe_tx.status = "succeeded"
			stripe_tx.synced_at = timezone.now()
			
			# Mark payment as paid if not already
			if payment_obj.status != "pago":
				payment_obj.mark_as_paid(metodo="cartao", detalhes=f"Stripe - {session.id[:20]}...")
			
		elif session.payment_status == "unpaid":
			stripe_tx.status = "pending"
		
		stripe_tx.save()
	
	return payment_obj


def handle_checkout_session_completed(session_id: str):
	"""
	Handle checkout.session.completed webhook event.
	Mark payment as successful.
	"""
	session = retrieve_checkout_session(session_id)
	if not session:
		return {"success": False, "error": "Session not found"}
	
	stripe_tx = StripeTransaction.objects.filter(stripe_session_id=session_id).first()
	if not stripe_tx:
		return {"success": False, "error": "Transaction not found"}
	
	# Determine payment object type
	if stripe_tx.object_type == "agendamento":
		payment_obj = Pagamento.objects.filter(
			agendamento_id=stripe_tx.object_id
		).first()
	elif stripe_tx.object_type == "plano":
		payment_obj = PlanoMensal.objects.filter(id=stripe_tx.object_id).first()
	else:
		return {"success": False, "error": "Unknown object type"}
	
	if not payment_obj:
		return {"success": False, "error": "Payment object not found"}
	
	# Update statuses
	stripe_tx.status = "succeeded"
	stripe_tx.webhook_received_at = timezone.now()
	stripe_tx.synced_at = timezone.now()
	stripe_tx.save()
	
	if payment_obj.status != "pago":
		payment_obj.mark_as_paid(
			metodo="cartao",
			detalhes=f"Stripe - {session_id[:20]}..."
		)
		payment_obj.stripe_synced_at = timezone.now()
		payment_obj.save()
	
	return {"success": True}


def handle_payment_intent_failed(payment_intent_id: str):
	"""
	Handle payment_intent.payment_failed webhook event.
	Mark transaction as failed.
	"""
	stripe_tx = StripeTransaction.objects.filter(
		stripe_payment_intent_id=payment_intent_id
	).first()
	
	if not stripe_tx:
		return {"success": False, "error": "Transaction not found"}
	
	stripe_tx.status = "failed"
	stripe_tx.webhook_received_at = timezone.now()
	stripe_tx.failure_reason = f"Payment intent {payment_intent_id} failed"
	stripe_tx.save()
	
	return {"success": True}


def _get_base_url(request=None) -> str:
	"""
	Get base URL for building return URLs.
	"""
	if request:
		return f"{request.scheme}://{request.get_host()}"
	return f"{settings.STRIPE_DOMAIN_URL}" if hasattr(settings, 'STRIPE_DOMAIN_URL') else "http://localhost:8000"
