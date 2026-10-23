from datetime import timedelta
import os
import re
import subprocess
import tempfile

from django.conf import settings
from django.utils import timezone

from .models import PostLink, PublishState
from .site_builder import build_site


def parse_deployment_url(output):
    """Extract deployment URL from wrangler stdout/stderr."""
    if not output:
        return ""
    match = re.search(r'https://[a-zA-Z0-9.-]+\.pages\.dev', output)
    if match:
        return match.group(0)
    match = re.search(r'https://[^\s"\'>]+', output)
    if match:
        return match.group(0)
    return ""


def _record(**fields):
    # Update only the given columns, so edits saved meanwhile (needs_publish/changed_at) survive.
    PublishState.get()
    PublishState.objects.filter(pk=1).update(**fields)


def publish():
    """Build the static site and deploy to Cloudflare Pages via wrangler."""
    state = PublishState.get()
    token = getattr(settings, 'CLOUDFLARE_API_TOKEN', '')
    if not token:
        _record(last_status="error", last_error="Cloudflare is not configured")
        return False

    started_changed_at = state.changed_at
    # The build only includes posts visible at this moment, so this is the time the
    # published site reflects; a post scheduled after it is picked up by is_due().
    build_started_at = timezone.now()

    try:
        with tempfile.TemporaryDirectory() as out_dir:
            build_site(out_dir)

            cmd = [
                getattr(settings, 'WRANGLER_BIN', 'wrangler'),
                "pages",
                "deploy",
                out_dir,
                "--project-name",
                getattr(settings, 'CF_PAGES_PROJECT', 'engineericly-links'),
                "--branch",
                "main",
                "--commit-dirty=true",
            ]
            env = os.environ.copy()
            env["CLOUDFLARE_API_TOKEN"] = token
            account_id = getattr(settings, 'CLOUDFLARE_ACCOUNT_ID', '')
            if account_id:
                env["CLOUDFLARE_ACCOUNT_ID"] = account_id

            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
                env=env,
            )

        output = f"{proc.stdout or ''}\n{proc.stderr or ''}"
        if proc.returncode == 0:
            fields = {'last_status': "ok", 'last_published_at': build_started_at, 'last_error': ""}
            deploy_url = parse_deployment_url(proc.stdout) or parse_deployment_url(proc.stderr)
            if deploy_url:
                fields['last_url'] = deploy_url
            _record(**fields)
            # Clear the flag only if nothing was edited while deploying.
            PublishState.objects.filter(pk=1, changed_at=started_changed_at).update(needs_publish=False)
            return True
        else:
            _record(last_status="error", last_error=output.strip()[-2000:])
            return False

    except Exception as exc:
        _record(last_status="error", last_error=str(exc)[:2000])
        return False


def is_due(now=None):
    """Check if static site publish is due."""
    if now is None:
        now = timezone.now()
    state = PublishState.get()
    debounce = getattr(settings, 'PUBLISH_DEBOUNCE_SECONDS', 10)

    # 1. Needs publish and debounced
    if state.needs_publish:
        if state.changed_at is None or state.changed_at <= now - timedelta(seconds=debounce):
            return True

    # 2. Scheduled post became visible
    if state.last_published_at is not None:
        if PostLink.objects.filter(
            published_at__gt=state.last_published_at,
            published_at__lte=now,
        ).exists():
            return True

    # 3. Last published is None and posts exist
    if state.last_published_at is None and PostLink.objects.exists():
        return True

    return False
