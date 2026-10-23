import sys

from django.core.management.base import BaseCommand

from products.models import PublishState
from products.publisher import publish


class Command(BaseCommand):
    help = "Publish static site once to Cloudflare Pages"

    def handle(self, *args, **options):
        success = publish()
        state = PublishState.get()
        if success:
            self.stdout.write(self.style.SUCCESS(f"Published successfully. URL: {state.last_url}"))
        else:
            self.stderr.write(self.style.ERROR(f"Publish failed: {state.last_error}"))
            sys.exit(1)
