import hmac
import os
import re

import docker
from flask import Flask, jsonify, request


app = Flask(__name__)
client = docker.from_env()
CONTROL_API_TOKEN = os.getenv("CONTROL_API_TOKEN", "change-control-token")
ROIP_NETWORK = os.getenv("ROIP_DOCKER_NETWORK", "mumbledocker_roip-net")
MUMBLE_IMAGE = os.getenv("MUMBLE_IMAGE", "mumblevoip/mumble-server:v1.5.915-1")
CONTAINER_RE = re.compile(r"^roip-mumble[1-9][0-9]*$")


@app.errorhandler(docker.errors.DockerException)
def handle_docker_error(exc):
    return jsonify({"status": "error", "error": str(exc)}), 503


@app.before_request
def authenticate_control_request():
    if request.path == "/healthz":
        return None
    supplied = request.headers.get("Authorization", "")
    expected = f"Bearer {CONTROL_API_TOKEN}"
    if not hmac.compare_digest(supplied, expected):
        return jsonify({"status": "error", "error": "unauthorized"}), 401


@app.route("/healthz")
def healthz():
    try:
        client.ping()
        return jsonify({"status": "ok", "docker": "ok"})
    except Exception as exc:
        return jsonify({"status": "degraded", "docker": str(exc)}), 503


def _container_name(value):
    name = str(value or "").strip()
    if not CONTAINER_RE.fullmatch(name):
        raise ValueError("invalid managed container name")
    return name


@app.route("/containers/inventory", methods=["POST"])
def inventory():
    containers = []
    for container in client.containers.list(all=True):
        if container.name.startswith("roip-mumble"):
            containers.append({
                "id": container.short_id,
                "name": container.name,
                "status": container.status,
                "managed": container.labels.get("roip.managed") == "true",
                "station_id": container.labels.get("roip.station_id"),
            })
    return jsonify({"status": "success", "containers": containers})


@app.route("/containers/create", methods=["POST"])
def create_container():
    data = request.get_json(silent=True) or {}
    try:
        station_id = int(data["station_id"])
        name = _container_name(data["container_name"])
        host_port = int(data["host_port"])
        host_ice_port = int(data["host_ice_port"])
        ice_secret = str(data["ice_secret"])
    except (KeyError, TypeError, ValueError) as exc:
        return jsonify({"status": "error", "error": str(exc)}), 400
    if station_id < 1 or not (1024 <= host_port <= 65535) or not (1024 <= host_ice_port <= 65535):
        return jsonify({"status": "error", "error": "invalid station or port"}), 400
    if len(ice_secret) < 8:
        return jsonify({"status": "error", "error": "ICE secret must be at least 8 characters"}), 400

    try:
        existing = client.containers.get(name)
        return jsonify({"status": "error", "error": f"container {existing.name} already exists"}), 409
    except docker.errors.NotFound:
        pass

    volume_name = f"roip-mumble-{station_id}-data"
    client.volumes.create(
        name=volume_name,
        labels={"roip.managed": "true", "roip.station_id": str(station_id)},
    )
    try:
        container = client.containers.run(
            image=MUMBLE_IMAGE,
            name=name,
            hostname=name,
            detach=True,
            ports={
                "64738/tcp": host_port,
                "64738/udp": host_port,
                "6502/tcp": host_ice_port,
            },
            environment={
                "MUMBLE_CONFIG_ICE": "tcp -h 0.0.0.0 -p 6502",
                "MUMBLE_CONFIG_ICESECRETWRITE": ice_secret,
                "MUMBLE_CONFIG_ICESECRETREAD": ice_secret,
            },
            labels={
                "roip.managed": "true",
                "roip.station_id": str(station_id),
                "roip.data_volume": volume_name,
            },
            volumes={volume_name: {"bind": "/data", "mode": "rw"}},
            network=ROIP_NETWORK,
            restart_policy={"Name": "unless-stopped"},
            mem_limit=os.getenv("MUMBLE_MEMORY_LIMIT", "512m"),
            nano_cpus=int(float(os.getenv("MUMBLE_CPU_LIMIT", "1.0")) * 1_000_000_000),
            pids_limit=256,
        )
    except Exception:
        # Keep the named volume for diagnosis/retry; it is harmless and recoverable.
        raise
    return jsonify({
        "status": "success",
        "container": {"id": container.short_id, "name": name, "volume": volume_name},
    }), 201


@app.route("/containers/delete", methods=["POST"])
def delete_container():
    data = request.get_json(silent=True) or {}
    try:
        name = _container_name(data.get("container_name"))
    except ValueError as exc:
        return jsonify({"status": "error", "error": str(exc)}), 400
    try:
        container = client.containers.get(name)
        if container.labels.get("roip.managed") != "true":
            return jsonify({"status": "error", "error": "container is not managed by ROIP"}), 403
        volume_name = container.labels.get("roip.data_volume")
        container.remove(force=True)
        return jsonify({
            "status": "success",
            "removed": name,
            "retained_volume": volume_name,
        })
    except docker.errors.NotFound:
        return jsonify({"status": "success", "removed": None, "not_found": name})


@app.route("/containers/cleanup", methods=["POST"])
def cleanup_containers():
    data = request.get_json(silent=True) or {}
    try:
        active_names = {
            _container_name(name) for name in data.get("active_names", [])
        }
    except (TypeError, ValueError) as exc:
        return jsonify({"status": "error", "error": str(exc)}), 400
    removed = []
    for container in client.containers.list(all=True, filters={"label": "roip.managed=true"}):
        if container.name.startswith("roip-mumble") and container.name not in active_names:
            removed.append(container.name)
            container.remove(force=True)
    return jsonify({"status": "success", "removed_count": len(removed), "removed": removed})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5100)
