from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.utils import timezone

from .models import PostLink, PublishState


@receiver(post_save, sender=PostLink)
@receiver(post_delete, sender=PostLink)
def on_post_link_changed(sender, instance, **kwargs):
    PublishState.get()  # make sure the row exists
    # A targeted UPDATE, so it can't clobber the publisher's own write of the same row.
    PublishState.objects.filter(pk=1).update(needs_publish=True, changed_at=timezone.now())
