"""One place that turns exceptions into JSON error responses."""

from __future__ import annotations

import logging

from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException

from ..domain.errors import AppError

logger = logging.getLogger(__name__)


def _wants_json() -> bool:
    return request.path.startswith(("/api/", "/auth/"))


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(AppError)
    def handle_app_error(err: AppError):
        body = {"error": err.message, "code": err.code}
        if err.details:
            body["details"] = err.details
        return jsonify(body), err.status_code

    @app.errorhandler(HTTPException)
    def handle_http_error(err: HTTPException):
        if not _wants_json():
            return err
        return jsonify({"error": err.description or err.name, "code": err.name.lower().replace(" ", "_")}), err.code

    @app.errorhandler(Exception)
    def handle_unexpected(err: Exception):
        logger.exception("Unhandled error on %s %s", request.method, request.path)
        if not _wants_json():
            raise err
        return jsonify({"error": "Internal server error.", "code": "internal_error"}), 500
