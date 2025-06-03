from rest_framework import status
from rest_framework.response import Response
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from .serializers import UserSerializer
from .models import User
from drf_yasg.utils import swagger_auto_schema
from .utils import send_otp_mail

class UserRegistrationView(GenericAPIView):
    @swagger_auto_schema(
        request_body=UserSerializer.RegistrationSerializer,
        responses={201: 'User registered successfully', 400: 'Bad Request'},
        operation_description="Register a new user.",
        tags=['account']
    )
    def post(self, request):
        serializer = UserSerializer.RegistrationSerializer(data=request.data)
        if serializer.is_valid(raise_exception=True):
            user = serializer.save()
            
            send_otp_mail(user.email)
            return Response({'user': UserSerializer.Retrieve(user).data}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class VerifyUserView(GenericAPIView):
    @swagger_auto_schema(
        request_body=UserSerializer.VerifyOtpSerializer,
        responses={200: 'User verified successfully', 400: 'Bad Request'},
        operation_description="Verify a user.",
        tags=['account']
    )
    def post(self, request):
        serializer = UserSerializer.VerifyOtpSerializer(data=request.data)

        if serializer.is_valid(raise_exception=True):
            user = serializer.validated_data
            user.is_verified = True
            user.save()
            return Response({'message': 'User verified successfully.', 'user': UserSerializer.Retrieve(user).data}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class ResendOtpView(GenericAPIView):
    @swagger_auto_schema(
        request_body=UserSerializer.ResendOtpSerializer,
        responses={200: 'OTP sent successfully', 400: 'Bad Request'},
        operation_description="Resend OTP for verification.",
        tags=['account']
    )
    def post(self, request):
        serializer = UserSerializer.ResendOtpSerializer(data=request.data)
        
        if serializer.is_valid(raise_exception=True):
            user = serializer.validated_data
            send_otp_mail(user.email)
            return Response({'message': 'OTP sent successfully.'}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class UserLoginView(GenericAPIView):
    @swagger_auto_schema(
        request_body=UserSerializer.LoginSerializer,
        responses={200: 'Login successful', 400: 'Bad Request'},
        operation_description="Login an existing user.",
        tags=['account']
    )
    def post(self, request):
        serializer = UserSerializer.LoginSerializer(data=request.data, context={'request': request})
        if serializer.is_valid(raise_exception=True):
            data = serializer.validated_data
            user = User.objects.get(id=data['id'])
            user_data = UserSerializer.Retrieve(user).data
            return Response({'access_token': data.access_token,
                             'refresh_token': data.refresh_token,
                             "user_data": user_data }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class UserView(GenericAPIView):
    @swagger_auto_schema(
        responses={200: 'User retrieved successfully', 400: 'Bad Request'},
        operation_description="Get a user.",
        tags=['account']
    )
    def get(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({'error': 'User does not exist.'}, status=status.HTTP_404_NOT_FOUND)
        return Response({'user': UserSerializer.Retrieve(user).data}, status=status.HTTP_200_OK)
    
class UserUpdateView(GenericAPIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        request_body=UserSerializer.UpdateSerializer,
        responses={200: 'User updated successfully', 400: 'Bad Request'},
        operation_description="Update a user.",
        tags=['account']
    )
    def put(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({'error': 'User does not exist.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = UserSerializer.UpdateSerializer(user, data=request.data, partial=True)
        if serializer.is_valid(raise_exception=True):
            user = serializer.save()
            return Response({'user': UserSerializer.Retrieve(user).data}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    