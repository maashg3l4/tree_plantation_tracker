from django.urls import path
from . import views
from . import views_additional

urlpatterns = [
    path('', views.tree_list, name='tree_list'),
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
    #testing
    
]
