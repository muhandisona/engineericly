"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.views.decorators.cache import cache_control
from django.views.static import serve

urlpatterns = [
    path('admin/', admin.site.urls),
    # Uploaded covers. Served by Django so the container works on its own behind any
    # proxy; every upload gets a unique name, so browsers may cache them for a week.
    re_path(
        r'^media/(?P<path>.*)$',
        cache_control(public=True, max_age=60 * 60 * 24 * 7)(serve),
        {'document_root': settings.MEDIA_ROOT},
    ),
    path('', include('products.urls')),
]