#!/usr/bin/env python3
"""
Klien pelanggan: pilih menu, kirim pesanan ke server, tunggu sampai siap.
"""
import time
from collections.abc import Iterator

from common import *


class ServerError(Exception):
    pass


class CustomerClient:
    """sesi pelanggan dengan server. menu + harga diambil dari server."""

    def __init__(self) -> None:
        self.conn = Connection.connect()
        self.conn.send("hello", role="customer")
        msg = self.expect("menu")
        self.merchant = msg["merchant"]
        self.menu: dict[str, int] = msg["menu"]
        self.menu_list = list(self.menu)

    def expect(self, *types: str) -> Message:
        """tunggu pesan dengan tipe tertentu, pesan lain diabaikan."""
        while True:
            msg = self.conn.recv()
            if msg is None:
                raise ServerError("koneksi ke server terputus")
            if msg["type"] == "error":
                raise ServerError(msg["message"])
            if msg["type"] in types:
                return msg

    def place_order(self, nama: str, selection: dict[str, int]) -> Message:
        self.conn.send("order", nama=nama, items=selection)
        return self.expect("accepted")

    def wait_ready(self) -> Iterator[Message]:
        # hasilkan setiap update status sampai pesanan siap.
        while True:
            msg = self.expect("status", "ready")
            yield msg
            if msg["type"] == "ready":
                return

    def close(self) -> None:
        self.conn.close()


# ---------------- tampilan ----------------
def print_menu(menu: dict[str, int]) -> None:
    clear_screen()
    print("\n\n------------- MENU -------------")
    print("  Pilih makanan atau minuman:")
    for k, (name, price) in enumerate(menu.items()):
        print(f"    {k + 1}. {name:<14}{rupiah(price):>10}")
    print("--------------------------------\n")


def erase_lines(n: int) -> None:
    print(f"\033[{n}F\033[0J", end="")


def select_items(menu_list: list[str]) -> dict[str, int]:
    """loop pemilihan menu. mengembalikan dict dengan bentuk {nama_menu: jumlah, +}."""
    selection: dict[str, int] = {}
    erase_count = 0
    while True:
        if selection:
            erase_count += 3
            print("---- ORDERAN ANDA ---")
            for k, v in selection.items():
                print(f"{k} sebanyak {v} buah")
                erase_count += 1
            print("---------------------\n")
        try:
            s = int(input("Pilihan (angka): "))
        except ValueError:
            s = 0  # bukan angka: lewat jalur "angka invalid" agar hapus-baris tetap pas
        if 0 < s <= len(menu_list):
            key = menu_list[s - 1]
            selection[key] = selection.get(key, 0) + 1
            if input("Order lagi? (y/N): ").lower() != "y":
                return selection
            erase_lines(erase_count + 2)
        else:
            print("angka invalid, mohon masukkan yang ada di MENU")
            time.sleep(1.7)
            erase_lines(erase_count + 2)
        erase_count = 0


def confirm_order(merchant: str, menu: dict[str, int], nama: str,
                  selection: dict[str, int]) -> bool:
    clear_screen()
    print("\n\n------------ ORDER CONFIRMATION ------------")
    print(f"  Merchant: {merchant}")
    print(f"  Atas Nama: {nama}")
    print("  Order:")
    for k, v in selection.items():
        print(f"      {v}x\t{k:<14}\t{rupiah(menu[k] * v):>10}")
    total = sum(menu[k] * v for k, v in selection.items())
    print(f"\n  Total\t\t\t\t{rupiah(total):>10}")
    print("--------------------------------------------\n")
    return input("Lanjutkan transaksi? (y/N): ").lower() == "y"


def print_receipt(merchant: str, menu: dict[str, int], receipt: Message) -> None:
    clear_screen()
    print("\n\n------------ RECEIPT ------------")
    print(f"  Merchant: {merchant}")
    print(f"  No. Antrian: {receipt['order_no']:03d}")
    print(f"  Atas Nama: {receipt['nama']}")
    for k, v in receipt["items"].items():
        print(f"  {v}x {k} = {rupiah(menu[k] * v)}")
    print(f"  Total: {rupiah(receipt['total'])}")
    print(f"  Estimasi tunggu: {receipt['estimasi']} menit")
    print("---------------------------------\n")


def show_updates(client: CustomerClient) -> None:
    """tampilkan update antrian yang didorong server sampai pesanan siap."""
    for msg in client.wait_ready():
        if msg["type"] == "ready":
            print(f"\nPesanan atas nama {msg['nama']} siap diambil!\a")
            return
        state = "sedang dimasak" if msg["status"] == DIPROSES else f"{msg['ahead']} orang di depan"
        print(f"Antrian: {', '.join(msg['queue'])}  [{state}]")


def loading(text: str) -> None:
    print(f"\n{text}.", end="", flush=True)
    for _ in range(2):
        time.sleep(0.7)
        print(".", end="", flush=True)
    print()


# ---------------- program utama ----------------
def serve_one_customer(client: CustomerClient) -> None:
    print_menu(client.menu)
    selection = select_items(client.menu_list)
    nama = input("\nOrder atas nama: ")
    if not confirm_order(client.merchant, client.menu, nama, selection):
        print("\nTransaksi dibatalkan.")
        return
    loading("Mengirim pesanan ke server")
    receipt = client.place_order(nama, selection)
    print_receipt(client.merchant, client.menu, receipt)
    show_updates(client)


def main() -> None:
    set_title("Dynamic Canteen QUEUE System")
    try:
        client = CustomerClient()
    except OSError:
        print(f"Tidak bisa terhubung ke server {HOST}:{PORT}. Jalankan server.py dulu.")
        return

    try:
        while True:
            serve_one_customer(client)
            if input("\nPelanggan berikutnya? (y/N): ").lower() != "y":
                break
    except ServerError as e:
        print(f"\nError dari server: {e}")
    except (KeyboardInterrupt, EOFError):
        print()
    finally:
        client.close()


if __name__ == "__main__":
    main()
