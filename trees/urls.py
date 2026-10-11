from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from . import views_additional

urlpatterns = [
    path('api/status/', views.system_status, name='system_status'),
    path('api/newsletter/subscribe/', views.newsletter_subscribe, name='newsletter_subscribe'),
    path(
        'newsletter/unsubscribe/<uuid:token>/',
        views.newsletter_unsubscribe,
        name='newsletter_unsubscribe',
    ),
    path('', views.landing, name='home'),
    path('community/', views.tree_list, name='tree_list'),
    path('discover/', views.discover, name='discover'),
    path('search/', views.search, name='search'),
    path('achievements/', views.achievements, name='achievements'),
    path('leaderboard/', views.leaderboard, name='leaderboard'),
    path('insights/', views.garden_insights, name='garden_insights'),
    path('challenges/', views.daily_challenges, name='daily_challenges'),
    path('api/cron/daily-engagement/', views.daily_engagement_cron, name='daily_engagement_cron'),
    path(
        'challenges/<int:challenge_id>/complete/',
        views.complete_daily_challenge,
        name='complete_daily_challenge',
    ),
    path('offline/', views.offline_page, name='offline'),
    path('signup/', views.signup_step1, name='signup_step1'),
    path('signup/create/', views.signup_step2, name='signup_step2'),
    path('onboarding/', views.onboarding, name='onboarding'),
    path('ajax/username-available/', views.username_available, name='username_available'),
    path(
        'password-reset/',
        auth_views.PasswordResetView.as_view(
            template_name='registration/password_reset_form.html',
            email_template_name='registration/password_reset_email.html',
            subject_template_name='registration/password_reset_subject.txt',
        ),
        name='password_reset',
    ),
    path(
        'password-reset/done/',
        auth_views.PasswordResetDoneView.as_view(
            template_name='registration/password_reset_done.html',
        ),
        name='password_reset_done',
    ),
    path(
        'reset/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='registration/password_reset_confirm.html',
        ),
        name='password_reset_confirm',
    ),
    path(
        'reset/done/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='registration/password_reset_complete.html',
        ),
        name='password_reset_complete',
    ),
    path('settings/password/', views.change_password, name='change_password'),
    path('notifications/', views.notification_center, name='notifications'),
    path('notifications/read-all/', views.mark_notifications_read, name='mark_notifications_read'),
    path('u/<str:username>/follow/', views.toggle_follow, name='toggle_follow'),
    path('u/<str:username>/<str:relation>/', views.follow_list, name='follow_list'),
    path('u/<str:username>/', views.user_profile, name='user_profile'),
    path('<int:pk>/', views.tree_detail, name='tree_detail'),
    path('add/', views.add_tree, name='add_tree'),
    path('ajax/identify-species/', views.identify_tree_species, name='identify_tree_species'),
    path('<int:pk>/analyze-health/', views.analyze_tree, name='analyze_tree'),
    path('task/<int:task_id>/complete/', views.mark_task_completed, name='mark_task_completed'),
    path('<int:pk>/add_health_log/', views_additional.add_health_log, name='add_health_log'),
    path('<int:pk>/add_task/', views_additional.add_task, name='add_task'),
    path('profile/', views.profile_view, name='profile'),
    path('pledges/<int:pledge_id>/status/', views.update_pledge_status, name='update_pledge_status'),
    path('ajax/react_or_comment/', views.react_or_comment, name='react_or_comment'),
    path('logout/', views.user_logout, name='logout'),
    path('login/', views.user_login, name='login'),
    path('register/', views.register, name='register'),
    path('ajax/delete_tree/<int:pk>/', views.delete_tree, name='delete_tree'),
]
