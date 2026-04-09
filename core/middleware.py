import logging
import time
import uuid

from .request_context import reset_request_id, set_request_id

logger = logging.getLogger("core.request")


class RequestContextMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        incoming_request_id = request.headers.get("X-Request-ID", "").strip()
        request_id = incoming_request_id or uuid.uuid4().hex

        token = set_request_id(request_id)
        request.request_id = request_id
        started_at = time.perf_counter()
        response = None

        try:
            response = self.get_response(request)
            response["X-Request-ID"] = request_id
            return response
        finally:
            duration_ms = (time.perf_counter() - started_at) * 1000
            status_code = getattr(response, "status_code", 500)
            logger.info(
                "%s %s %s %.2fms",
                request.method,
                request.path,
                status_code,
                duration_ms,
            )
            reset_request_id(token)
