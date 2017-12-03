import oauth2 as oauth

try:
    from functools import update_wrapper
except ImportError:
    from django.utils.functional import update_wrapper  # Python 2.3, 2.4 fallback.

from django.utils.translation import ugettext as _

from responses import INVALID_PARAMS_RESPONSE, INVALID_CONSUMER_RESPONSE, COULD_NOT_VERIFY_OAUTH_REQUEST_RESPONSE, INVALID_SCOPE_RESPONSE
from utils import initialize_server_request, send_oauth_error, get_oauth_request, verify_oauth_request
from consts import OAUTH_PARAMETERS_NAMES
from store import store, InvalidTokenError, InvalidConsumerError
from functools import wraps

def DoOAuthCheck(request, scope_name, *args, **kwargs):
    oauth_request = get_oauth_request(request)
    if oauth_request is None:
        return False, INVALID_PARAMS_RESPONSE, None

    try:
        consumer = store.get_consumer(request, oauth_request, oauth_request['oauth_consumer_key'])
    except InvalidConsumerError:
        return False, INVALID_CONSUMER_RESPONSE, None

    try:
        token = store.get_access_token(request, oauth_request, consumer, oauth_request.get_parameter('oauth_token'))
    except InvalidTokenError:
        return False, send_oauth_error(oauth.Error(_('Invalid access token: %s') % oauth_request.get_parameter('oauth_token'))), None

    if not verify_oauth_request(request, oauth_request, consumer, token):
        return False, COULD_NOT_VERIFY_OAUTH_REQUEST_RESPONSE, None

    if bool(scope_name) and (not token.scope
                            or token.scope.name != scope_name):
        return False, INVALID_SCOPE_RESPONSE, None

    return True, None, token.user

class CheckOauth(object):
    """
    Decorator that checks that the OAuth parameters passes the given test, raising
    an OAuth error otherwise. If the test is passed, the view function
    is invoked.

    We use a class here so that we can define __get__. This way, when a
    CheckOAuth object is used as a method decorator, the view function
    is properly bound to its instance.
    """
    def __init__(self, scope_name=None):
        self.scope_name = scope_name

    def __new__(cls, arg=None):
        if not callable(arg):
            return super(CheckOauth, cls).__new__(cls)
        else:
            obj =  super(CheckOauth, cls).__new__(cls)
            obj.__init__()
            return obj(arg)

    def __call__(self, view_func):

        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            ok, err_view, token_user = DoOAuthCheck(request, self.scope_name, *args, **kwargs)
            if not ok:
                return err_view
            if token_user:
                request.user = token_user
            return view_func(request, *args, **kwargs)

        return wrapped_view


oauth_required = CheckOauth
