from django.contrib import admin

from mcod.aed.admin.base import StaffOnlyMixin
from mcod.aed.models import AedRecord
from mcod.aed.registry import RegistryBuilder


@admin.register(AedRecord)
class AedRecordAdmin(StaffOnlyMixin, admin.ModelAdmin):
    list_display = ("id_aed", "nazwa_obiektu", "miejscowosc", "organization", "status", "updated")
    list_filter = ("status", "organization")
    search_fields = ("id_aed", "nazwa_obiektu", "miejscowosc")
    readonly_fields = [f.name for f in AedRecord._meta.fields]
    actions = ["rebuild"]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("organization")

    def get_actions(self, request):
        return super().get_actions(request) if request.user.is_superuser else {}

    def rebuild(self, request, queryset):
        count = RegistryBuilder(request.user).rebuild()
        self.message_user(request, "Scalono wykaz zbiorczy: %d urządzeń" % count)

    rebuild.short_description = "Scal wykaz zbiorczy z zasobów dostawców"
