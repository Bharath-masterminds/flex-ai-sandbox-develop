import datetime
import jwt
import logging

from fx_ai_reusables.authenticators.constants import JWT_VERIFY_SIGNATURE
from fx_ai_reusables.authenticators.hcp.interfaces.hcp_authenticator_interface import IHcpAuthenticator


class HcpAuthenticatorCacheAsideDecorator(IHcpAuthenticator):
    """Cache Aside Decorator for Hcp-Token.

    Token is stored as a member-variable.
    If member-variable is None, generate token.
    If member-variable is not None, check the expires_on against "now".
    If "expires_on" does not exist, right now, code returns the cached-token.  This may cause an issue.

    """

    def __init__(self, inner_item_to_decorate: IHcpAuthenticator):
        self._inner_item_to_decorate = inner_item_to_decorate
        self.cached_token = None

    async def flush_cache_aside(self):
        logging.info("HcpAuthenticatorCacheAsideDecorator:flush_cache_aside (set to None)")
        self.cached_token = None

    async def get_hcp_token(self) -> str:
        logging.info("inner_item_to_decorate get_hcp_token being called")

        if self.cached_token is not None:

            # Decode the token (without verifying signature, if you don't have the key)
            decoded = jwt.decode(self.cached_token, options={"verify_signature": JWT_VERIFY_SIGNATURE})

            # Extract and convert the expiration time
            exp_timestamp = decoded.get("exp")
            if exp_timestamp:
                exp_datetime = datetime.datetime.utcfromtimestamp(exp_timestamp)
                print("Token expires on:", exp_datetime)

                # Get current UTC time
                now = datetime.datetime.utcnow()

                # Compare
                if exp_datetime < now:
                    logging.info("Token has expired. Setting member variable to None")
                    self.cached_token = None
                else:
                    print("Token is still valid. Let us keep using it")

            else:
                logging.info("No expiration claim found in token.  This is ambiguous.  Right now, do not None-i-fy the member variable.")


        if self.cached_token is None:
            logging.info("cached_token is NONE, getting a new token")
            self.cached_token = await self._inner_item_to_decorate.get_hcp_token()

        return self.cached_token