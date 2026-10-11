from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from django.views.decorators.cache import never_cache


urlpatterns = [
    path('admin/', admin.site.urls),
    path("service-worker.js", never_cache(TemplateView.as_view(
        template_name="service-worker.js",
        content_type="application/javascript",
        extra_context={},
    )), name="service_worker"),
    path("i18n/", include("django.conf.urls.i18n")),
    path("grove/", include(("grove.urls", "grove"), namespace="grove")),
    path("grove/", include("grove_finance.urls")),
    path("grove/", include("grove_carbon.urls")),
    path("grove/", include("grove_compliance.urls")),
    path("market/", include("grove_market.urls")),
    path('', include('trees.urls')),
]


urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
#testing commit