from django.urls import path, re_path, reverse_lazy
from django.views.generic import RedirectView
from . import views

urlpatterns = [
    path('api/gallery', views.api_gallery_view, name='api_gallery'),
    path('healthz', views.healthz, name='healthz'),
    path('about/', views.about_view, name='about'),
    # One bio link per platform, each showing only the posts ticked for it.
    re_path(r'^ig/?$', views.feed_view, {'platform': 'instagram'}, name='feed_instagram'),
    re_path(r'^tt/?$', views.feed_view, {'platform': 'tiktok'}, name='feed_tiktok'),
    re_path(r'^yt/?$', views.feed_view, {'platform': 'youtube'}, name='feed_youtube'),
    # Django only serves the admin now (the public grid is on Cloudflare Pages), so the bare
    # admin.engineericly.com goes straight to it. /all/ keeps an all-posts preview.
    re_path(r'^all/?$', views.feed_view, name='feed'),
    path('', RedirectView.as_view(url=reverse_lazy('admin:index')), name='home'),
]
