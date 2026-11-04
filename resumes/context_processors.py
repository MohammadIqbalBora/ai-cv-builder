from .models import Subscription, FreeDownloadUsage


def document_access(request):
    """Use current subscription state, never a browser-supplied plan flag."""
    subscription = Subscription.objects.filter(user=request.user).first() if request.user.is_authenticated else None
    premium = bool(subscription and subscription.has_premium_access)
    remaining = 3
    if request.user.is_authenticated and not premium:
        usage = FreeDownloadUsage.objects.filter(user=request.user).first()
        remaining = max(0, 3 - usage.downloads) if usage else 3
    return {"watermarked_documents": request.user.is_authenticated and not premium, "free_downloads_remaining": remaining}
