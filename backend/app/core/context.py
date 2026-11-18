from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar("request_id", default="system")


def current_request_id() -> str:
    return request_id_var.get()
