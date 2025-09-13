from urllib.parse import parse_qs
from asgiref.sync import sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.authentication import JWTAuthentication


class JWTAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        scope['user'] = scope.get('user') or AnonymousUser()

        token = None
        query_string = scope.get('query_string', b'').decode()
        if query_string:
            qs = parse_qs(query_string)
            if 'token' in qs and len(qs['token']) > 0:
                token = qs['token'][0]

        if not token:
            for header_name, header_val in scope.get('headers', []):
                if header_name == b'authorization':
                    val = header_val.decode()
                    if val.lower().startswith('bearer '):
                        token = val.split(' ', 1)[1].strip()
                    break

        if token:
            try:
                auth = JWTAuthentication()
                validated = await sync_to_async(auth.get_validated_token)(token)
                user = await sync_to_async(auth.get_user)(validated)
                scope['user'] = user
            except Exception:
                pass

        return await super().__call__(scope, receive, send)


def JWTAuthMiddlewareStack(inner):
    return JWTAuthMiddleware(inner)

 