from django.contrib import admin
from .models import (
    Trainer,
    Membership,
    ClientMembership,
    Client,
    Payment,
    CheckIn,
    ClientSync,
)


# -----------------------------
# Inlines
# -----------------------------
class ClientMembershipInline(admin.TabularInline):
    model = ClientMembership
    extra = 0
    autocomplete_fields = ["membership"]
    fields = (
        "membership",
        "start_date",
        "end_date",
        "remaining_visits",
        "status",
        "created_at",
    )
    readonly_fields = ("created_at",)


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    autocomplete_fields = ["membership", "trainer", "client_membership"]
    fields = (
        "operation_date",
        "membership",
        "trainer",
        "membership_amount",
        "trainer_fee",
        "amount",
        "method",
        "client_membership",
        "created_at",
    )
    readonly_fields = ("created_at",)


class CheckInInline(admin.TabularInline):
    model = CheckIn
    extra = 0
    fields = ("created_at",)
    readonly_fields = ("created_at",)


class ClientSyncInline(admin.TabularInline):
    model = ClientSync
    extra = 0
    fields = ("action", "status", "error", "created_at", "synced_at")
    readonly_fields = ("created_at", "synced_at")


# -----------------------------
# Admin classes
# -----------------------------
@admin.register(Trainer)
class TrainerAdmin(admin.ModelAdmin):
    list_display = ("id", "first_name", "last_name", "phone", "specialization", "fee")
    search_fields = ("first_name", "last_name", "phone", "specialization")
    list_filter = ("specialization",)
    ordering = ("first_name", "last_name")


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "membership_type",
        "price",
        "duration_days",
        "visit_count",
    )
    search_fields = ("name",)
    list_filter = ("membership_type",)
    ordering = ("name",)


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "passId",
        "first_name",
        "last_name",
        "phone",
        "email",
        "organization",
        "card_number",
        "gender",
        "created_at",
        "has_active_membership",
        "photo"
    )
    search_fields = (
        "first_name",
        "last_name",
        "phone",
        "email",
        "organization",
        "card_number",
    )
    list_filter = ("gender", "created_at")
    readonly_fields = ("created_at",)
    ordering = ("-id",)
    inlines = [ClientMembershipInline, PaymentInline, CheckInInline, ClientSyncInline]

    fieldsets = (
        ("ძირითადი ინფორმაცია", {
            "fields": (
                "first_name",
                "last_name",
                "birth_date",
                "gender",
                "phone",
                "email",
                "organization",
            )
        }),
        ("დამატებითი ინფორმაცია", {
            "fields": (
                "card_number",
                "photo",
                "comment",
                "created_at",
            )
        }),
    )


@admin.register(ClientMembership)
class ClientMembershipAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "client",
        "membership",
        "start_date",
        "end_date",
        "remaining_visits",
        "status",
        "created_at",
        "is_active_display",
    )
    search_fields = (
        "client__first_name",
        "client__last_name",
        "client__phone",
        "membership__name",
    )
    list_filter = ("status", "membership__membership_type", "start_date", "end_date")
    autocomplete_fields = ("client", "membership")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)
    date_hierarchy = "start_date"

    @admin.display(boolean=True, description="რეალურად აქტიური")
    def is_active_display(self, obj):
        return obj.is_active()


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "client",
        "membership",
        "trainer",
        "amount",
        "membership_amount",
        "trainer_fee",
        "method",
        "operation_date",
        "created_at",
    )
    search_fields = (
        "client__first_name",
        "client__last_name",
        "client__phone",
        "membership__name",
        "trainer__first_name",
        "trainer__last_name",
    )
    list_filter = ("method", "operation_date", "created_at", "trainer", "membership")
    autocomplete_fields = ("client", "membership", "trainer", "client_membership")
    readonly_fields = ("created_at",)
    ordering = ("-operation_date", "-id")
    date_hierarchy = "operation_date"


@admin.register(CheckIn)
class CheckInAdmin(admin.ModelAdmin):
    list_display = ("id", "client", "created_at")
    search_fields = (
        "client__first_name",
        "client__last_name",
        "client__phone",
        "client__card_number",
    )
    list_filter = ("created_at",)
    autocomplete_fields = ("client",)
    ordering = ("-created_at",)
    date_hierarchy = "created_at"


@admin.register(ClientSync)
class ClientSyncAdmin(admin.ModelAdmin):
    list_display = ("id", "client", "action", "status", "created_at", "synced_at")
    search_fields = (
        "client__first_name",
        "client__last_name",
        "client__phone",
        "client__card_number",
        "error",
    )
    list_filter = ("action", "status", "created_at", "synced_at")
    autocomplete_fields = ("client",)
    readonly_fields = ("created_at", "synced_at")
    ordering = ("-created_at",)
    date_hierarchy = "created_at"