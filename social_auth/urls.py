from django.urls import path
from . import views

urlpatterns = [
    path('google', views.GoogleSocialAuthView.as_view({'post': 'create'}), name='google'),
    path('github', views.GithubSocialAuthView.as_view({'post': 'create'}), name='github')
]