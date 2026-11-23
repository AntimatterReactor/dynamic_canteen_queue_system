"""
Konfigurasi dan protokol bersama untuk server, pelanggan, dan dapur.

Protokol: TCP, setiap pesan 1 objek JSON per baris.
"""
import json
import os
import socket
import threading
from typing import Any

HOST = "127.0.0.1"
PORT = 5050

MERCHANT = "PT SIANTURI BERKAH ABADI"

MENU: dict[str, int] = {
    "geprek": 16_000,
    "sate": 18_000,
    "batagor": 13_000,
    "telor": 13_000,
    "es teh manis": 7_000,
    "air mineral": 5_000,
}

# status pesanan
MENUNGGU = "menunggu"
DIPROSES = "diproses"

Message = dict[str, Any]  # satu pesan JSON, selalu punya kunci "type"


class Connection:
    """bungkus utk socket, kirim/terima pesan JSON per baris. thread-safe."""

    def __init__(self, sock: socket.socket) -> None:
        self.sock = sock
        self._reader = sock.makefile("r", encoding="utf-8", newline="\n")
        self._send_lock = threading.Lock()
        self.closed = False

    @classmethod
    def connect(cls, host: str = HOST, port: int = PORT) -> "Connection":
        return cls(socket.create_connection((host, port)))

    def send(self, msg_type: str, **data: Any) -> bool:
        """kirim satu pesan. return False jika koneksi sudah putus."""
        line = json.dumps({"type": msg_type, **data}) + "\n"
        with self._send_lock:
            try:
                self.sock.sendall(line.encode("utf-8"))
                return True
            except OSError:
                self.closed = True
                return False

    def recv(self) -> Message | None:
        """terima satu pesan (dict). return None jika koneksi ditutup."""
        try:
            line = self._reader.readline()
        except (OSError, ValueError):
            line = ""
        if not line:
            self.closed = True
            return None
        try:
            msg: Message = json.loads(line)
            return msg
        except json.JSONDecodeError:
            return {"type": "invalid"}

    def close(self) -> None:
        self.closed = True
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.sock.close()


def rupiah(n: int) -> str:
    return f"Rp{n:,}".replace(",", ".")


def clear_screen() -> None:
    print("\033[2J\033[H", end="", flush=True)


def set_title(title: str) -> None:
    os.system("")  # antisipasi cmd (aktifkan ANSI di Windows)
    print(f"\033]0;{title}\007", end="", flush=True)
