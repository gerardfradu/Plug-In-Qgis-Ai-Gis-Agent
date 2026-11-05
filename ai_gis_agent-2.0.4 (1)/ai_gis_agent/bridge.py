import json
import socket
import threading

from qgis.PyQt.QtCore import QObject, pyqtSignal

from .commands import CommandDispatcher


class QGISCommandServer(QObject):
    request_signal = pyqtSignal(object, object)

    def __init__(self, iface, host="127.0.0.1", port=8765):
        super().__init__()
        self.iface = iface
        self.host = host
        self.port = port
        self.sock = None
        self.is_running = False
        self.dispatcher = CommandDispatcher(iface)
        self.request_signal.connect(self.handle_request)

    def start(self):
        if self.is_running:
            return

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((self.host, self.port))
        self.sock.listen(16)
        self.sock.settimeout(1.0)
        self.is_running = True

        threading.Thread(target=self.accept_loop, daemon=True, name="AIGisAccept").start()

    def stop(self):
        self.is_running = False
        if self.sock:
            try:
                self.sock.close()
            except OSError:
                pass
            self.sock = None

    def accept_loop(self):
        while self.is_running:
            try:
                conn, _ = self.sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break

            threading.Thread(
                target=self.client,
                args=(conn,),
                daemon=True,
                name="AIGisClient",
            ).start()

    def client(self, conn):
        request_id = None
        try:
            # The MCP client half-closes its write side after sending one JSON
            # request. Reading until EOF avoids the old single-recv TCP bug.
            chunks = []
            while True:
                chunk = conn.recv(65536)
                if not chunk:
                    break
                chunks.append(chunk)

            if not chunks:
                raise ValueError("Solicitud vacía")

            req = json.loads(b"".join(chunks).decode("utf-8"))
            request_id = req.get("id")
            self.request_signal.emit(req, conn)

        except Exception as exc:
            self.send(
                conn,
                {
                    "id": request_id,
                    "ok": False,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                },
            )
            try:
                conn.close()
            except OSError:
                pass

    def handle_request(self, req, conn):
        request_id = req.get("id")
        try:
            command = req.get("command")
            if not command:
                raise ValueError("Falta 'command'")

            result = self.dispatcher.dispatch(command, req.get("params") or {})
            response = {"id": request_id, "ok": True, "result": result}

        except Exception as exc:
            response = {
                "id": request_id,
                "ok": False,
                "error": str(exc),
                "error_type": type(exc).__name__,
            }

        self.send(conn, response)
        try:
            conn.close()
        except OSError:
            pass

    @staticmethod
    def send(conn, obj):
        payload = json.dumps(
            obj,
            ensure_ascii=False,
            default=str,
            separators=(",", ":"),
        ).encode("utf-8")
        conn.sendall(payload)
