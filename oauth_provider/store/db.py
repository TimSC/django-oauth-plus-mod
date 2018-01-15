import oauth10a as oauth

from django.conf import settings
from oauth_provider.compat import now

from oauth_provider.store import InvalidConsumerError, InvalidTokenError, Store
from oauth_provider.models import Nonce, Token, Consumer, Scope, VERIFIER_SIZE

NONCE_VALID_PERIOD = getattr(settings, "OAUTH_NONCE_VALID_PERIOD", None)

class ModelStore(Store):
    """
    Store implementation using the Django models defined in `piston.models`.
    """
    def get_consumer(self, request, oauth_request, consumer_key):
        try:
            return Consumer.objects.get(key=consumer_key)
        except Consumer.DoesNotExist:
            raise InvalidConsumerError()

    def get_consumer_for_request_token(self, request, oauth_request, request_token):
        return request_token.consumer

    def get_consumer_for_access_token(self, request, oauth_request, access_token):
        return access_token.consumer

    def create_request_token(self, request, oauth_request, consumer, callback):
        try:
            scope = Scope.objects.get(name=oauth_request.get_parameter('scope'))
        except oauth.Error:
            # oauth.Error means that scope wasn't specified
            scope = None
        except Scope.DoesNotExist:
            # Scope.DoesNotExist means that specified scope doesn't exist in db
            raise oauth.Error('Scope does not exist.')
        
        token = Token.objects.create_token(
            token_type=Token.REQUEST,
            consumer=Consumer.objects.get(key=oauth_request['oauth_consumer_key']),
            timestamp=oauth_request['oauth_timestamp'],
            scope=scope,
        )
        token.set_callback(callback)
        token.save()

        return token

    def get_request_token(self, request, oauth_request, request_token_key):
        try:
            return Token.objects.get(key=request_token_key, token_type=Token.REQUEST)
        except Token.DoesNotExist:
            raise InvalidTokenError()

    def authorize_request_token(self, request, oauth_request, request_token):
        request_token.is_approved = True
        request_token.user = request.user
        request_token.verifier = oauth.generate_verifier(VERIFIER_SIZE)
        request_token.save()
        return request_token

    def create_access_token(self, request, oauth_request, consumer, request_token):
        scope = request_token.scope
        token_user = request_token.user
        request_token.delete()
        access_token = Token.objects.create_token(
            token_type=Token.ACCESS,
            timestamp=oauth_request['oauth_timestamp'],
            consumer=Consumer.objects.get(key=consumer.key),
            user=token_user,
            scope=scope,
        )
        return access_token

    def get_access_token(self, request, oauth_request, consumer, access_token_key):
        try:
            return Token.objects.get(key=access_token_key, token_type=Token.ACCESS)
        except Token.DoesNotExist:
            raise InvalidTokenError()

    def get_user_for_access_token(self, request, oauth_request, access_token):
        return access_token.user

    def get_user_for_consumer(self, request, oauth_request, consumer):
        return consumer.user

    def check_nonce(self, request, oauth_request, nonce, timestamp=0):
        timestamp = int(timestamp)

        if NONCE_VALID_PERIOD and int(now().strftime("%s")) - timestamp > NONCE_VALID_PERIOD:
            return False

        nonce, created = Nonce.objects.get_or_create(
            consumer_key=oauth_request['oauth_consumer_key'],
            token_key=oauth_request.get('oauth_token', ''),
            key=nonce, timestamp=timestamp,
        )
        return created
