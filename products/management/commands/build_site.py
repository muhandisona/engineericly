from django.core.management.base import BaseCommand

from products.site_builder import build_site


class Command(BaseCommand):
    help = "Build the static site for Cloudflare Pages"

    def add_arguments(self, parser):
        parser.add_argument(
            '--out',
            dest='out_dir',
            default='site-build',
            help='Output directory for the static site',
        )

    def handle(self, *args, **options):
        out_dir = options['out_dir']
        build_site(out_dir)
        self.stdout.write(self.style.SUCCESS(f"Built static site in {out_dir}"))
