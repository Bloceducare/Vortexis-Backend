from rest_framework.viewsets import ViewSet
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from .serializer import GoogleSocialAuthSerializer, GithubSocialAuthSerializer

# Create your views here.

class GoogleSocialAuthView(ViewSet):

    @swagger_auto_schema(
        request_body=GoogleSocialAuthSerializer,
        responses={200: 'User authenticated successfully', 400: 'Bad Request'},
        operation_description="Authenticate user with google.",
        tags=['social_auth']
        )
    def create(self, request):
        serializer = GoogleSocialAuthSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data.get('access_token'), status=status.HTTP_200_OK)
    
class GithubSocialAuthView(ViewSet):

    @swagger_auto_schema(
            request_body=GithubSocialAuthSerializer,
            responses={200: 'User authenticated successfully', 400: 'Bad Request'},
            operation_description="Authenticate user with github.",
            tags=['social_auth']
            )
    def create(self, request):
        serializer = GithubSocialAuthSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer._validated_data['code'], status=status.HTTP_200_OK)