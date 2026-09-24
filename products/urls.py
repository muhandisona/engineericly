from django.urls import path, re_path
from . import views

urlpatterns = [
    path('api/gallery', views.api_gallery_view, name='api_gallery'),
    path('healthz', views.healthz, name='healthz'),
    path('about/', views.about_view, name='about'),
    # One bio link per platform, each showing only the posts ticked for it.
    re_path(r'^ig/?$', views.feed_view, {'platform': 'instagram'}, name='feed_instagram'),
    re_path(r'^tt/?$', views.feed_view, {'platform': 'tiktok'}, name='feed_tiktok'),
    re_path(r'^yt/?$', views.feed_view, {'platform': 'youtube'}, name='feed_youtube'),
    path('', views.feed_view, name='feed'),
]
