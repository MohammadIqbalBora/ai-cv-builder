"""Idempotent fulfilment of verified Stripe application-pack payments."""
from django.contrib.auth import get_user_model
from django.db import transaction
from .models import ApplicationPack


def fulfil_application_pack(session):
    if (session.get("mode") != "payment" or session.get("payment_status") != "paid"
            or session.get("currency") != "gbp" or session.get("amount_total") != 199
            or session.get("metadata", {}).get("purchase") != "application_pack"):
        return False
    user_id = session.get("metadata", {}).get("user_id")
    with transaction.atomic():
        user = get_user_model().objects.select_for_update().filter(pk=user_id).first()
        if not user:
            return False
        ApplicationPack.objects.get_or_create(
            checkout_session_id=session["id"], defaults={"user": user}
        )
    return True
