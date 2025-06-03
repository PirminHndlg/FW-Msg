from . import views
from django.urls import path, include

urlpatterns = [
    path('', views.index, name='index_home'),
    path('index', views.index, name='index'),
    path('login/<str:token>', views.token_login, name='token_login'),
    path('first_login', views.first_login, name='first_login'),
    path('first_login/<str:username>/<str:einmalpasswort>', views.first_login, name='first_login_with_params'),
    path('first_login/<str:username>', views.first_login, name='first_login_with_username'),
    path('password_reset', views.password_reset, name='password_reset'),
    path('maintenance', views.maintenance, name='maintenance'),
]
