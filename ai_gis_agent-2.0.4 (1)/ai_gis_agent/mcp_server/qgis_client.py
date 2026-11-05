import json
import socket
import time
import uuid


class QGISClient:
    def __init__(self, host="127.0.0.1", port=8765, timeout=60):
        self.host = host
        self.port = port
        self.timeout = timeout

    def call(self, command, params=None):
        request = {
            "id": str(uuid.uuid4()),
            "command": command,
            "params": params or {},
        }
        data = json.dumps(
            request,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")

        deadline = time.monotonic() + self.timeout

        try:
            with socket.create_connection(
                (self.host, self.port),
                timeout=max(1, self.timeout),
            ) as sock:
                sock.settimeout(max(1, int(deadline - time.monotonic())))
                sock.sendall(data)
                sock.shutdown(socket.SHUT_WR)

                chunks = []
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError("Tiempo de espera agotado esperando a QGIS")
                    sock.settimeout(remaining)
                    chunk = sock.recv(65536)
                    if not chunk:
                        break
                    chunks.append(chunk)

        except ConnectionRefusedError as exc:
            raise RuntimeError(
                "No se puede conectar con QGIS. "
                "Comprueba que el plugin AI GIS AGENT esté activado y escuchando en "
                "127.0.0.1:8765."
            ) from exc

        if not chunks:
            raise RuntimeError("QGIS no devolvió respuesta")

        response = json.loads(b"".join(chunks).decode("utf-8"))

        if not response.get("ok"):
            error = response.get("error", "Error desconocido en QGIS")
            error_type = response.get("error_type")
            prefix = f"{error_type}: " if error_type else ""
            raise RuntimeError(prefix + error)

        return response.get("result")
