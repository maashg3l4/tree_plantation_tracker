from urllib.parse import urlparse

from django.conf import settings


def mobile_navigation(request):
    unread_notifications = 0
    if request.user.is_authenticated:
        unread_notifications = request.user.notifications.filter(is_read=False).count()
    return {"mobile_unread_notifications": unread_notifications}


def footer_configuration(request):
    urls = {
        name: value
        for name, value in settings.CANOPY_FOOTER_URLS.items()
        if urlparse(value).scheme == "https" and urlparse(value).netloc
    }
    return {
        "canopy_footer_urls": urls,
        "canopy_support_email": settings.CANOPY_SUPPORT_EMAIL,
    }
