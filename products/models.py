from django.db import models
from django.utils import timezone


class PostLink(models.Model):
    title = models.CharField(
        max_length=255,
        help_text="It will be displayed as the 3D model/post link name on the card"
    )
    link = models.URLField(help_text="Link to the external product/post page")
    show_for_youtube = models.BooleanField(
        default=True,
        verbose_name="Show for YouTube",
        help_text="If checked, the post link will be shown for YouTube domain"
    )
    show_for_tiktok = models.BooleanField(
        default=True,
        verbose_name="Show for TikTok",
        help_text="If checked, the post link will be shown for TikTok domain"
    )
    show_for_instagram = models.BooleanField(
        default=True,
        verbose_name="Show for Instagram",
        help_text="If checked, the post link will be shown for Instagram domain"
    )
    is_pinned = models.BooleanField(
        default=False,
        verbose_name="Pin?",
        help_text="If checked, the post link will be pinned at the top of the list"
    )
    file = models.FileField(
        upload_to='post_links/',
        help_text="Upload an image or file related to the post link"
    )
    order = models.FloatField(
        verbose_name="Order",
        help_text="The order of the post link",
        null=True,
        blank=True
    )
    published_at = models.DateTimeField(
        default=timezone.now,
        null=True,
        blank=True,
        verbose_name="Published At",
        help_text="The date and time when the post link was published"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_pinned', '-order', '-published_at']
        verbose_name = "Post Link"
        verbose_name_plural = "Post Links"

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if self.order is None:
            last_item = PostLink.objects.order_by('-order').first()
            last_order = 0.0
            if last_item and last_item.order is not None:
                try:
                    last_order = float(last_item.order)
                except (TypeError, ValueError):
                    last_order = 0.0
            self.order = last_order + 1.0

        if self.published_at is None:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)


class PublishState(models.Model):
    needs_publish = models.BooleanField(default=False)
    changed_at = models.DateTimeField(null=True, blank=True)
    last_published_at = models.DateTimeField(null=True, blank=True)
    last_status = models.CharField(max_length=20, default="", blank=True)
    last_error = models.TextField(blank=True, default="")
    last_url = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        verbose_name = "Publish State"
        verbose_name_plural = "Publish State"

    def __str__(self):
        return f"PublishState(needs_publish={self.needs_publish}, status={self.last_status})"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
