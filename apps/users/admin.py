from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Profile

User = get_user_model()


# Keep transparent guest accounts out of the Django admin user list.
try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass


@admin.register(User)
class GuestAwareUserAdmin(BaseUserAdmin):
    def get_queryset(self, request):
        return super().get_queryset(request).exclude(profile__is_guest=True)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'is_guest', 'created_at')
    list_filter = ('role', 'is_guest')
    search_fields = ('user__username', 'user__email')

    def get_queryset(self, request):
        return super().get_queryset(request).exclude(is_guest=True)
