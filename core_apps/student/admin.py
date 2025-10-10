from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from core_apps.student import models as StudentModels
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


@admin.register(StudentModels.Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = [
        "parent",
        "admission_number",
        "first_name",
        "last_name",
        "gender",
        "account_status",
        "has_sibling",
        "get_verified_by",
    ]
    list_filter = [
        "account_status",
        "has_sibling",
        "gender",
    ]
    search_fields = [
        "admission_number",
        "parent__email",
        "parent__first_name",
        "parent__last_name",
        "first_name",
        "last_name",
    ]
    readonly_fields = [
        "admission_number",
        "verification_date",
        "created_at",
        "updated_at",
    ]
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "parent",
                    "admission_number",
                    "first_name",
                    "last_name",
                    "gender",
                )
            },
        ),
        (
            _("Status"),
            {
                "fields": (
                    "account_status",
                    "has_sibling",
                )
            },
        ),
        (
            _("Verification"),
            {
                "fields": (
                    "verified_by",
                    "verification_date",
                    "verification_notes",
                    "fully_activated",
                )
            },
        ),
        (
            _("Timestamps"),
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def get_verified_by(self, obj):
        return obj.verified_by.full_name if obj.verified_by else "-"

    get_verified_by.short_description = "Verified By"
    get_verified_by.admin_order_field = "verified_by__first_name"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs

        return qs.filter(verified_by=request.user)

    def has_change_permission(self, request, obj=None):
        if not obj:
            return True
        return request.user.is_superuser or obj.verified_by == request.user

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "verified_by":
            kwargs["queryset"] = User.objects.filter(is_staff=True)

        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        # Determine if verified_by changed or needs setting
        prev_verified_by = None
        if change and obj.pk:
            try:
                prev = StudentModels.Student.objects.get(pk=obj.pk)
                prev_verified_by = prev.verified_by
            except StudentModels.Student.DoesNotExist:
                prev_verified_by = None

        # Auto-set verified_by to current staff user if not provided
        if not obj.verified_by and request.user.is_staff:
            obj.verified_by = request.user

        # If verified_by was newly set or changed, update verification_date
        should_set_date = False
        if obj.verified_by and (not change or prev_verified_by != obj.verified_by):
            should_set_date = True

        if should_set_date:
            obj.verification_date = timezone.now()

        super().save_model(request, obj, form, change)