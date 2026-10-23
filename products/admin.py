from datetime import timedelta

from django.contrib import admin, messages
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from unfold.admin import ModelAdmin
from unfold.decorators import action, display

from products.models import PostLink, PublishState
from products.widgets import CustomUnfoldAdminImageFieldWidget


@admin.register(PostLink)
class PostLinkAdmin(ModelAdmin):
    actions_list = ["publish_now"]
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

    @action(description="Publish now")
    def publish_now(self, request):
        state = PublishState.get()
        state.needs_publish = True
        state.changed_at = timezone.now() - timedelta(seconds=60)
        state.save()
        messages.success(request, "Publishing - the site updates in about a minute.")
        return redirect(reverse("admin:products_postlink_changelist"))

    def changelist_view(self, request, extra_context=None):
        storage = messages.get_messages(request)
        existing = list(storage)
        for m in existing:
            storage.add(m.level, m.message, m.extra_tags)
        if not existing:
            state = PublishState.get()
            if state.last_status == "error":
                lines = (state.last_error or "").strip().splitlines()
                err_msg = lines[0] if lines else "Publish failed"
                messages.warning(request, err_msg)
            elif state.needs_publish:
                messages.info(request, "Changes waiting to publish")
            elif state.last_published_at:
                messages.info(request, f"Last published: {state.last_published_at.strftime('%Y-%m-%d %H:%M:%S')}")
            else:
                messages.info(request, "Last published: never")
        return super().changelist_view(request, extra_context=extra_context)

