import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
import os
from datetime import datetime
import win32print



# --- 1. Fungsi Database SQLite ---
def connect_db():
    conn = sqlite3.connect('pos_data.db')
    return conn

def create_table():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            price REAL NOT NULL,
            stock INTEGER DEFAULT 0
        )
    ''')
    conn.commit()

    try:
        cursor.execute("ALTER TABLE products ADD COLUMN stock INTEGER DEFAULT 0")
        conn.commit()
    except sqlite3.OperationalError as e:
        if "duplicate column name: stock" in str(e):
            pass
        else:
            print(f"Error saat menambahkan kolom stock: {e}")
            messagebox.showerror("Error Database", f"Gagal memodifikasi tabel produk: {e}")
    conn.close()

def insert_product(product_id, name, price, stock):
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO products (id, name, price, stock) VALUES (?, ?, ?, ?)", (product_id, name, price, stock))
        conn.commit()
        return True
    except sqlite3.IntegrityError as e:
        if "UNIQUE constraint failed: products.id" in str(e):
            messagebox.showerror("Error", f"Produk dengan ID '{product_id}' sudah ada. Harap gunakan ID lain.")
        elif "UNIQUE constraint failed: products.name" in str(e):
            messagebox.showerror("Error", f"Produk dengan nama '{name}' sudah ada. Harap gunakan nama lain.")
        else:
            messagebox.showerror("Error", f"Terjadi kesalahan database: {e}")
        return False
    finally:
        conn.close()

def get_all_products():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, price, stock FROM products ORDER BY name ASC")
    products = cursor.fetchall()
    conn.close()
    return products

def get_product_by_id(product_id):
    conn = sqlite3.connect('pos_data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, price, stock FROM products WHERE id = ?", (product_id,))
    product = cursor.fetchone()
    conn.close()
    return product

def delete_product_by_id(product_id):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM products WHERE id = ?", (product_id,))
    conn.commit()
    conn.close()

def update_product_stock(product_id, new_stock):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE products SET stock = ? WHERE id = ?", (new_stock, product_id))
    conn.commit()
    conn.close()
    
# --- 2. Kelas Aplikasi POS dengan Tkinter ---
class POSApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Aplikasi POS Sederhana - Toko GRAND")
        self.root.geometry("1000x700")
        self.root.resizable(True, True)

        self.style = ttk.Style()
        self.style.theme_use('clam') 

        self.style.configure('.', font=('Segoe UI', 10))
        self.style.configure('TButton', font=('Segoe UI', 10, 'bold'), padding=8)
        self.style.configure('TLabel', font=('Segoe UI', 10))
        self.style.configure('TEntry', font=('Segoe UI', 10))
        self.style.configure('TNotebook.Tab', font=('Segoe UI', 11, 'bold'))

        self.style.configure('Header.TLabel', font=('Segoe UI', 16, 'bold'), foreground='#2C3E50')
        self.style.configure('Total.TLabel', font=('Segoe UI', 28, 'bold'), foreground='#27AE60')

        self.style.configure('TFrame', background='#ECF0F1')
        self.style.configure('TLabelframe', background='#ECF0F1')
        self.style.configure('TLabelframe.Label', background='#ECF0F1', font=('Segoe UI', 12, 'bold'), foreground='#34495E')

        self.style.configure("Treeview.Heading", font=('Segoe UI', 11, 'bold'), background='#3498DB', foreground='white')
        self.style.configure("Treeview", font=('Segoe UI', 10), rowheight=25, background='white', fieldbackground='white')

        create_table()

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(expand=True, fill="both", padx=15, pady=15)

        self.product_frame = ttk.Frame(self.notebook, style='TFrame')
        self.notebook.add(self.product_frame, text="Manajemen Produk")
        self.create_product_management_ui(self.product_frame)

        self.transaction_frame = ttk.Frame(self.notebook, style='TFrame')
        self.notebook.add(self.transaction_frame, text="Transaksi Penjualan")
        self.create_transaction_ui(self.transaction_frame)

    def create_product_management_ui(self, parent_frame):
        parent_frame.columnconfigure(0, weight=1)

        ttk.Label(parent_frame, text="Manajemen Produk", style='Header.TLabel').pack(pady=15)

        input_frame = ttk.LabelFrame(parent_frame, text="Tambah Produk Baru", style='TLabelframe')
        input_frame.pack(pady=10, padx=20, fill="x")
        input_frame.columnconfigure(1, weight=1)

        ttk.Label(input_frame, text="ID Produk:").grid(row=0, column=0, padx=10, pady=5, sticky="w")
        self.product_id_entry = ttk.Entry(input_frame)
        self.product_id_entry.grid(row=0, column=1, padx=10, pady=5, sticky="ew")

        ttk.Label(input_frame, text="Nama Produk:").grid(row=1, column=0, padx=10, pady=5, sticky="w")
        self.product_name_entry = ttk.Entry(input_frame)
        self.product_name_entry.grid(row=1, column=1, padx=10, pady=5, sticky="ew")

        ttk.Label(input_frame, text="Harga (Rp):").grid(row=2, column=0, padx=10, pady=5, sticky="w")
        self.product_price_entry = ttk.Entry(input_frame)
        self.product_price_entry.grid(row=2, column=1, padx=10, pady=5, sticky="ew")
        
        ttk.Label(input_frame, text="Stok Awal:").grid(row=3, column=0, padx=10, pady=5, sticky="w")
        self.product_stock_entry = ttk.Entry(input_frame)
        self.product_stock_entry.insert(0, "0")
        self.product_stock_entry.grid(row=3, column=1, padx=10, pady=5, sticky="ew")

        add_button = ttk.Button(input_frame, text="Tambah Produk", command=self.add_product, style='TButton')
        add_button.grid(row=4, column=0, columnspan=2, pady=15, padx=10)

        list_frame = ttk.LabelFrame(parent_frame, text="Daftar Produk Tersedia", style='TLabelframe')
        list_frame.pack(pady=10, padx=20, fill="both", expand=True)

        columns = ("ID", "Nama Produk", "Harga", "Stok")
        self.product_tree = ttk.Treeview(list_frame, columns=columns, show="headings", selectmode="browse")
        self.product_tree.pack(fill="both", expand=True, padx=10, pady=10)

        for col in columns:
            self.product_tree.heading(col, text=col, anchor="center")
            self.product_tree.column(col, anchor="center")
        
        self.product_tree.column("ID", width=80, stretch=tk.NO)
        self.product_tree.column("Nama Produk", width=250, stretch=tk.YES)
        self.product_tree.column("Harga", width=120, stretch=tk.NO)
        self.product_tree.column("Stok", width=70, stretch=tk.NO)

        product_tree_scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.product_tree.yview)
        self.product_tree.configure(yscrollcommand=product_tree_scrollbar.set)
        product_tree_scrollbar.pack(side="right", fill="y")

        delete_button = ttk.Button(list_frame, text="Hapus Produk Terpilih", command=self.delete_selected_product, style='TButton')
        delete_button.pack(pady=10, padx=10)

        self.load_products_to_tree()

    def load_products_to_tree(self):
        for i in self.product_tree.get_children():
            self.product_tree.delete(i)
        
        products = get_all_products()
        for prod_id, name, price, stock in products:
            self.product_tree.insert("", "end", values=(prod_id, name, f"Rp{price:,.2f}", stock))
        
        self.product_id_entry.delete(0, tk.END)
        self.product_name_entry.delete(0, tk.END)
        self.product_price_entry.delete(0, tk.END)
        self.product_stock_entry.delete(0, tk.END)
        self.product_stock_entry.insert(0, "0")

    def add_product(self):
        product_id = self.product_id_entry.get().strip()
        name = self.product_name_entry.get().strip()
        price_str = self.product_price_entry.get().strip()
        stock_str = self.product_stock_entry.get().strip()

        if not product_id:
            messagebox.showwarning("Input Kosong", "ID Produk tidak boleh kosong.")
            return
        if not name:
            messagebox.showwarning("Input Kosong", "Nama produk tidak boleh kosong.")
            return
        if not price_str:
            messagebox.showwarning("Input Kosong", "Harga produk tidak boleh kosong.")
            return
        if not stock_str:
            messagebox.showwarning("Input Kosong", "Stok awal tidak boleh kosong.")
            return

        try:
            price = float(price_str)
            if price <= 0:
                messagebox.showwarning("Harga Tidak Valid", "Harga harus lebih besar dari nol.")
                return
        except ValueError:
            messagebox.showwarning("Input Tidak Valid", "Harga harus berupa angka.")
            return
        
        try:
            stock = int(stock_str)
            if stock < 0:
                messagebox.showwarning("Stok Tidak Valid", "Stok tidak boleh kurang dari nol.")
                return
        except ValueError:
            messagebox.showwarning("Input Tidak Valid", "Stok harus berupa angka bulat.")
            return
        
        if insert_product(product_id, name, price, stock):
            messagebox.showinfo("Berhasil", f"Produk '{name}' (ID: {product_id}) berhasil ditambahkan dengan stok: {stock}.")
            self.load_products_to_tree()

    def delete_selected_product(self):
        selected_item = self.product_tree.selection()
        if not selected_item:
            messagebox.showwarning("Tidak Ada Pilihan", "Pilih produk yang ingin dihapus terlebih dahulu.")
            return
        
        product_id = self.product_tree.item(selected_item[0])['values'][0]
        product_name = self.product_tree.item(selected_item[0])['values'][1]

        if messagebox.askyesno("Konfirmasi Hapus", f"Apakah Anda yakin ingin menghapus produk '{product_name}' (ID: {product_id})?"):
            delete_product_by_id(product_id)
            messagebox.showinfo("Berhasil", f"Produk '{product_name}' (ID: {product_id}) berhasil dihapus.")
            self.load_products_to_tree()

    # --- UI untuk Transaksi Penjualan ---
    def create_transaction_ui(self, parent_frame):
        parent_frame.columnconfigure(0, weight=1)

        ttk.Label(parent_frame, text="Transaksi Penjualan", style='Header.TLabel').pack(pady=15)

        search_id_transaction_frame = ttk.LabelFrame(parent_frame, text="Scan / Masukkan ID Produk", style='TLabelframe')
        search_id_transaction_frame.pack(pady=10, padx=20, fill="x")
        search_id_transaction_frame.columnconfigure(1, weight=1)

        ttk.Label(search_id_transaction_frame, text="ID Produk:").grid(row=0, column=0, padx=10, pady=5, sticky="w")
        self.transaction_search_id_entry = ttk.Entry(search_id_transaction_frame)
        self.transaction_search_id_entry.grid(row=0, column=1, padx=10, pady=5, sticky="ew")
        self.transaction_search_id_entry.bind('<Return>', self.process_product_id_input)
        self.transaction_search_id_entry.focus_set()

        ttk.Label(search_id_transaction_frame, text="Nama:").grid(row=1, column=0, padx=10, pady=5, sticky="w")
        self.found_product_name_label = ttk.Label(search_id_transaction_frame, text="-", font=('Segoe UI', 10, 'bold'))
        self.found_product_name_label.grid(row=1, column=1, padx=10, pady=5, sticky="w", columnspan=2)

        ttk.Label(search_id_transaction_frame, text="Harga:").grid(row=2, column=0, padx=10, pady=5, sticky="w")
        self.found_product_price_label = ttk.Label(search_id_transaction_frame, text="Rp0.00", font=('Segoe UI', 10, 'bold'), foreground='#2980B9')
        self.found_product_price_label.grid(row=2, column=1, padx=10, pady=5, sticky="w", columnspan=2)

        ttk.Label(search_id_transaction_frame, text="Stok Tersedia:").grid(row=3, column=0, padx=10, pady=5, sticky="w")
        self.found_product_stock_label = ttk.Label(search_id_transaction_frame, text="0", font=('Segoe UI', 10, 'bold'), foreground='#E67E22')
        self.found_product_stock_label.grid(row=3, column=1, padx=10, pady=5, sticky="w", columnspan=2)

        cart_frame = ttk.LabelFrame(parent_frame, text="Keranjang Belanja", style='TLabelframe')
        cart_frame.pack(pady=10, padx=20, fill="both", expand=True)

        cart_columns = ("ID Produk", "Nama Produk", "Jumlah", "Harga Satuan", "Subtotal")
        self.cart_tree = ttk.Treeview(cart_frame, columns=cart_columns, show="headings", selectmode="browse")
        self.cart_tree.pack(fill="both", expand=True, padx=10, pady=10)

        for col in cart_columns:
            self.cart_tree.heading(col, text=col, anchor="center")
            self.cart_tree.column(col, anchor="center")
        
        self.cart_tree.column("ID Produk", width=80, stretch=tk.NO)
        self.cart_tree.column("Nama Produk", width=200, stretch=tk.YES)
        self.cart_tree.column("Jumlah", width=70, stretch=tk.NO)
        self.cart_tree.column("Harga Satuan", width=100, stretch=tk.NO)
        self.cart_tree.column("Subtotal", width=120, stretch=tk.NO)

        self.cart_scrollbar = ttk.Scrollbar(cart_frame, orient="vertical", command=self.cart_tree.yview) 
        self.cart_tree.configure(yscrollcommand=self.cart_scrollbar.set) 
        self.cart_scrollbar.pack(side="right", fill="y") 

        delete_cart_item_button = ttk.Button(cart_frame, text="Hapus Item Terpilih", command=self.remove_from_cart, style='TButton')
        delete_cart_item_button.pack(pady=5, padx=10, anchor="w")

        total_display_frame = ttk.Frame(parent_frame, style='TFrame')
        total_display_frame.pack(fill="x", pady=10, padx=20)
        total_display_frame.columnconfigure(0, weight=1)
        
        self.total_label = ttk.Label(total_display_frame, text="TOTAL: Rp0.00", style='Total.TLabel')
        self.total_label.grid(row=0, column=0, sticky="e", padx=10)

        finish_transaction_button = ttk.Button(parent_frame, text="Selesaikan Transaksi", command=self.complete_transaction, style='TButton')
        finish_transaction_button.pack(pady=20, padx=20, fill="x")

        self.cart_items = {}
        self.update_total_label()

    def process_product_id_input(self, event=None):
        search_id = self.transaction_search_id_entry.get().strip()
        
        self.transaction_search_id_entry.delete(0, tk.END)

        if not search_id:
            self._clear_found_product_display()
            return
        
        product = get_product_by_id(search_id)
        if product:
            p_id, p_name, p_price, p_stock = product

            self.found_product_name_label.config(text=p_name)
            self.found_product_price_label.config(text=f"Rp{p_price:,.2f}")
            self.found_product_stock_label.config(text=str(p_stock))

            current_qty_in_cart = self.cart_items.get(p_id, {}).get('qty', 0)
            if current_qty_in_cart + 1 > p_stock:
                messagebox.showwarning("Stok Tidak Cukup", f"Stok {p_name} hanya {p_stock}. Tidak dapat menambahkan lagi.")
                self.root.after(500, self._clear_found_product_display)
                self.transaction_search_id_entry.focus_set()
                return
            
            self._add_item_to_cart_logic(p_id, p_name, p_price, 1, p_stock)

            self.root.after(500, self._clear_found_product_display)
            self.transaction_search_id_entry.focus_set()
        else:
            messagebox.showinfo("Tidak Ditemukan", f"Produk dengan ID '{search_id}' tidak ditemukan.")
            self.root.after(500, self._clear_found_product_display)
            self.transaction_search_id_entry.focus_set()

    def _clear_found_product_display(self):
        self.found_product_name_label.config(text="-")
        self.found_product_price_label.config(text="Rp0.00")
        self.found_product_stock_label.config(text="0")

    def _add_item_to_cart_logic(self, product_id, product_name, product_price, quantity, product_initial_stock):
        if product_id in self.cart_items:
            new_qty = self.cart_items[product_id]['qty'] + quantity
            if new_qty > product_initial_stock:
                messagebox.showwarning("Stok Tidak Cukup", f"Stok {product_name} hanya {product_initial_stock}. Tidak dapat menambahkan lebih dari itu.")
                return
            self.cart_items[product_id]['qty'] = new_qty
        else:
            if quantity > product_initial_stock:
                messagebox.showwarning("Stok Tidak Cukup", f"Stok {product_name} hanya {product_initial_stock}. Tidak dapat menambahkan {quantity} item.")
                return
            self.cart_items[product_id] = {
                'name': product_name,
                'price': product_price,
                'qty': quantity,
                'initial_stock': product_initial_stock
            }
        
        self.update_cart_treeview()
        self.update_total_label()

    def remove_from_cart(self):
        selected_item = self.cart_tree.selection()
        if not selected_item:
            messagebox.showwarning("Tidak Ada Pilihan", "Pilih item di keranjang yang ingin dihapus.")
            return
        
        product_id_to_remove = self.cart_tree.item(selected_item[0])['values'][0]
        product_name_to_remove = self.cart_tree.item(selected_item[0])['values'][1]

        if messagebox.askyesno("Konfirmasi Hapus", f"Apakah Anda yakin ingin menghapus produk '{product_name_to_remove}' (ID: {product_id_to_remove}) dari keranjang?"):
            if product_id_to_remove in self.cart_items:
                del self.cart_items[product_id_to_remove]
                self.update_cart_treeview()
                self.update_total_label()
                messagebox.showinfo("Berhasil", f"Produk '{product_name_to_remove}' berhasil dihapus dari keranjang.")
            else:
                messagebox.showerror("Error", "Item tidak ditemukan di keranjang. (Ini seharusnya tidak terjadi)")

    def update_cart_treeview(self):
        for i in self.cart_tree.get_children():
            self.cart_tree.delete(i)
        
        for prod_id, data in self.cart_items.items():
            name = data['name']
            qty = data['qty']
            price = data['price']
            subtotal = qty * price
            self.cart_tree.insert("", "end", values=(prod_id, name, qty, f"Rp{price:,.2f}", f"Rp{subtotal:,.2f}"))

    def update_total_label(self):
        total = sum(item['qty'] * item['price'] for item in self.cart_items.values())
        self.total_label.config(text=f"TOTAL: Rp{total:,.2f}")
        
    def complete_transaction(self):
        if not self.cart_items:
            messagebox.showwarning("Keranjang Kosong", "Keranjang belanja masih kosong.")
            return
        
        total = sum(item['qty'] * item['price'] for item in self.cart_items.values())
        
        if not messagebox.askyesno("Konfirmasi Pembayaran", f"Total yang harus dibayar: Rp{total:,.2f}\nLanjutkan transaksi?"):
            return

        try:
            for prod_id, data in self.cart_items.items():
                current_db_product = get_product_by_id(prod_id)
                if current_db_product:
                    db_id, db_name, db_price, db_stock = current_db_product
                    if db_stock < data['qty']:
                        messagebox.showerror("Stok Tidak Cukup", f"Stok {db_name} tidak mencukupi untuk transaksi ini. Hanya tersisa {db_stock}.")
                        return
                    new_stock = db_stock - data['qty']
                    update_product_stock(prod_id, new_stock)
                else:
                    messagebox.showerror("Error Stok", f"Produk '{data['name']}' (ID: {prod_id}) tidak ditemukan di database saat mengurangi stok.")
                    return
        except Exception as e:
            messagebox.showerror("Error Stok", f"Terjadi kesalahan saat mengurangi stok: {e}")
            return

        self.generate_and_print_receipt(self.cart_items, total)

        messagebox.showinfo("Transaksi Selesai", "Transaksi berhasil!\nStruk telah dicetak ke printer.")

        self.cart_items = {}
        self.update_cart_treeview()
        self.update_total_label()
        self.transaction_search_id_entry.focus_set()
        self.load_products_to_tree()

    def generate_and_print_receipt(self, items_in_cart, total_amount):
        """
        Menghasilkan struk transaksi dan mencetaknya ke printer Blueprint M58 
        melalui printer sharing Windows (RAW ESC/POS).
        """

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        transaction_id = datetime.now().strftime("%Y%m%d%H%M%S")

        # Ganti dengan nama printer yang ter-share di Windows (pastikan ini benar)
        printer_name = r"Blueprint_M58"  # <- Ganti sesuai share name printer kamu

        try:
            receipt = b"\x1b@"  # Initialize printer

            # Header
            receipt += b"\x1b\x61\x01"  # Align center
            receipt += b"\x1b\x45\x01TOKO GRAND\x1b\x45\x00\n"
            receipt += b"Jl. Moh Saleh Bantilan\n"
            receipt += b"Tolitoli, Sulawesi Tengah\n"
            receipt += b"Telp: 085222224333\n\n"

            # Info transaksi
            receipt += b"\x1b\x61\x00"  # Align left
            receipt += f"Waktu: {current_time}\n".encode()
            receipt += f"ID: {transaction_id}\n".encode()
            receipt += b"--------------------------------\n"
            receipt += b"Produk     Q x Hrg   Subtotal\n"
            receipt += b"--------------------------------\n"

            for prod_id, data in items_in_cart.items():
                name = data['name']
                qty = data['qty']
                price = data['price']
                subtotal = qty * price

                item_name_formatted = name[:10]
                price_formatted = f"{price:,.0f}" if price == int(price) else f"{price:,.2f}"
                subtotal_formatted = f"{subtotal:,.0f}" if subtotal == int(subtotal) else f"{subtotal:,.2f}"

                line = f"{item_name_formatted:<10} {qty:>2}x{price:>5,.0f} {subtotal:>10,.0f}\n"

                receipt += line.encode()

                if len(name) > 10:
                    receipt += f"  {name[10:]}\n".encode()

            receipt += b"--------------------------------\n"
            receipt += b"\x1b\x61\x02"  # Align right
            receipt += b"\x1b\x45\x01"  # Bold on
            receipt += f"TOTAL: Rp{total_amount:,.0f}\n".encode()
            receipt += b"\x1b\x45\x00"  # Bold off

            receipt += b"\x1b\x61\x01"  # Center
            receipt += b"\nTERIMA KASIH!\nSelamat Berbelanja Kembali\n"
            receipt += b"================================\n\n\n"
            receipt += b"\x1dV\x00"  # Cut paper

            # Kirim ke printer
            printer = win32print.OpenPrinter(printer_name)
            job = win32print.StartDocPrinter(printer, 1, ("Struk Transaksi", None, "RAW"))
            win32print.StartPagePrinter(printer)
            win32print.WritePrinter(printer, receipt)
            win32print.EndPagePrinter(printer)
            win32print.EndDocPrinter(printer)
            win32print.ClosePrinter(printer)

            self._save_receipt_to_file(items_in_cart, total_amount, current_time, transaction_id)

        except Exception as e:
            messagebox.showerror("Gagal Cetak", f"Error saat mencetak:\n{e}\n\n"
                                                "Pastikan printer Blueprint M58 tersambung dan dibagikan melalui jaringan.")
            self._save_receipt_to_file(items_in_cart, total_amount, current_time, transaction_id)

    def _save_receipt_to_file(self, items_in_cart, total_amount, current_time, transaction_id):
                    receipt_content_file = f"""
            ======================================
                    STRUK BELANJA TOKO GRAND
            ======================================
            Waktu Transaksi: {current_time}
            ID Transaksi: {transaction_id}
            --------------------------------------
            No. ID Produk | Nama Produk | Qty | Harga Satuan | Subtotal
            --------------------------------------
            """
                    item_no = 1
                    for prod_id, data in items_in_cart.items():
                        name = data['name']
                        qty = data['qty']
                        price = data['price']
                        subtotal = qty * price
                        receipt_content_file += f"{item_no:3}. {prod_id:<10} | {name:<11} | {qty:<3} | {price:10,.2f} | {subtotal:8,.2f}\n"
                        item_no += 1

                    receipt_content_file += f"""
            --------------------------------------
            TOTAL PEMBAYARAN: Rp{total_amount:,.2f}
            ======================================
                    TERIMA KASIH!
                Selamat Berbelanja Kembali
            ======================================
            """
                    if not os.path.exists("receipts"):
                        os.makedirs("receipts")

                    file_name = f"receipts/struk_{transaction_id}.txt"
                    try:
                        with open(file_name, "w") as f:
                            f.write(receipt_content_file)
                        print(f"Struk transaksi disimpan sebagai: {file_name}")
                    except IOError as e:
                        messagebox.showerror("Error Simpan Struk", f"Gagal menyimpan struk ke file: {e}")


# --- 3. Main Program ---
if __name__ == "__main__":
    root = tk.Tk()
    app = POSApp(root)
    root.mainloop()