#!/usr/bin/env python3
"""
Server antrian kantin: menjembatani pelanggan (order.py) dan dapur (dapur.py).

Server memegang satu-satunya antrian yang sah. Pelanggan mengirim pesanan,
dapur memproses/menyelesaikan pesanan, dan server mendorong (push) setiap
perubahan antrian ke semua pihak yang terhubung.
"""
import argparse
import socket
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from common import *


@dataclass
class Order:
    no: int
    nama: str
    items: dict[str, int]
    total: int
    status: str = MENUNGGU
    conn: Connection | None = None  # None untuk pelanggan seed (palsu)
    waktu: str = field(default_factory=lambda: time.strftime("%H:%M:%S"))

    def to_dict(self) -> dict[str, Any]:
        return {"no": self.no, "nama": self.nama, "items": self.items,
                "total": self.total, "status": self.status, "waktu": self.waktu}


class CanteenServer:
    def __init__(self, seed: int = 0) -> None:
        self.orders: list[Order] = []  # antrian FIFO, dijaga self.lock
        self.last_no = 0
        self.lock = threading.Lock()
        self.dapur: Connection | None = None  # hanya satu dapur
        for i in range(seed):
            self.add_order(f"Pelanggan {i + 1}", {"es teh manis": 1})
        if seed:
            self.log(f"SEED {seed} pelanggan palsu")

    # ---------- utilitas ----------
    def log(self, event: str) -> None:
        """Tampilkan event + isi antrian di layar server."""
        names = ", ".join(o.nama for o in self.orders) or "-"
        print(f"{time.strftime('%H:%M:%S')} | {event} | antrian: {names}", flush=True)

    def broadcast(self) -> None:
        """Dorong status terbaru ke dapur dan ke setiap pelanggan yang menunggu.
        Dipanggil saat lock sedang dipegang."""
        if self.dapur:
            self.dapur.send("queue", orders=[o.to_dict() for o in self.orders])
        names = [o.nama for o in self.orders]
        for ahead, order in enumerate(self.orders):
            if order.conn and not order.conn.closed:
                order.conn.send("status", status=order.status, ahead=ahead, queue=names)

    # ---------- operasi antrian ----------
    def add_order(self, nama: str, items: dict[str, int],
                  conn: Connection | None = None) -> Order:
        self.last_no += 1
        total = sum(MENU[k] * v for k, v in items.items())
        order = Order(self.last_no, nama, items, total, conn=conn)
        self.orders.append(order)
        return order

    def place_order(self, conn: Connection, nama: str, items: dict[str, int]) -> None:
        with self.lock:
            order = self.add_order(nama.strip() or "Tanpa Nama", items, conn)
            ahead = len(self.orders) - 1
            conn.send("accepted", order_no=order.no, nama=order.nama, items=items,
                      total=order.total, ahead=ahead, estimasi=ahead)
            self.log(f"ORDER #{order.no:03d} {order.nama}")
            self.broadcast()

    def process_next(self) -> str:
        with self.lock:
            order = next((o for o in self.orders if o.status == MENUNGGU), None)
            if order is None:
                return "tidak ada pesanan yang menunggu"
            order.status = DIPROSES
            self.log(f"PROSES #{order.no:03d} {order.nama}")
            self.broadcast()
            return f"#{order.no:03d} {order.nama} diproses"

    def finish_front(self) -> str:
        with self.lock:
            if not self.orders:
                return "antrian kosong"
            order = self.orders.pop(0)
            if order.conn and not order.conn.closed:
                order.conn.send("ready", nama=order.nama)
            self.log(f"SIAP #{order.no:03d} {order.nama}")
            self.broadcast()
            return f"#{order.no:03d} {order.nama} siap diambil"

    # ---------- jaringan ----------
    def serve_forever(self) -> None:
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((HOST, PORT))
        srv.listen()
        print(f"Server {MERCHANT} berjalan di {HOST}:{PORT} (Ctrl+C untuk berhenti)")
        try:
            while True:
                sock, _ = srv.accept()
                threading.Thread(target=self.handle_client, args=(Connection(sock),),
                                 daemon=True).start()
        except KeyboardInterrupt:
            print("\nServer berhenti.")
        finally:
            srv.close()

    def handle_client(self, conn: Connection) -> None:
        hello = conn.recv()
        role = hello.get("role") if hello and hello.get("type") == "hello" else None
        try:
            if role == "customer":
                self.serve_customer(conn)
            elif role == "dapur":
                self.serve_dapur(conn)
            else:
                conn.send("error", message="harus diawali pesan hello")
        finally:
            conn.close()  # closed=True: pesanan tetap antre, tapi tak dikirimi pesan lagi

    def serve_customer(self, conn: Connection) -> None:
        print("[+] pelanggan terhubung", flush=True)
        conn.send("menu", merchant=MERCHANT, menu=MENU)
        while (msg := conn.recv()) is not None:
            if msg.get("type") == "order":
                self.place_order(conn, msg["nama"], msg["items"])
            else:
                conn.send("error", message="perintah tidak dikenal")
        print("[-] pelanggan terputus", flush=True)

    def serve_dapur(self, conn: Connection) -> None:
        with self.lock:
            if self.dapur:
                conn.send("error", message="dapur lain sudah terhubung")
                return
            self.dapur = conn
            conn.send("welcome", merchant=MERCHANT)
            self.broadcast()
        print("[+] dapur terhubung", flush=True)
        while (msg := conn.recv()) is not None:
            kind = msg.get("type")
            if kind == "process":
                result = self.process_next()
            elif kind == "done":
                result = self.finish_front()
            else:
                result = "perintah tidak dikenal"
            conn.send("info", message=result)
        with self.lock:
            self.dapur = None
        print("[-] dapur terputus", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Server antrian kantin")
    parser.add_argument("--seed", type=int, default=0, metavar="N",
                        help="isi antrian dengan N pelanggan palsu untuk demo")
    CanteenServer(parser.parse_args().seed).serve_forever()


if __name__ == "__main__":
    main()
