#!/usr/bin/env python3
"""
Klien dapur: lihat antrian secara langsung, proses dan selesaikan pesanan.
Hanya satu dapur yang boleh terhubung ke server.
"""
import threading
from typing import Any

from common import *

HELP = "Perintah: [p]roses berikutnya | [s]elesai terdepan | [k]eluar"


class DapurClient:
    def __init__(self) -> None:
        self.conn = Connection.connect()
        self.conn.send("hello", role="dapur")
        self.merchant = ""
        self.orders: list[dict[str, Any]] = []
        self.info = "terhubung ke server"
        self.lock = threading.Lock()
        self.running = True

    # ---------- menerima push dari server (thread terpisah) ----------
    def listen(self) -> None:
        while (msg := self.conn.recv()) is not None:
            with self.lock:
                if msg["type"] == "welcome":
                    self.merchant = msg["merchant"]
                elif msg["type"] == "queue":
                    self.orders = msg["orders"]
                elif msg["type"] in ("info", "error"):
                    self.info = msg["message"]
            self.render()
        if self.running:
            self.running = False
            print("\nKoneksi ke server terputus. Tekan Enter untuk keluar.")

    # ---------- tampilan ----------
    def render(self) -> None:
        with self.lock:
            orders, info = list(self.orders), self.info
        clear_screen()
        print(f"\n===== DAPUR {self.merchant} =====")
        if not orders:
            print("  (antrian kosong)")
        for o in orders:
            items = ", ".join(f"{v}x {k}" for k, v in o["items"].items())
            mark = ">>" if o["status"] == DIPROSES else "  "
            print(f" {mark} #{o['no']:03d} {o['nama']:<16} {o['status']:<9} {o['waktu']}  {items}")
        total = sum(o["total"] for o in orders)
        print(f"\n  {len(orders)} pesanan di antrian, nilai {rupiah(total)}")
        print(f"  Info: {info}")
        print(f"\n{HELP}")
        print("dapur> ", end="", flush=True)

    # ---------- perintah ----------
    def handle_command(self, line: str) -> bool:
        """Jalankan satu perintah. return False jika dapur ingin keluar."""
        cmd = line.strip().lower()
        if cmd in ("p", "proses"):
            self.conn.send("process")
        elif cmd in ("s", "selesai"):
            self.conn.send("done")
        elif cmd in ("k", "keluar", "q"):
            return False
        elif cmd:
            with self.lock:
                self.info = f"perintah '{cmd}' tidak dikenal"
            self.render()
        return True

    def run(self) -> None:
        threading.Thread(target=self.listen, daemon=True).start()
        try:
            while self.running and self.handle_command(input()):
                pass
        except (KeyboardInterrupt, EOFError):
            pass
        finally:
            self.running = False
            self.conn.close()
            print("\nDapur ditutup.")


def main() -> None:
    set_title("Dapur - Dynamic Canteen QUEUE System")
    try:
        client = DapurClient()
    except OSError:
        print(f"Tidak bisa terhubung ke server di {HOST}:{PORT}. Jalankan server.py dulu.")
        return
    client.run()


if __name__ == "__main__":
    main()
