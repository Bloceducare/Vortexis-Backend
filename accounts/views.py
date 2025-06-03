from rest_framework import status
from rest_framework.response import Response
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from drf_yasg.utils import swagger_auto_schema
from .serializers import UserSerializer, ProfileSerializer
from .models import User, Profile
from .utils import send_otp_mail


class UserRegistrationView(GenericAPIView):
    @swagger_auto_schema(
        request_body=UserSerializer.RegistrationSerializer,
        responses={
            201: UserSerializer.RetrieveSerializer,
            400: "Bad Request"
        },
        operation_description="Register a new user and send OTP for verification.",
        tags=['account']
    )
    def post(self, request):
        serializer = UserSerializer.RegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        # Automatically create a Profile for the user
        Profile.objects.get_or_create(user=user)
        send_otp_mail(user.email)
        return Response(
            {"message": "User registered successfully. Please verify your email.", "user": UserSerializer.RetrieveSerializer(user).data},
            status=status.HTTP_201_CREATED
        )


class VerifyUserView(GenericAPIView):
    @swagger_auto_schema(
        request_body=UserSerializer.VerifyOtpSerializer,
        responses={
            200: UserSerializer.RetrieveSerializer,
            400: "Bad Request",
            404: "User not found"
        },
        operation_description="Verify a user with OTP.",
        tags=['account']
    )
    def post(self, request):
        serializer = UserSerializer.VerifyOtpSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data
        if user.is_verified:
            return Response({"message": "User is already verified."}, status=status.HTTP_200_OK)
        user.is_verified = True
        user.save()
        return Response(
            {"message": "User verified successfully.", "user": UserSerializer.RetrieveSerializer(user).data},
            status=status.HTTP_200_OK
        )


class ResendOtpView(GenericAPIView):
    @swagger_auto_schema(
        request_body=UserSerializer.ResendOtpSerializer,
        responses={
            200: "OTP sent successfully",
            400: "Bad Request",
            404: "User not found"
        },
        operation_description="Resend OTP for email verification.",
        tags=['account']
    )
    def post(self, request):
        serializer = UserSerializer.ResendOtpSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data
        if user.is_verified:
            return Response({"message": "User is already verified."}, status=status.HTTP_200_OK)
        send_otp_mail(user.email)
        return Response({"message": "OTP sent successfully."}, status=status.HTTP_200_OK)


class UserLoginView(GenericAPIView):
    @swagger_auto_schema(
        request_body=UserSerializer.LoginSerializer,
        responses={
            200: UserSerializer.LoginSerializer,
            400: "Bad Request",
            401: "Unauthorized"
        },
        operation_description="Log in a user and return tokens.",
        tags=['account']
    )
    def post(self, request):
        serializer = UserSerializer.LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        return Response(
            {
                "message": "Login successful.",
                "access_token": data["access_token"],
                "refresh_token": data["refresh_token"],
                "user": UserSerializer.RetrieveSerializer(User.objects.get(id=data["id"])).data
            },
            status=status.HTTP_200_OK
        )


