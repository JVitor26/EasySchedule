import logging

from .request_context import get_request_id


class RequestContextFilter(logging.Filter):
    def filter(self, record):
        record.request_id = get_request_id()
        return True
