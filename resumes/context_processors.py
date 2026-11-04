from .models import Subscription, FreeDownloadUsage, ApplicationPack


def document_access(request):
    """Use current subscription state, never a browser-supplied plan flag."""
    subscription = Subscription.objects.filter(user=request.user).first() if request.user.is_authenticated else None
    premium = bool(subscription and subscription.has_premium_access)
    remaining = 3
    if request.user.is_authenticated and not premium:
        usage = FreeDownloadUsage.objects.filter(user=request.user).first()
        remaining = max(0, 3 - usage.downloads) if usage else 3
    from django.db.models import Sum
    credits = ApplicationPack.objects.filter(user=request.user).aggregate(cv=Sum("cv_downloads"), letter=Sum("letter_downloads")) if request.user.is_authenticated else {}
    cv_credits, letter_credits = credits.get("cv") or 0, credits.get("letter") or 0
    route = request.resolver_match.url_name if request.resolver_match else ""
    relevant_credits = letter_credits if route == "create_cover_letter" else cv_credits
    return {"pack_cv_credits": cv_credits, "pack_letter_credits": letter_credits, "watermarked_documents": request.user.is_authenticated and not premium and not relevant_credits, "free_downloads_remaining": remaining}
