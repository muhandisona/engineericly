import logging
import time

from django.conf import settings
from django.core.management.base import BaseCommand

from products.models import PublishState
from products.publisher import is_due, publish

logger = logging.getLogger('publisher')


class Command(BaseCommand):
    help = "Run the static site publisher daemon"

    def add_arguments(self, parser):
        parser.add_argument(
            '--once',
            action='store_true',
            help='Run one check and exit',
        )

    def handle(self, *args, **options):
        once = options['once']
        poll_seconds = getattr(settings, 'PUBLISH_POLL_SECONDS', 15)
        # After a failed deploy (bad token, Cloudflare down) wait longer before retrying.
        retry_seconds = getattr(settings, 'PUBLISH_RETRY_SECONDS', 300)

        while True:
            wait = poll_seconds
            if is_due():
                ok = publish()
                state = PublishState.get()
                msg = f"Published: status={state.last_status} url={state.last_url} error={state.last_error}"
                logger.info(msg)
                self.stdout.write(msg)
                if not ok:
                    wait = max(poll_seconds, retry_seconds)
            if once:
                break
            time.sleep(wait)