class UserRetrieveView(GenericAPIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        responses={
            200: UserSerializer.RetrieveSerializer,
            403: "Forbidden",
            404: "User not found"
        },
        operation_description="Retrieve a user's details.",
        tags=['account']
    )
    def get(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
            if request.user.id != user_id and not request.user.is_admin:
                return Response({"error": "You do not have permission to view this user."}, status=status.HTTP_403_FORBIDDEN)
            return Response({"user": UserSerializer.RetrieveSerializer(user).data}, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({"error": "User does not exist."}, status=status.HTTP_404_NOT_FOUND)


class UserUpdateView(GenericAPIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        request_body=UserSerializer.UpdateSerializer,
        responses={
            200: UserSerializer.RetrieveSerializer,
            400: "Bad Request",
            403: "Forbidden",
            404: "User not found"
        },
        operation_description="Update a user's details.",
        tags=['account']
    )
    def put(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
            if request.user.id != user_id and not request.user.is_admin:
                return Response({"error": "You do not have permission to update this user."}, status=status.HTTP_403_FORBIDDEN)
            serializer = UserSerializer.UpdateSerializer(user, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            user = serializer.save()
            return Response({"message": "User updated successfully.", "user": UserSerializer.RetrieveSerializer(user).data}, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({"error": "User does not exist."}, status=status.HTTP_404_NOT_FOUND)


class UserDeleteView(GenericAPIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        responses={
            200: "User deleted successfully",
            403: "Forbidden",
            404: "User not found"
        },
        operation_description="Delete a user account.",
        tags=['account']
    )
    def delete(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
            if request.user.id != user_id and not request.user.is_admin:
                return Response({"error": "You do not have permission to delete this user."}, status=status.HTTP_403_FORBIDDEN)
            serializer = UserSerializer.DeleteSerializer(data={}, context={"user": user})
            serializer.is_valid(raise_exception=True)
            response = serializer.delete(user)
            return Response(response, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({"error": "User does not exist."}, status=status.HTTP_404_NOT_FOUND)


class ProfileCreateView(GenericAPIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        request_body=ProfileSerializer,
        responses={
            201: ProfileSerializer,
            400: "Bad Request",
            403: "Forbidden",
            404: "User not found"
        },
        operation_description="Create or update a user's profile.",
        tags=['profile']
    )
    def post(self, request):
        try:
            profile, created = Profile.objects.get_or_create(user=request.user)
            serializer = ProfileSerializer(profile, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            profile = serializer.save()
            return Response(
                {"message": "Profile created/updated successfully.", "profile": ProfileSerializer(profile).data},
                status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
            )
        except User.DoesNotExist:
            return Response({"error": "User does not exist."}, status=status.HTTP_404_NOT_FOUND)


class ProfileRetrieveView(GenericAPIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        responses={
            200: ProfileSerializer,
            403: "Forbidden",
            404: "Profile not found"
        },
        operation_description="Retrieve a user's profile.",
        tags=['profile']
    )
    def get(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
            if request.user.id != user_id and not request.user.is_admin:
                return Response({"error": "You do not have permission to view this profile."}, status=status.HTTP_403_FORBIDDEN)
            profile = Profile.objects.get(user=user)
            return Response({"profile": ProfileSerializer(profile).data}, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({"error": "User does not exist."}, status=status.HTTP_404_NOT_FOUND)
        except Profile.DoesNotExist:
            return Response({"error": "Profile does not exist."}, status=status.HTTP_404_NOT_FOUND)


class ProfileUpdateView(GenericAPIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        request_body=ProfileSerializer,
        responses={
            200: ProfileSerializer,
            400: "Bad Request",
            403: "Forbidden",
            404: "Profile not found"
        },
        operation_description="Update a user's profile.",
        tags=['profile']
    )
    def put(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
            if request.user.id != user_id and not request.user.is_admin:
                return Response({"error": "You do not have permission to update this profile."}, status=status.HTTP_403_FORBIDDEN)
            profile = Profile.objects.get(user=user)
            serializer = ProfileSerializer(profile, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            profile = serializer.save()
            return Response({"message": "Profile updated successfully.", "profile": ProfileSerializer(profile).data}, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({"error": "User does not exist."}, status=status.HTTP_404_NOT_FOUND)
        except Profile.DoesNotExist:
            return Response({"error": "Profile does not exist."}, status=status.HTTP_404_NOT_FOUND)


class ProfileDeleteView(GenericAPIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        responses={
            200: "Profile deleted successfully",
            403: "Forbidden",
            404: "Profile not found"
        },
        operation_description="Delete a user's profile.",
        tags=['profile']
    )
    def delete(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
            if request.user.id != user_id and not request.user.is_admin:
                return Response({"error": "You do not have permission to delete this profile."}, status=status.HTTP_403_FORBIDDEN)
            profile = Profile.objects.get(user=user)
            profile.delete()
            return Response({"message": "Profile deleted successfully."}, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({"error": "User does not exist."}, status=status.HTTP_404_NOT_FOUND)
        except Profile.DoesNotExist:
            return Response({"error": "Profile does not exist."}, status=status.HTTP_404_NOT_FOUND)