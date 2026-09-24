from django.contrib import admin
from unfold.admin import ModelAdmin
from unfold.decorators import display

from products.widgets import CustomUnfoldAdminImageFieldWidget


from products.models import *


@admin.register(PostLink)
class PostLinkAdmin(ModelAdmin):
    list_display = ('cover', 'title', 'on_instagram', 'on_tiktok', 'on_youtube', 'is_pinned', 'order', 'published_at')
    list_display_links = ('cover', 'title')
    search_fields = ('title', 'link')
    list_filter = ('is_pinned', 'show_for_youtube', 'show_for_tiktok', 'show_for_instagram', 'created_at', 'updated_at')
    list_filter_submit = True
    compressed_fields = True
    warn_unsaved_form = True
    list_fullwidth = True
    # Same order as the public grid: pinned first, then highest order, then newest.
    ordering = ('-is_pinned', '-order', '-published_at')

    fieldsets = (
        (None, {'fields': ('title', 'link', 'is_pinned', 'order')}),
        ("Show on", {
            'fields': ('show_for_instagram', 'show_for_tiktok', 'show_for_youtube'),
            'description': "Each platform's bio link (/ig, /tt, /yt) only shows the posts ticked for it.",
        }),
        ("Cover", {'fields': ('file',)}),
        ('Timestamps', {'fields': ('published_at', 'created_at', 'updated_at')}),
    )
    readonly_fields = ('id', 'created_at', 'updated_at')

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        form.base_fields['file'].widget = CustomUnfoldAdminImageFieldWidget()
        return form

    @display(description="Cover", image=True)
    def cover(self, obj):
        return obj.file.url if obj.file else None

    @display(description="Instagram", boolean=True)
    def on_instagram(self, obj):
        return obj.show_for_instagram

    @display(description="TikTok", boolean=True)
    def on_tiktok(self, obj):
        return obj.show_for_tiktok

    @display(description="YouTube", boolean=True)
    def on_youtube(self, obj):
        return obj.show_for_youtube
