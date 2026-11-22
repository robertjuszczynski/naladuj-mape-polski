"""Maximising the register: outside sources and the consent queue for AEDs whose licence does not allow publishing."""

from django.conf import settings
from django.contrib import admin, messages
from django.core.mail import send_mail
from django.db.models import Case, When
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse
from django.utils import timezone

from mcod.aed.api.serializers import AedStats
from mcod.aed.constants import ConsentStatus
from mcod.aed.models import AedSource, ConsentRequest
from mcod.aed.outside import ConsentQueue
from mcod.aed.registry import RegistryBuilder

QUEUE_PAGE = 40
INVITE_PREVIEW = 15
SINGLE_PATH = "/aed/aedtask/single/"
UNKNOWN_KEY = "gm:?"


class SuperuserOnly:
    def has_module_permission(self, request):
        return request.user.is_active and request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_change_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        return self.has_module_permission(request)

    def has_delete_permission(self, request, obj=None):
        return self.has_module_permission(request)


@admin.register(AedSource)
class AedSourceAdmin(SuperuserOnly, admin.ModelAdmin):
    list_display = ("name", "licence", "parser", "fetched", "rows", "published", "held", "error")
    readonly_fields = ("fetched", "rows", "published", "held", "error")
    actions = ["fetch_now"]

    def fetch_now(self, request, queryset):
        from mcod.aed.tasks import fetch_aed_source

        for source in queryset:
            fetch_aed_source.delay(source.pk)
        self.message_user(
            request, "Pobieranie %d źródeł ruszyło w tle. Wynik pojawi się na liście za kilka minut." % queryset.count()
        )

    fetch_now.short_description = "Pobierz teraz"


@admin.register(ConsentRequest)
class ConsentRequestAdmin(SuperuserOnly, admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def get_urls(self):
        view = self.admin_site.admin_view
        return [path("<int:pk>/act/", view(self.act_view), name="aed_consent_act")] + super().get_urls()

    def changelist_view(self, request, extra_context=None):
        status = request.GET.get("status", ConsentStatus.TO_CONTACT)
        queue = ConsentRequest.objects.filter(lead_count__gt=0)
        counts = {code: queue.filter(status=code).count() for code, _ in ConsentStatus.CHOICES}
        context = dict(
            self.admin_site.each_context(request),
            opts=self.model._meta,
            title="Pozyskiwanie danych",
            stats=AedStats(timezone.localtime()).sources(),
            sources=AedSource.objects.all(),
            statuses=[(code, label, counts[code]) for code, label in ConsentStatus.CHOICES],
            status=status,
            requests=queue.filter(status=status).order_by(Case(When(key=UNKNOWN_KEY, then=1), default=0), "-lead_count")[
                :QUEUE_PAGE
            ],
            total=counts.get(status, 0),
            page=QUEUE_PAGE,
        )
        return render(request, "admin/aed/acquisition.html", context)

    def act_view(self, request, pk):
        consent = get_object_or_404(ConsentRequest, pk=pk)
        if request.method != "POST":
            return redirect("admin:aed_consentrequest_changelist")
        consent.contact = request.POST.get("contact", consent.contact).strip()
        consent.notes = request.POST.get("notes", consent.notes)
        action = request.POST.get("action")
        if action == "invite":
            self._invite(request, consent)
        elif action == "agreed":
            published = ConsentQueue().publish_agreed(consent, request.user)
            RegistryBuilder(request.user).rebuild()
            messages.success(request, "Opublikowano %d AED za zgodą: %s." % (published, consent.label))
        elif action in dict(ConsentStatus.CHOICES):
            consent.status = action
        consent.save()
        url = reverse("admin:aed_consentrequest_changelist")
        return redirect("%s?status=%s" % (url, request.POST.get("back", ConsentStatus.TO_CONTACT)))

    @staticmethod
    def _invite(request, consent):
        if "@" not in consent.contact:
            messages.error(request, "Podaj adres e-mail dysponenta, żeby wysłać zaproszenie.")
            return
        leads = list(consent.leads.filter(in_register=False)[:INVITE_PREVIEW])
        lines = "\n".join("- %s (%.5f, %.5f)" % (lead.name, lead.lat, lead.lon) for lead in leads)
        more = consent.lead_count - len(leads)
        body = (
            "Dzień dobry,\n\nw ramach akcji „Naładuj mapę Polski.” zbieramy w portalu dane.gov.pl "
            "informacje o defibrylatorach AED, "
            "żeby dyspozytorzy 112 i świadkowie mogli szybko znaleźć najbliższy dostępny AED.\n\n"
            "Z publicznych źródeł wiemy o %d AED, którymi prawdopodobnie Państwo dysponują:\n%s%s\n\n"
            "Czy zgadzają się Państwo na ich publikację jako otwarte dane (licencja CC0)? Wystarczy odpowiedzieć na tę wiadomość "
            "albo sprawdzić i poprawić dane samodzielnie: %s%s\n\nUdział jest dobrowolny.\nZespół dane.gov.pl"
            % (
                consent.lead_count,
                lines,
                "\n- …i %d więcej" % more if more > 0 else "",
                settings.ADMIN_URL.rstrip("/"),
                SINGLE_PATH,
            )
        )
        send_mail("Państwa AED na mapie dla 112 – prośba o zgodę", body, settings.DEFAULT_FROM_EMAIL, [consent.contact])
        consent.status = ConsentStatus.CONTACTED
        consent.notes = ("%s: wysłano zaproszenie e-mail na %s\n" % (timezone.localdate(), consent.contact)) + consent.notes
        messages.success(request, "Wysłano zaproszenie do: %s." % consent.label)
