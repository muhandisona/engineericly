from urllib.parse import urlparse

from django.core.paginator import EmptyPage, Paginator
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone

from .models import PostLink

PAGE_SIZE = 18  # multiple of 3 so every page fills whole grid rows

# platform -> PostLink flag that makes a post visible on that platform's grid
PLATFORM_FIELDS = {
    'instagram': 'show_for_instagram',
    'tiktok': 'show_for_tiktok',
    'youtube': 'show_for_youtube',
}

PLATFORM_URL_NAMES = {
    'instagram': 'feed_instagram',
    'tiktok': 'feed_tiktok',
    'youtube': 'feed_youtube',
}


def detect_platform(value):
    """Guess the platform from a URL or hostname (e.g. a Referer header)."""
    value = (value or '').lower()
    host = urlparse(value).hostname or value
    if 'instagram' in host:
        return 'instagram'
    if 'tiktok' in host:
        return 'tiktok'
    if 'youtube' in host or 'youtu.be' in host:
        return 'youtube'
    return ''


def healthz(request):
    """Liveness probe for the Docker healthcheck."""
    return HttpResponse('ok', content_type='text/plain')


def feed_view(request, platform=''):
    """The bio-link grid. /ig, /tt and /yt pin the platform; / falls back to the referrer."""
    if not platform:
        platform = detect_platform(request.META.get('HTTP_REFERER', ''))
    return render(request, 'feed.html', {'platform': platform, 'static_site': False})


def about_view(request):
    platform = request.GET.get('from', '')
    if platform in PLATFORM_URL_NAMES:
        back_url = reverse(PLATFORM_URL_NAMES[platform])
    else:
        platform = ''
        back_url = reverse('feed')
    return render(request, 'about.html', {'platform': platform, 'back_url': back_url, 'static_site': False})


def get_visible_posts(platform='', now=None):
    """Return the visible PostLink queryset for a platform.

    If platform is empty or unknown, all visible posts are returned.
    Only posts with published_at null or <= now are included.
    """
    if now is None:
        now = timezone.now()
    qs = PostLink.objects.filter(
        Q(published_at__isnull=True) | Q(published_at__lte=now)
    )
    if platform and platform in PLATFORM_FIELDS:
        qs = qs.filter(**{PLATFORM_FIELDS[platform]: True})
    return qs


def post_to_dict(post):
    """Turn a PostLink into an item dict matching the gallery API shape."""
    host = urlparse(post.link).hostname or ''
    return {
        'id': post.id,
        'title': post.title,
        'link': post.link,
        'host': host.removeprefix('www.'),
        'image': post.file.url if post.file else '',
        'is_pinned': post.is_pinned,
    }


def api_gallery_view(request):
    """Post links as JSON, filtered to one platform's grid when `platform` is given."""
    try:
        page = int(request.GET.get('page', 1))
    except ValueError:
        page = 1

    platform = request.GET.get('platform', '')
    if platform not in PLATFORM_FIELDS:
        # Older clients sent a `domain` instead of a platform name.
        platform = detect_platform(request.GET.get('domain', ''))

    post_links = get_visible_posts(platform)

    # Ordering comes from Meta.ordering: pinned first, then highest order, then newest.
    paginator = Paginator(post_links, PAGE_SIZE)
    try:
        page_obj = paginator.page(page)
        posts = list(page_obj)
        has_next = page_obj.has_next()
    except EmptyPage:
        posts = []
        has_next = False

    items = [post_to_dict(p) for p in posts]

    return JsonResponse({
        'items': items,
        'page': page,
        'has_next': has_next,
        'total_pages': paginator.num_pages,
        'total_items': paginator.count,
        'platform': platform,
    })
