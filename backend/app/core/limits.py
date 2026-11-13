"""Reject oversized upload requests from Content-Length before the body is read.

FastAPI parses multipart bodies before the route runs, so this is the only place to stop a
huge upload early. Chunked requests without Content-Length are still capped by the
per-file check in app.services.uploads.
"""

from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.errors import error_response

MULTIPART_OVERHEAD = 64 * 1024


class UploadSizeLimitMiddleware:
    def __init__(self, app: ASGIApp, *, path: str, max_bytes: int) -> None:
        self.app = app
        self.path = path
        self.limit = max_bytes + MULTIPART_OVERHEAD
        self.max_mb = max_bytes // (1024 * 1024)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["method"] == "POST" and scope["path"] == self.path:
            for name, value in scope["headers"]:
                if name == b"content-length":
                    if value.isdigit() and int(value) > self.limit:
                        response = error_response(
                            413,
                            "file_too_large",
                            f"File is larger than the {self.max_mb} MB limit.",
                        )
                        await response(scope, receive, send)
                        return
                    break
        await self.app(scope, receive, send)
