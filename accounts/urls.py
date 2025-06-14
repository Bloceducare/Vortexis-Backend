from django.urls import path
from .views import (
    UserRegistrationView,
    UserLoginView,
    VerifyUserView,
    ResendOtpView,
    UserRetrieveView,
    UserUpdateView,
    UserDeleteView,
    ProfileCreateView,
    ProfileRetrieveView,
    ProfileUpdateView,
    ProfileDeleteView
)

urlpatterns = [
    path('register/', UserRegistrationView.as_view(), name='register'),
    path('login/', UserLoginView.as_view(), name='login'),
    path('verify/', VerifyUserView.as_view(), name='verify'),
    path('resend-otp/', ResendOtpView.as_view(), name='resend_otp'),
    path('users/<int:user_id>/', UserRetrieveView.as_view(), name='user_retrieve'),
    path('users/<int:user_id>/update/', UserUpdateView.as_view(), name='user_update'),
    path('users/<int:user_id>/delete/', UserDeleteView.as_view(), name='user_delete'),
    path('profiles/create/', ProfileCreateView.as_view(), name='profile_create'),
    path('profiles/<int:user_id>/', ProfileRetrieveView.as_view(), name='profile_retrieve'),
    path('profiles/<int:user_id>/update/', ProfileUpdateView.as_view(), name='profile_update'),
    path('profiles/<int:user_id>/delete/', ProfileDeleteView.as_view(), name='profile_delete'),
]