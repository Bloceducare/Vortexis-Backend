from django.urls import path
from .views import UserRegistrationView, UserLoginView, VerifyUserView, ResendOtpView, UserView

urlpatterns = [
    path('register', UserRegistrationView.as_view(), name='register'),
    path('login', UserLoginView.as_view(), name='login'),
    path('verify', VerifyUserView.as_view(), name='verify'),
    path('resend_otp', ResendOtpView.as_view(), name='resend_otp'),
    path('<int:user_id>', UserView.as_view(), name='user'),
]