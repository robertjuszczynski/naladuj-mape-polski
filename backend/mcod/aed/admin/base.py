from mcod.organizations.models import Organization


def user_organizations(user):
    if user.is_superuser:
        return Organization.objects.filter(status="published").order_by("title")
    return user.organizations.all().order_by("title")


class StaffOnlyMixin:
    def has_module_permission(self, request):
        return request.user.is_active and request.user.is_staff

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if request.user.is_superuser:
            return queryset
        return queryset.filter(organization__in=user_organizations(request.user))
