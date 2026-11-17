"""Vercel entrypoint for LeadFinder.

The local app (``python server.py``) stays dependency-free. On Vercel, this
thin Flask wrapper routes requests through the same ``server.dispatch`` logic
used by the standard-library HTTP server.
"""
import json
import os

from flask import Flask, Response, request

import server

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = server.MAX_REQUEST_BYTES


@app.route("/", defaults={"path": ""}, methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
@app.route("/<path:path>", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
def vercel_handler(path):
    path_with_query = request.full_path
    if path_with_query.endswith("?"):
        path_with_query = path_with_query[:-1]

    code, body, ctype = server.dispatch(
        request.method,
        path_with_query,
        request.get_data(),
        serverless=True,
    )
    if isinstance(body, (dict, list)):
        body = json.dumps(body)
    return Response(body, status=code, content_type=ctype)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
