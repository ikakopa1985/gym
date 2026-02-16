from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from gymapp import views as gym_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("gymapp.urls"))
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


