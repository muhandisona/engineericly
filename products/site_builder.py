import json
import os
import shutil
from urllib.parse import urlparse

from django.conf import settings
from django.core.paginator import Paginator
from django.template.loader import render_to_string
from django.test import RequestFactory
from django.test.utils import override_settings
from django.utils import timezone

from .views import PAGE_SIZE, get_visible_posts, post_to_dict

HEADERS_CONTENT = (
    "/static/*\n"
    "  Cache-Control: public, max-age=86400\n"
    "/media/*\n"
    "  Cache-Control: public, max-age=604800\n"
    "/data/*\n"
    "  Cache-Control: public, max-age=60\n"
)


def build_site(out_dir):
    """Build the static site into out_dir for Cloudflare Pages."""
    # The pages are rendered as if requested on the public host, which the admin server's
    # ALLOWED_HOSTS does not (and should not) list, so allow it just for the build.
    public_host = urlparse(getattr(settings, 'PUBLIC_SITE_URL', 'https://links.engineericly.com')).hostname
    allowed = list(settings.ALLOWED_HOSTS) + ([public_host] if public_host else [])
    with override_settings(ALLOWED_HOSTS=allowed):
        _build_site(out_dir)


def _build_site(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    now = timezone.now()

    # RequestFactory for template rendering with public host/scheme
    public_site_url = getattr(settings, 'PUBLIC_SITE_URL', 'https://links.engineericly.com')
    parsed = urlparse(public_site_url)
    scheme = parsed.scheme or 'https'
    host = parsed.netloc or parsed.path.rstrip('/')
    is_secure = (scheme == 'https')
    rf = RequestFactory()

    # 1. Render HTML pages
    pages = [
        ('index.html', '', '/'),
        ('ig.html', 'instagram', '/ig'),
        ('tt.html', 'tiktok', '/tt'),
        ('yt.html', 'youtube', '/yt'),
    ]

    for filename, platform, path in pages:
        req = rf.get(path, HTTP_HOST=host, secure=is_secure)
        content = render_to_string(
            'feed.html',
            {'platform': platform, 'static_site': True},
            request=req,
        )
        with open(os.path.join(out_dir, filename), 'w', encoding='utf-8') as f:
            f.write(content)

    # About page at about/index.html
    about_dir = os.path.join(out_dir, 'about')
    os.makedirs(about_dir, exist_ok=True)
    about_req = rf.get('/about/', HTTP_HOST=host, secure=is_secure)
    about_content = render_to_string(
        'about.html',
        {'platform': '', 'back_url': '/', 'static_site': True},
        request=about_req,
    )
    with open(os.path.join(about_dir, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(about_content)

    # 2. Page JSON per platform
    platforms = [
        ('all', ''),
        ('instagram', 'instagram'),
        ('tiktok', 'tiktok'),
        ('youtube', 'youtube'),
    ]

    for folder_name, platform_param in platforms:
        platform_dir = os.path.join(out_dir, 'data', folder_name)
        os.makedirs(platform_dir, exist_ok=True)

        qs = get_visible_posts(platform=platform_param, now=now)
        paginator = Paginator(qs, PAGE_SIZE)

        for page_num in range(1, paginator.num_pages + 1):
            page_obj = paginator.page(page_num)
            items = [post_to_dict(p) for p in page_obj]
            data = {
                'items': items,
                'page': page_num,
                'has_next': page_obj.has_next(),
                'total_pages': paginator.num_pages,
                'total_items': paginator.count,
                'platform': platform_param,
            }
            page_file = os.path.join(platform_dir, f'{page_num}.json')
            with open(page_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

    # 3. Static assets (only project assets, not django admin or unfold)
    assets_dir = getattr(settings, 'ASSETS_DIR', os.path.join(settings.BASE_DIR, 'assets'))
    dest_static = os.path.join(out_dir, 'static')
    if os.path.exists(assets_dir):
        shutil.copytree(
            assets_dir,
            dest_static,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns('.DS_Store', '*.pyc', '__pycache__'),
        )

    # 4. Media covers referenced by published posts only
    all_visible = get_visible_posts('', now=now)
    seen_files = set()
    for post in all_visible:
        if post.file and post.file.name:
            rel_name = post.file.name
            if rel_name in seen_files:
                continue
            seen_files.add(rel_name)

            try:
                src_path = post.file.path
            except (AttributeError, NotImplementedError):
                src_path = os.path.join(settings.MEDIA_ROOT, rel_name)

            if os.path.isfile(src_path):
                dest_file = os.path.join(out_dir, 'media', rel_name)
                os.makedirs(os.path.dirname(dest_file), exist_ok=True)
                shutil.copy2(src_path, dest_file)

    # 5. Cache headers
    with open(os.path.join(out_dir, '_headers'), 'w', encoding='utf-8') as f:
        f.write(HEADERS_CONTENT)
