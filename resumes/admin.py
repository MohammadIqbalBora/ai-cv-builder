from django.contrib import admin
from .models import CV, Subscription

admin.site.site_header = "AI CV Builder Administration"
admin.site.site_title = "AI CV Builder Admin"
admin.site.index_title = "Project Admin Dashboard"


@admin.register(CV)
class CVAdmin(admin.ModelAdmin):
    list_display = (
        "full_name",
        "user",
        "job_title",
        "template",
        "created_at",
    )

    search_fields = (
        "full_name",
        "email",
        "job_title",
        "user__username",
    )

    list_filter = (
        "template",
        "created_at",
    )

    readonly_fields = ("created_at",)

    fieldsets = (
        ("User", {"fields": ("user",)}),
        (
            "Personal Information",
            {
                "fields": (
                    "full_name",
                    "email",
                    "phone",
                    "address",
                )
            },
        ),
        (
            "CV Content",
            {
                "fields": (
                    "job_title",
                    "professional_summary",
                    "skills",
                    "experience",
                    "education",
                )
            },
        ),
        (
            "Template & Upload",
            {
                "fields": (
                    "template",
                    "uploaded_file",
                )
            },
        ),
        ("Dates", {"fields": ("created_at",)}),
    )


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "plan_name",
        "is_active",
        "stripe_customer_id",
        "stripe_subscription_id",
        "created_at",
    )

    search_fields = (
        "user__username",
        "user__email",
        "stripe_customer_id",
        "stripe_subscription_id",
    )

    list_filter = (
        "is_active",
        "plan_name",
        "created_at",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    fieldsets = (
        (
            "User & Plan",
            {
                "fields": (
                    "user",
                    "plan_name",
                    "is_active",
                )
            },
        ),
        (
            "Stripe Details",
            {
                "fields": (
                    "stripe_customer_id",
                    "stripe_subscription_id",
                )
            },
        ),
        (
            "Dates",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )
