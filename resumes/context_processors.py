from .models import Subscription


def document_access(request):
    """Use current subscription state, never a browser-supplied plan flag."""
    premium = request.user.is_authenticated and Subscription.objects.filter(
        user=request.user, is_active=True
    ).exists()
    return {"watermarked_documents": request.user.is_authenticated and not premium}
