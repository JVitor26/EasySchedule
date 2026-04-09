from contextvars import ContextVar

REQUEST_ID = ContextVar("request_id", default="-")


def set_request_id(request_id):
    return REQUEST_ID.set(request_id)


def get_request_id():
    return REQUEST_ID.get()


def reset_request_id(token):
    REQUEST_ID.reset(token)
