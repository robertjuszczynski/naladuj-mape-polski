from django.contrib import admin, messages
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse
from django.utils import timezone

from mcod.aed.admin.base import StaffOnlyMixin, user_organizations
from mcod.aed.constants import COLUMN_SAMPLE_SIZE, Decision
from mcod.aed.export import CorrectedCsvExport
from mcod.aed.importing.columns import ADDRESS_TARGET, ColumnMatcher
from mcod.aed.importing.geocoder import GugikGeocoder
from mcod.aed.importing.pipeline import ImportPipeline, ImportSource
from mcod.aed.importing.reader import UploadError, UploadValidator
from mcod.aed.models import AedUpload
from mcod.aed.profile import FIELDS, PROFILE_VERSION
from mcod.aed.publishing import DatasetPublisher, license_from_form, license_name, license_options
from mcod.aed.registry import RegistryBuilder
from mcod.aed.validation import PortalQualityCheck

STEPS = ["Plik", "Kolumny", "Sprawdzenie", "Licencja", "Gotowe"]


@admin.register(AedUpload)
class AedUploadAdmin(StaffOnlyMixin, admin.ModelAdmin):
    list_display = ("filename", "organization", "status", "created", "published")
    actions = None
    list_filter = ("status",)

    def has_add_permission(self, request):
        return self.has_module_permission(request)

    def has_change_permission(self, request, obj=None):
        owner = obj is None or request.user.is_superuser or obj.user_id == request.user.id
        return self.has_module_permission(request) and owner

    def has_delete_permission(self, request, obj=None):
        return self.has_change_permission(request, obj)

    def get_urls(self):
        view = self.admin_site.admin_view
        return [
            path("wgraj/", view(self.step_file), name="aed_wgraj"),
            path("<int:pk>/kolumny/", view(self.step_columns), name="aed_kolumny"),
            path("<int:pk>/sprawdzenie/", view(self.step_review), name="aed_sprawdzenie"),
            path("<int:pk>/licencja/", view(self.step_license), name="aed_licencja"),
            path("<int:pk>/gotowe/", view(self.step_done), name="aed_gotowe"),
            path("<int:pk>/pobierz/", view(self.download_fixed), name="aed_pobierz"),
        ] + super().get_urls()

    def add_view(self, request, form_url="", extra_context=None):
        return redirect("admin:aed_wgraj")

    def changelist_view(self, request, extra_context=None):
        if not self.get_queryset(request).exists():
            return redirect("admin:aed_wgraj")
        return super().changelist_view(request, extra_context)

    def change_view(self, request, object_id, form_url="", extra_context=None):
        upload = self.get_upload(request, object_id)
        return redirect("admin:aed_gotowe" if upload.is_published else "admin:aed_sprawdzenie", pk=upload.pk)

    def render_step(self, request, template, step, **context):
        base = dict(
            self.admin_site.each_context(request),
            title="Dodaj dane o AED",
            steps=STEPS,
            step=step,
            opts=self.model._meta,
            profile_version=PROFILE_VERSION,
        )
        return render(request, "admin/aed/%s.html" % template, dict(base, **context))

    def get_upload(self, request, pk):
        upload = get_object_or_404(self.get_queryset(request), pk=pk)
        if not self.has_change_permission(request, upload):
            raise PermissionDenied
        return upload

    def step_file(self, request):
        organizations = user_organizations(request.user)
        if request.method == "POST":
            upload = self._create_upload(request, organizations)
            if upload is not None:
                return redirect("admin:aed_kolumny", pk=upload.pk)
        return self.render_step(request, "step_file", 1, orgs=organizations)

    def _create_upload(self, request, organizations):
        uploaded = request.FILES.get("plik")
        organization = organizations.filter(pk=request.POST.get("organizacja")).first()
        if not uploaded or not organization:
            messages.error(request, "Wybierz instytucję i plik CSV albo XLSX.")
            return None
        try:
            table = UploadValidator().read(uploaded)
        except UploadError as exc:
            messages.error(request, str(exc))
            return None
        if not table.header or not table.rows:
            messages.error(request, "Plik nie zawiera danych.")
            return None
        return AedUpload.objects.create(
            user=request.user,
            organization=organization,
            filename=uploaded.name,
            header=table.header,
            rows=table.rows,
            repairs=table.repairs,
            mapping=ColumnMatcher().suggest(table.header, table.rows),
        )

    def step_columns(self, request, pk):
        upload = self.get_upload(request, pk)
        if request.method == "POST":
            mapping = {column: request.POST.get("col_%d" % i, "") for i, column in enumerate(upload.header)}
            upload.run_import(self._pipeline(upload), mapping)
            upload.save()
            return redirect("admin:aed_sprawdzenie", pk=upload.pk)
        sample = upload.rows[:COLUMN_SAMPLE_SIZE]
        columns = [
            {
                "i": i,
                "name": column,
                "target": upload.mapping.get(column, ""),
                "sample": " · ".join(r[i] for r in sample if i < len(r) and r[i]),
            }
            for i, column in enumerate(upload.header)
        ]
        return self.render_step(
            request, "step_columns", 2, up=upload, columns=columns, fields=FIELDS, address_target=ADDRESS_TARGET
        )

    @staticmethod
    def _pipeline(upload):
        organization = upload.organization
        source = ImportSource.for_organization(
            organization, "Kreator „Dodaj dane o AED”, %s" % organization.title, timezone.now().date().isoformat()
        )
        return ImportPipeline(source, geocoder=GugikGeocoder(cache=cache))

    def step_review(self, request, pk):
        upload = self.get_upload(request, pk)
        if request.method == "POST":
            index = request.POST.get("idx", "")
            if index.isdigit() and upload.apply_decision(int(index), request.POST.get("action"), request.POST):
                upload.save()
            return redirect("admin:aed_sprawdzenie", pk=upload.pk)
        quality = PortalQualityCheck().run([c["record"] for c in upload.checked])
        return self.render_step(
            request,
            "step_review",
            3,
            up=upload,
            rows=upload.review.review_rows(),
            summary=upload.summary(),
            fix_action=Decision.FIX,
            quality_errors=[q for q in quality if q["errors"]],
            quality_checked=len([q for q in quality if q["checked"]]),
        )

    def download_fixed(self, request, pk):
        return CorrectedCsvExport(self.get_upload(request, pk)).response()

    def step_license(self, request, pk):
        upload = self.get_upload(request, pk)
        to_publish = upload.rows_for_publish()
        others = upload.foreign_operator_rows()
        if request.method == "POST":
            error = self._license_error(request, to_publish, others)
            if error:
                messages.error(request, error)
            else:
                self._publish(request, upload, to_publish)
                return redirect("admin:aed_gotowe", pk=upload.pk)
        return self.render_step(
            request,
            "step_license",
            4,
            up=upload,
            count=len(to_publish),
            held=len(upload.checked) - len(to_publish),
            others=len(others),
            others_orgs=len({(r.get("dysponent_nazwa") or "").strip().lower() for r in others}),
            licenses=license_options(),
        )

    @staticmethod
    def _license_error(request, to_publish, others):
        if not request.POST.get("zgoda"):
            return "Publikacja wymaga oświadczenia o prawie do udostępnienia danych."
        if others and not request.POST.get("zgoda_inni"):
            return "Plik zawiera AED innych dysponentów – potwierdź zgodę lub podstawę prawną."
        if not to_publish:
            return "Brak rekordów do publikacji."
        return None

    @staticmethod
    @transaction.atomic
    def _publish(request, upload, records):
        license_code = license_from_form(request.POST.get("licencja", ""))
        dataset = DatasetPublisher(upload.organization, request.user).publish(records, license_code)
        RegistryBuilder.rebuild_on_commit()
        upload.mark_published(dataset, license_name(license_code))
        upload.save()

    def step_done(self, request, pk):
        upload = self.get_upload(request, pk)
        dataset_url = reverse("admin:datasets_dataset_change", args=[upload.dataset_id]) if upload.dataset_id else None
        return self.render_step(request, "step_done", 5, up=upload, ds_url=dataset_url)
