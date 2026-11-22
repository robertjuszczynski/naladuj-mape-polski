from django.contrib import admin, messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse

from mcod.aed.constants import LeadReview
from mcod.aed.models import AedLead
from mcod.aed.opening_hours import OpeningHours
from mcod.aed.sources import source_meta, teryt_for
from mcod.organizations.models import Organization

MUNICIPALITY_PREFIX = 6
SHOWN = 100


def areas(user):
    """Institutions of the user that are municipalities (known TERYT), with the code prefix of their territory."""
    if user.is_superuser:
        titles = {m["wydawca"] for m in source_meta() if m.get("kod_teryt_gminy")}
        organizations = Organization.objects.filter(title__in=titles, status="published").order_by("title")
    else:
        organizations = user.organizations.all().order_by("title")
    return [(o, teryt_for(o.title)[:MUNICIPALITY_PREFIX]) for o in organizations if teryt_for(o.title)]


def territory_leads(user, organization_pk=None):
    """Leads on the territory of one of the user's municipalities (the chosen one or the first)."""
    found = areas(user)
    chosen = next((a for a in found if str(a[0].pk) == str(organization_pk)), found[0] if found else None)
    if chosen is None:
        return found, None, AedLead.objects.none()
    leads = AedLead.objects.filter(kod_teryt_gminy__startswith=chosen[1], in_register=False).select_related("source")
    return found, chosen[0], leads


def lead_for(user, pk):
    prefixes = [prefix for _, prefix in areas(user)]
    lead = get_object_or_404(AedLead, pk=pk)
    if not user.is_superuser and not any(lead.kod_teryt_gminy.startswith(p) for p in prefixes):
        raise Http404
    return lead


def recount(lead):
    if lead.request_id:
        request = lead.request
        request.lead_count = request.leads.filter(in_register=False).exclude(review__in=LeadReview.CLOSED).count()
        request.save(update_fields=["lead_count", "updated"])


def confirm(lead, organization):
    lead.review, lead.in_register = LeadReview.CONFIRMED, True
    lead.review_note = organization.title
    lead.save(update_fields=["review", "in_register", "review_note", "updated"])
    recount(lead)


@admin.register(AedLead)
class AedLeadAdmin(admin.ModelAdmin):
    def has_module_permission(self, request):
        user = request.user
        return user.is_active and user.is_staff and (user.is_superuser or bool(areas(user)))

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_change_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_urls(self):
        view = self.admin_site.admin_view
        return [path("<int:pk>/review/", view(self.review_view), name="aed_lead_review")] + super().get_urls()

    def changelist_view(self, request, extra_context=None):
        found, organization, leads = territory_leads(request.user, request.GET.get("org"))
        pending = leads.filter(review=LeadReview.PENDING)
        reviewed = leads.exclude(review=LeadReview.PENDING).exclude(review=LeadReview.CONFIRMED)
        confirmed = AedLead.objects.filter(review=LeadReview.CONFIRMED, review_note=getattr(organization, "title", None))
        return render(
            request,
            "admin/aed/territory.html",
            dict(
                self.admin_site.each_context(request),
                opts=self.model._meta,
                title="AED do potwierdzenia",
                organization=organization,
                areas=[a for a, _ in found],
                pending=[self._item(lead) for lead in pending.order_by("name")[:SHOWN]],
                pending_count=pending.count(),
                reviewed=reviewed.order_by("review", "name"),
                confirmed_count=confirmed.count(),
            ),
        )

    @staticmethod
    def _item(lead):
        data = lead.data or {}
        hours = data.get("godziny_dostepnosci", "")
        return {
            "lead": lead,
            "hours": OpeningHours.to_polish(hours) if hours else "",
            "place": ", ".join(x for x in (data.get("opis_lokalizacji"), data.get("pietro") and "piętro " + data["pietro"]) if x),
            "operator": lead.operator,
            "address": " ".join(x for x in (data.get("ulica"), data.get("numer_budynku")) if x),
            "public": lead.source.publishable,
        }

    def review_view(self, request, pk):
        lead = lead_for(request.user, pk)
        back = reverse("admin:aed_aedlead_changelist") + ("?org=%s" % request.POST["org"] if request.POST.get("org") else "")
        if request.method != "POST":
            return redirect(back)
        action = request.POST.get("action")
        if action == "ours":
            return redirect(reverse("admin:aed_single") + "?lead=%d" % lead.pk)
        if action == "not_ours":
            lead.review, lead.review_note = LeadReview.NOT_OURS, request.POST.get("note", "").strip()[:500]
            self._tell_ministry(lead, request)
            messages.info(request, "Zapisano. Ministerstwo poprosi o zgodę właściwego dysponenta.")
        elif action == "gone":
            lead.review, lead.review_note = LeadReview.GONE, request.POST.get("note", "").strip()[:500]
            messages.info(request, "Zapisano. Ten punkt nie trafi do wykazu.")
        elif action == "reopen":
            lead.review, lead.review_note = LeadReview.PENDING, ""
        else:
            raise Http404
        lead.save(update_fields=["review", "review_note", "updated"])
        recount(lead)
        return redirect(back)

    @staticmethod
    def _tell_ministry(lead, request):
        if lead.request_id:
            consent = lead.request
            note = "Gmina: „%s” to nie nasz AED%s." % (lead.name, ", dysponent: " + lead.review_note if lead.review_note else "")
            consent.notes = "\n".join(x for x in (consent.notes, note) if x)
            consent.save(update_fields=["notes", "updated"])
