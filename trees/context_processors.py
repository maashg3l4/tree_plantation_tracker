def mobile_navigation(request):
    unread_notifications = 0
    if request.user.is_authenticated:
        unread_notifications = request.user.notifications.filter(is_read=False).count()
    return {"mobile_unread_notifications": unread_notifications}
