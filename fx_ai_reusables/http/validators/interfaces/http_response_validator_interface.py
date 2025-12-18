import httpx


# Response validator
class IHttpResponseValidator:
    def validate_http_response(self, response: httpx.Response):
        pass

