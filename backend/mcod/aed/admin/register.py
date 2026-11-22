from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html, format_html_join

from mcod.aed.models import AggregatedAedInfo
from mcod.aed.registry import RegistryBuilder


@admin.register(AggregatedAedInfo)
class AggregatedAedInfoAdmin(admin.ModelAdmin):
    """The main AED register and which provider resources went into it, like the main DGA list."""

    list_display = ("__str__", "main_resource", "source_count", "aed_count")
    readonly_fields = ("updated_at", "main_resource", "sources_report", "conflicts_report")
    fields = readonly_fields
    actions = ["rebuild"]

    def has_module_permission(self, request):
        return request.user.is_active and request.user.is_staff

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_actions(self, request):
        return super().get_actions(request) if request.user.is_superuser else {}

    def main_resource(self, obj):
        if obj.resource is None:
            return "–"
        return format_html(
            '<a href="{}">{}</a>', reverse("admin:resources_resource_change", args=[obj.resource_id]), obj.resource
        )

    main_resource.short_description = "Zasób wykazu zbiorczego"

    def source_count(self, obj):
        return len(obj.sources)

    source_count.short_description = "Zasoby dostawców"

    def aed_count(self, obj):
        return sum(s["published"] for s in obj.sources)

    aed_count.short_description = "AED w wykazie"

    def sources_report(self, obj):
        rows = format_html_join(
            "",
            '<tr><td><a href="{}">{}</a></td><td>{}</td><td style="white-space:nowrap">{}</td>'
            '<td style="text-align:right">{}</td><td style="text-align:right">{}</td><td style="white-space:nowrap">{}</td></tr>',
            (
                (
                    reverse("admin:resources_resource_change", args=[s["resource_id"]]),
                    s["resource"],
                    s["organization"],
                    s["license"],
                    s["rows"],
                    s["published"],
                    s["error"] or "odczytano",
                )
                for s in obj.sources
            ),
        )
        return format_html(
            '<table style="width:100%"><thead><tr><th>Zasób</th><th>Dostawca</th><th style="white-space:nowrap">Licencja</th>'
            '<th style="white-space:nowrap">Wierszy</th><th style="white-space:nowrap">W wykazie</th>'
            '<th style="white-space:nowrap">Stan</th></tr></thead><tbody>{}</tbody></table>',
            rows,
        )

    sources_report.short_description = "Źródła"

    def conflicts_report(self, obj):
        if not obj.conflicts:
            return "Brak – źródła nie opisują tego samego AED inaczej."
        rows = format_html_join(
            "",
            "<tr><td>{}<br><small>{} · {}</small></td><td>{}</td><td>{}</td></tr>",
            (
                (c["a"]["name"] or c["a"]["id"], c["a"]["source"], c["a"]["id"], self._other(c), self._differences(c))
                for c in obj.conflicts
            ),
        )
        return format_html(
            "<p>{} przypadków: ten sam AED (do 30 m albo ten sam identyfikator) opisany przez źródła inaczej "
            "albo pola jednego rekordu, które sobie przeczą. Do wykazu trafia wersja pierwszego źródła; "
            "dostawca powinien ustalić, która jest aktualna.</p>"
            '<table style="width:100%"><thead><tr><th>AED</th><th style="white-space:nowrap">Drugie źródło</th>'
            "<th>Sprzeczność</th></tr></thead><tbody>{}</tbody></table>",
            len(obj.conflicts),
            rows,
        )

    @staticmethod
    def _other(conflict):
        other = conflict["b"]
        return "%s · %s" % (other["source"], other["name"] or other["id"]) if other else "–"

    @staticmethod
    def _differences(conflict):
        if conflict["b"] is None:
            return "; ".join(f["a"] for f in conflict["fields"])
        return "; ".join("%s: „%s” / „%s”" % (f["field"], f["a"], f["b"]) for f in conflict["fields"])

    conflicts_report.short_description = "Sprzeczne dane między źródłami"

    def rebuild(self, request, queryset):
        count = RegistryBuilder(request.user).rebuild()
        self.message_user(request, "Scalono wykaz zbiorczy: %d urządzeń" % count)

    rebuild.short_description = "Scal teraz wykaz zbiorczy"
