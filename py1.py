import tkinter as tk
from tkinter import ttk, messagebox, Toplevel, filedialog
import sqlite3
import os
from datetime import datetime
import csv # Import the csv module

import win32print # This module is specific to Windows for printing.
                  # If running on Linux/macOS, this part will cause an error
                  # and the printing functionality will not work.

# --- 1. Fungsi Database SQLite ---
def connect_db():
    """Membangun koneksi ke database SQLite."""
    conn = sqlite3.connect('pos_data.db')
    return conn

def create_table():
    """Membuat tabel 'products' jika belum ada.
    Menambahkan kolom 'stock' jika belum ada.
    """
    conn = sqlite3.connect('pos_data.db')
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

    # Memastikan kolom 'stock' ada di tabel 'products'
    try:
        cursor.execute("ALTER TABLE products ADD COLUMN stock INTEGER DEFAULT 0")
        conn.commit()
    except sqlite3.OperationalError as e:
        # Menangani error jika kolom 'stock' sudah ada
        if "duplicate column name: stock" in str(e):
            pass # Kolom sudah ada, tidak perlu melakukan apa-apa
        else:
            # Menangani error lain yang mungkin terjadi
            print(f"Error saat menambahkan kolom stock: {e}")
            messagebox.showerror("Error Database", f"Gagal memodifikasi tabel produk: {e}")
    conn.close()

def insert_product(product_id, name, price, stock):
    """Menambahkan produk baru ke database."""
    conn = sqlite3.connect('pos_data.db')
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
    """Mengambil semua produk dari database, diurutkan berdasarkan nama."""
    conn = sqlite3.connect('pos_data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, price, stock FROM products ORDER BY name ASC")
    products = cursor.fetchall()
    conn.close()
    return products

def get_product_by_id(product_id):
    """Mengambil produk berdasarkan ID."""
    conn = sqlite3.connect('pos_data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, price, stock FROM products WHERE id = ?", (product_id,))
    product = cursor.fetchone()
    conn.close()
    return product

def get_products_by_search_term(search_term):
    """Mengambil produk berdasarkan istilah pencarian (ID atau Nama)."""
    conn = sqlite3.connect('pos_data.db')
    cursor = conn.cursor()
    # Use LIKE for partial matching, and COLLATE NOCASE for case-insensitive search
    cursor.execute("SELECT id, name, price, stock FROM products WHERE id LIKE ? OR name LIKE ? ORDER BY name ASC", 
                   ('%' + search_term + '%', '%' + search_term + '%'))
    products = cursor.fetchall()
    conn.close()
    return products

def delete_product_by_id(product_id):
    """Menghapus produk berdasarkan ID."""
    conn = sqlite3.connect('pos_data.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM products WHERE id = ?", (product_id,))
    conn.commit()
    conn.close()

def update_product_stock(product_id, new_stock):
    """Memperbarui stok produk berdasarkan ID."""
    conn = sqlite3.connect('pos_data.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE products SET stock = ? WHERE id = ?", (new_stock, product_id))
    conn.commit()
    conn.close()

def get_low_stock_products(threshold=10):
    """Mengambil produk dengan stok di bawah ambang batas tertentu."""
    conn = sqlite3.connect('pos_data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, stock FROM products WHERE stock <= ? ORDER BY stock ASC, name ASC", (threshold,))
    low_stock_products = cursor.fetchall()
    conn.close()
    return low_stock_products
    
# --- 2. Kelas Aplikasi POS dengan Tkinter ---
class POSApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Aplikasi POS Sederhana - Toko GRAND")
        self.root.geometry("1000x700")
        self.root.resizable(True, True)

        self.style = ttk.Style()
        self.style.theme_use('clam') 

        # Global font configuration for most widgets
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

        # Specific style for Treeview content (larger font)
        # Using a custom style for the cart treeview to allow for specific font size
        self.style.configure("Cart.Treeview", font=('Segoe UI', 12), rowheight=28, background='white', fieldbackground='white')
        self.style.configure("Cart.Treeview.Heading", font=('Segoe UI', 11, 'bold'), background='#3498DB', foreground='white')
        
        # Default Treeview style for others (e.g., product management)
        self.style.configure("Treeview", font=('Segoe UI', 10), rowheight=25, background='white', fieldbackground='white')
        self.style.configure("Treeview.Heading", font=('Segoe UI', 11, 'bold'), background='#3498DB', foreground='white')


        # Style for the delete button
        self.style.configure('Danger.TButton', background='#E74C3C', foreground='white', font=('Segoe UI', 10, 'bold'))
        self.style.map('Danger.TButton',
                       background=[('active', '#C0392B')],
                       foreground=[('active', 'white')])

        create_table()

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(expand=True, fill="both", padx=15, pady=15)

        # Tab Manajemen Produk
        self.product_frame = ttk.Frame(self.notebook, style='TFrame')
        self.notebook.add(self.product_frame, text="Manajemen Produk")
        self.create_product_management_ui(self.product_frame)

        # Tab Transaksi Penjualan
        self.transaction_frame = ttk.Frame(self.notebook, style='TFrame')
        self.notebook.add(self.transaction_frame, text="Transaksi Penjualan")
        self.create_transaction_ui(self.transaction_frame)

        # Tab Laporan Stok
        self.low_stock_frame = ttk.Frame(self.notebook, style='TFrame')
        self.notebook.add(self.low_stock_frame, text="Laporan Stok")
        self.create_low_stock_report_ui(self.low_stock_frame)

    def create_product_management_ui(self, parent_frame):
        """Membuat antarmuka pengguna untuk manajemen produk."""
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
        self.product_stock_entry.insert(0, "0") # Default stock to 0
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

        button_frame = ttk.Frame(list_frame, style='TFrame')
        button_frame.pack(pady=10, padx=10, fill="x", anchor="w")

        delete_button = ttk.Button(button_frame, text="Hapus Produk Terpilih", command=self.delete_selected_product, style='TButton')
        delete_button.pack(side="left", padx=5)

        # Tombol Edit Stok
        edit_stock_button = ttk.Button(button_frame, text="Edit Stok Terpilih", command=self.edit_selected_product_stock, style='TButton')
        edit_stock_button.pack(side="left", padx=5)

        # --- CSV Import/Export Section ---
        csv_frame = ttk.LabelFrame(parent_frame, text="Impor/Ekspor Data Produk (CSV)", style='TLabelframe')
        csv_frame.pack(pady=10, padx=20, fill="x")
        csv_frame.columnconfigure(0, weight=1)
        csv_frame.columnconfigure(1, weight=1)

        # Import Section
        ttk.Label(csv_frame, text="Impor Stok dari CSV:").grid(row=0, column=0, padx=10, pady=5, sticky="w")
        self.csv_file_path_label = ttk.Label(csv_frame, text="Tidak ada file terpilih", foreground='gray')
        self.csv_file_path_label.grid(row=0, column=1, padx=10, pady=5, sticky="ew")

        self.select_csv_button = ttk.Button(csv_frame, text="Pilih File CSV", command=self.open_csv_file_dialog, style='TButton')
        self.select_csv_button.grid(row=1, column=0, padx=10, pady=5, sticky="ew")

        self.import_stock_button = ttk.Button(csv_frame, text="Update Stok dari CSV", command=self.import_stock_from_csv, style='TButton')
        self.import_stock_button.grid(row=1, column=1, padx=10, pady=5, sticky="ew")

        ttk.Separator(csv_frame, orient="horizontal").grid(row=2, columnspan=2, sticky="ew", pady=10)

        # Export Section
        self.download_template_button = ttk.Button(csv_frame, text="Download Template CSV", command=self.download_csv_template, style='TButton')
        self.download_template_button.grid(row=3, column=0, padx=10, pady=5, sticky="ew")

        self.export_data_button = ttk.Button(csv_frame, text="Export Data Produk ke CSV", command=self.export_products_to_csv, style='TButton')
        self.export_data_button.grid(row=3, column=1, padx=10, pady=5, sticky="ew")
        # --- End CSV Import/Export Section ---

        self.load_products_to_tree()
        self.selected_csv_file = None # Initialize selected CSV file path

    def load_products_to_tree(self):
        """Memuat data produk dari database ke Treeview manajemen produk."""
        for i in self.product_tree.get_children():
            self.product_tree.delete(i)
        
        products = get_all_products()
        for prod_id, name, price, stock in products:
            self.product_tree.insert("", "end", values=(prod_id, name, f"Rp{price:,.2f}", stock))
        
        # Mengosongkan input setelah produk dimuat
        self.product_id_entry.delete(0, tk.END)
        self.product_name_entry.delete(0, tk.END)
        self.product_price_entry.delete(0, tk.END)
        self.product_stock_entry.delete(0, tk.END)
        self.product_stock_entry.insert(0, "0") # Reset stock entry to 0

    def add_product(self):
        """Menambahkan produk baru ke database dan memperbarui Treeview."""
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
            self.load_products_to_tree() # Muat ulang data setelah penambahan

    def delete_selected_product(self):
        """Menghapus produk yang dipilih dari database dan memperbarui Treeview."""
        selected_item = self.product_tree.selection()
        if not selected_item:
            messagebox.showwarning("Tidak Ada Pilihan", "Pilih produk yang ingin dihapus terlebih dahulu.")
            return
        
        product_id = self.product_tree.item(selected_item[0])['values'][0]
        product_name = self.product_tree.item(selected_item[0])['values'][1]

        if messagebox.askyesno("Konfirmasi Hapus", f"Apakah Anda yakin ingin menghapus produk '{product_name}' (ID: {product_id})?"):
            delete_product_by_id(product_id)
            messagebox.showinfo("Berhasil", f"Produk '{product_name}' (ID: {product_id}) berhasil dihapus.")
            self.load_products_to_tree() # Muat ulang data setelah penghapusan

    def edit_selected_product_stock(self):
        """Membuka jendela baru untuk mengedit stok produk yang dipilih."""
        selected_item = self.product_tree.selection()
        if not selected_item:
            messagebox.showwarning("Tidak Ada Pilihan", "Pilih produk yang stoknya ingin diedit terlebih dahulu.")
            return
        
        # Ambil data produk dari item yang dipilih di Treeview
        product_id = self.product_tree.item(selected_item[0])['values'][0]
        product_name = self.product_tree.item(selected_item[0])['values'][1]
        current_stock = self.product_tree.item(selected_item[0])['values'][3]

        # Buat jendela Toplevel baru
        edit_window = Toplevel(self.root)
        edit_window.title(f"Edit Stok: {product_name}")
        edit_window.transient(self.root) # Membuat jendela ini di atas jendela utama
        edit_window.grab_set() # Mengunci interaksi dengan jendela utama
        edit_window.resizable(False, False)

        # Frame untuk input
        input_frame = ttk.Frame(edit_window, padding="15")
        input_frame.pack()

        ttk.Label(input_frame, text="Nama Produk:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        ttk.Label(input_frame, text=product_name, font=('Segoe UI', 10, 'bold')).grid(row=0, column=1, padx=5, pady=5, sticky="w")

        ttk.Label(input_frame, text="Stok Saat Ini:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        ttk.Label(input_frame, text=str(current_stock), font=('Segoe UI', 10, 'bold')).grid(row=1, column=1, padx=5, pady=5, sticky="w")

        ttk.Label(input_frame, text="Stok Baru:").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        new_stock_entry = ttk.Entry(input_frame)
        new_stock_entry.grid(row=2, column=1, padx=5, pady=5, sticky="ew")
        new_stock_entry.insert(0, str(current_stock)) # Isi dengan stok saat ini
        new_stock_entry.focus_set()

        # Tombol Simpan
        save_button = ttk.Button(input_frame, text="Simpan", 
                                  command=lambda: self._save_edited_stock(product_id, new_stock_entry.get(), edit_window),
                                  style='TButton')
        save_button.grid(row=3, column=0, columnspan=2, pady=10)

    def _save_edited_stock(self, product_id, new_stock_str, edit_window):
        """Menyimpan stok yang diedit ke database."""
        try:
            new_stock = int(new_stock_str.strip())
            if new_stock < 0:
                messagebox.showwarning("Stok Tidak Valid", "Stok baru tidak boleh kurang dari nol.")
                return
        except ValueError:
            messagebox.showwarning("Input Tidak Valid", "Stok baru harus berupa angka bulat.")
            return
        
        update_product_stock(product_id, new_stock)
        messagebox.showinfo("Berhasil", f"Stok produk ID '{product_id}' berhasil diperbarui menjadi {new_stock}.")
        self.load_products_to_tree() # Muat ulang data produk untuk menampilkan perubahan
        edit_window.destroy() # Tutup jendela edit

    def open_csv_file_dialog(self):
        """Membuka dialog untuk memilih file CSV."""
        file_path = filedialog.askopenfilename(
            title="Pilih File CSV Stok Produk",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if file_path:
            self.selected_csv_file = file_path
            self.csv_file_path_label.config(text=os.path.basename(file_path), foreground='black')
        else:
            self.selected_csv_file = None
            self.csv_file_path_label.config(text="Tidak ada file terpilih", foreground='gray')

    def import_stock_from_csv(self):
        """Mengimpor stok produk dari file CSV yang dipilih.
           Jika ID produk tidak ada, produk baru akan ditambahkan.
        """
        if not self.selected_csv_file:
            messagebox.showwarning("Tidak Ada File", "Pilih file CSV terlebih dahulu.")
            return

        updated_count = 0
        new_product_count = 0
        failed_count = 0
        error_messages = []

        try:
            with open(self.selected_csv_file, 'r', newline='', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                
                # Check for required columns for both update and new creation
                required_columns = ['ID Produk', 'Nama Produk', 'Harga', 'Stok']
                if not all(col in reader.fieldnames for col in required_columns):
                    messagebox.showerror("Format CSV Salah", 
                                         f"File CSV harus memiliki kolom: {', '.join(required_columns)}.")
                    return

                for row_num, row in enumerate(reader, start=2): # Start from row 2 for user-friendly errors
                    product_id = row.get('ID Produk', '').strip()
                    name = row.get('Nama Produk', '').strip()
                    price_str = row.get('Harga', '').strip()
                    stock_str = row.get('Stok', '').strip()

                    if not product_id:
                        error_messages.append(f"Baris {row_num}: ID Produk kosong, dilewati.")
                        failed_count += 1
                        continue
                    
                    try:
                        stock = int(stock_str)
                        if stock < 0:
                            error_messages.append(f"Baris {row_num} (ID: {product_id}): Stok tidak valid (harus >= 0), dilewati.")
                            failed_count += 1
                            continue
                    except ValueError:
                        error_messages.append(f"Baris {row_num} (ID: {product_id}): Stok bukan angka, dilewati.")
                        failed_count += 1
                        continue
                    
                    product_exists = get_product_by_id(product_id)
                    if product_exists:
                        # Product exists, update stock
                        update_product_stock(product_id, stock)
                        updated_count += 1
                    else:
                        # Product does not exist, try to create new
                        if not name or not price_str:
                            error_messages.append(f"Baris {row_num} (ID: {product_id}): Nama atau Harga kosong untuk produk baru, dilewati.")
                            failed_count += 1
                            continue
                        try:
                            price = float(price_str)
                            if price <= 0:
                                error_messages.append(f"Baris {row_num} (ID: {product_id}): Harga tidak valid (harus > 0), dilewati.")
                                failed_count += 1
                                continue
                        except ValueError:
                            error_messages.append(f"Baris {row_num} (ID: {product_id}): Harga bukan angka, dilewati.")
                            failed_count += 1
                            continue
                        
                        if insert_product(product_id, name, price, stock):
                            new_product_count += 1
                        else:
                            # insert_product already shows an error message, just increment failed count
                            failed_count += 1

            messagebox.showinfo("Impor Selesai", 
                                 f"Impor stok selesai.\n"
                                 f"Produk diperbarui: {updated_count}\n"
                                 f"Produk baru ditambahkan: {new_product_count}\n"
                                 f"Gagal: {failed_count}")
            if error_messages:
                messagebox.showwarning("Detail Error Impor", "\n".join(error_messages))

            self.load_products_to_tree() # Muat ulang data produk di manajemen
            self.load_low_stock_to_tree() # Muat ulang laporan stok rendah
            self.csv_file_path_label.config(text="Tidak ada file terpilih", foreground='gray')
            self.selected_csv_file = None

        except FileNotFoundError:
            messagebox.showerror("File Tidak Ditemukan", "File CSV tidak ditemukan.")
        except Exception as e:
            messagebox.showerror("Error Impor CSV", f"Terjadi kesalahan saat mengimpor CSV:\n{e}")

    def download_csv_template(self):
        """Mengunduh template CSV untuk data produk."""
        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile="template_produk.csv",
            title="Simpan Template CSV Produk"
        )
        if file_path:
            try:
                with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    # Updated header to include Name and Price for new product creation
                    writer.writerow(['ID Produk', 'Nama Produk', 'Harga', 'Stok'])
                messagebox.showinfo("Berhasil", f"Template CSV berhasil disimpan ke:\n{file_path}")
            except Exception as e:
                messagebox.showerror("Error", f"Gagal menyimpan template CSV:\n{e}")

    def export_products_to_csv(self):
        """Mengekspor semua data produk ke file CSV."""
        products = get_all_products()
        if not products:
            messagebox.showwarning("Data Kosong", "Tidak ada data produk untuk diekspor.")
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile="data_produk_sekarang.csv",
            title="Simpan Data Produk ke CSV"
        )
        if file_path:
            try:
                with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    # Updated header to include Name and Price
                    writer.writerow(['ID Produk', 'Nama Produk', 'Harga', 'Stok']) # Header
                    for prod_id, name, price, stock in products:
                        writer.writerow([prod_id, name, price, stock])
                messagebox.showinfo("Berhasil", f"Data produk berhasil diekspor ke:\n{file_path}")
            except Exception as e:
                messagebox.showerror("Error", f"Gagal mengekspor data produk ke CSV:\n{e}")


    # --- UI untuk Transaksi Penjualan ---
    def create_transaction_ui(self, parent_frame):
        """Membuat antarmuka pengguna untuk transaksi penjualan."""
        parent_frame.columnconfigure(0, weight=1) # Kolom kiri (pencarian)
        parent_frame.columnconfigure(1, weight=1) # Kolom kanan (keranjang)
        
        parent_frame.rowconfigure(0, weight=0) # Header
        parent_frame.rowconfigure(1, weight=1) # Baris utama untuk konten kiri-kanan
        parent_frame.rowconfigure(2, weight=0) # Total
        parent_frame.rowconfigure(3, weight=0) # Tombol Selesaikan Transaksi

        ttk.Label(parent_frame, text="Transaksi Penjualan", style='Header.TLabel').grid(row=0, column=0, columnspan=2, pady=15, sticky="ew")

        # --- Panel Kiri (Input Barcode & Live Search) ---
        left_panel_frame = ttk.Frame(parent_frame, style='TFrame')
        left_panel_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)
        left_panel_frame.columnconfigure(0, weight=1) # Izinkan konten di panel kiri untuk meluas
        left_panel_frame.rowconfigure(1, weight=1) # Izinkan live search frame meluas secara vertikal

        # Frame untuk input ID Produk (barcode scanner)
        search_id_transaction_frame = ttk.LabelFrame(left_panel_frame, text="Scan / Masukkan ID Produk (Barcode)", style='TLabelframe')
        search_id_transaction_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
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

        # --- Live Search Product Section ---
        live_search_frame = ttk.LabelFrame(left_panel_frame, text="Cari Produk (Live Search)", style='TLabelframe')
        live_search_frame.grid(row=1, column=0, sticky="nsew") # Mengisi sisa ruang vertikal di panel kiri
        live_search_frame.columnconfigure(0, weight=1)
        live_search_frame.columnconfigure(1, weight=1) 
        live_search_frame.rowconfigure(1, weight=1) # Izinkan treeview meluas

        search_results_columns = ("ID", "Nama Produk", "Harga", "Stok")
        self.live_search_tree = ttk.Treeview(live_search_frame, columns=search_results_columns, show="headings", selectmode="browse")
        self.live_search_tree.grid(row=1, column=0, columnspan=2, padx=10, pady=5, sticky="nsew")

        ttk.Label(live_search_frame, text="Cari Nama/ID:").grid(row=0, column=0, padx=10, pady=5, sticky="w")
        self.live_search_entry = ttk.Entry(live_search_frame)
        self.live_search_entry.grid(row=0, column=1, padx=10, pady=5, sticky="ew")
        self.live_search_entry.bind('<KeyRelease>', self.live_search_products) # Bind for live search


        for col in search_results_columns:
            self.live_search_tree.heading(col, text=col, anchor="center")
            self.live_search_tree.column(col, anchor="center")
        
        self.live_search_tree.column("ID", width=80, stretch=tk.NO)
        self.live_search_tree.column("Nama Produk", width=200, stretch=tk.YES)
        self.live_search_tree.column("Harga", width=100, stretch=tk.NO)
        self.live_search_tree.column("Stok", width=70, stretch=tk.NO)

        live_search_tree_scrollbar = ttk.Scrollbar(live_search_frame, orient="vertical", command=self.live_search_tree.yview)
        self.live_search_tree.configure(yscrollcommand=live_search_tree_scrollbar.set)
        live_search_tree_scrollbar.grid(row=1, column=2, sticky="ns") # Place scrollbar next to treeview

        self.live_search_tree.bind('<<TreeviewSelect>>', self.add_selected_product_from_search)
        # --- End Live Search Product Section ---

        # --- Panel Kanan (Keranjang Belanja) ---
        cart_frame = ttk.LabelFrame(parent_frame, text="Keranjang Belanja", style='TLabelframe')
        cart_frame.grid(row=1, column=1, sticky="nsew", padx=20, pady=10)
        cart_frame.columnconfigure(0, weight=1) # Izinkan konten di keranjang meluas
        cart_frame.rowconfigure(0, weight=1) # Izinkan treeview keranjang meluas

        # Kolom untuk keranjang belanja (ID Produk ada secara internal, tapi tidak ditampilkan)
        cart_columns = ("_id", "Nama Produk", "Jumlah", "Harga Satuan", "Subtotal") # Use _id for internal reference
        self.cart_tree = ttk.Treeview(cart_frame, columns=cart_columns, show="headings", selectmode="browse", style="Cart.Treeview") # Apply custom style
        self.cart_tree.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        # Configure columns, setting ID Produk width to 0 to hide it
        self.cart_tree.heading("_id", text="ID Produk", anchor="center")
        self.cart_tree.column("_id", width=0, stretch=tk.NO) # Hidden column
        
        self.cart_tree.heading("Nama Produk", text="Nama Produk", anchor="w") # Align left for better readability
        self.cart_tree.column("Nama Produk", width=200, stretch=tk.YES) # Adjusted width
        
        self.cart_tree.heading("Jumlah", text="Jumlah", anchor="center")
        self.cart_tree.column("Jumlah", width=70, stretch=tk.NO) # Adjusted width
        
        self.cart_tree.heading("Harga Satuan", text="Harga Satuan", anchor="e") # Align right for currency
        self.cart_tree.column("Harga Satuan", width=110, stretch=tk.NO) # Adjusted width
        
        self.cart_tree.heading("Subtotal", text="Subtotal", anchor="e") # Align right for currency
        self.cart_tree.column("Subtotal", width=120, stretch=tk.NO) # Adjusted width

        self.cart_scrollbar = ttk.Scrollbar(cart_frame, orient="vertical", command=self.cart_tree.yview) 
        self.cart_tree.configure(yscrollcommand=self.cart_scrollbar.set) 
        self.cart_scrollbar.grid(row=0, column=1, sticky="ns") 

        delete_cart_item_button = ttk.Button(cart_frame, text="Hapus Item Terpilih", command=self.remove_from_cart, style='Danger.TButton') # Apply Danger style
        delete_cart_item_button.grid(row=1, column=0, pady=5, padx=10, sticky="w")

        # --- Bagian Bawah (Total & Tombol Selesaikan Transaksi) ---
        total_display_frame = ttk.Frame(parent_frame, style='TFrame')
        total_display_frame.grid(row=2, column=0, columnspan=2, pady=10, padx=20, sticky="ew")
        total_display_frame.columnconfigure(0, weight=1)
        
        self.total_label = ttk.Label(total_display_frame, text="TOTAL: Rp0.00", style='Total.TLabel')
        self.total_label.grid(row=0, column=0, sticky="e", padx=10)

        finish_transaction_button = ttk.Button(parent_frame, text="Selesaikan Transaksi", command=lambda: self.complete_transaction(confirm=True), style='TButton')
        finish_transaction_button.grid(row=3, column=0, columnspan=2, pady=20, padx=20, sticky="ew")

        # Bind shortcut for completing transaction without confirmation
        self.root.bind('<F12>', lambda event: self.complete_transaction(confirm=False))


        self.cart_items = {} # Dictionary untuk menyimpan item di keranjang
        self.update_total_label()

    def live_search_products(self, event=None):
        """
        Melakukan pencarian produk secara langsung saat pengguna mengetik
        dan menampilkan hasilnya di live_search_tree.
        """
        search_term = self.live_search_entry.get().strip()

        # Bersihkan treeview hasil pencarian sebelumnya
        for i in self.live_search_tree.get_children():
            self.live_search_tree.delete(i)

        if search_term:
            products = get_products_by_search_term(search_term)
            for prod_id, name, price, stock in products:
                self.live_search_tree.insert("", "end", values=(prod_id, name, f"Rp{price:,.2f}", stock))

    def add_selected_product_from_search(self, event=None):
        """
        Menambahkan produk yang dipilih dari hasil live search ke keranjang.
        """
        selected_item = self.live_search_tree.selection()
        if not selected_item:
            return # No item selected

        # Get product ID from the selected item in the live search tree
        product_id = self.live_search_tree.item(selected_item[0])['values'][0]

        product = get_product_by_id(product_id)
        if product:
            p_id, p_name, p_price, p_stock = product

            current_qty_in_cart = self.cart_items.get(p_id, {}).get('qty', 0)
            if current_qty_in_cart + 1 > p_stock:
                messagebox.showwarning("Stok Tidak Cukup", f"Stok {p_name} hanya {p_stock}. Tidak dapat menambahkan lagi.")
                return
            
            self._add_item_to_cart_logic(p_id, p_name, p_price, 1, p_stock)
            
            # Clear live search entry and results after adding to cart
            self.live_search_entry.delete(0, tk.END)
            for i in self.live_search_tree.get_children():
                self.live_search_tree.delete(i)
            
            # Set focus back to the barcode scanner entry
            self.transaction_search_id_entry.focus_set()
        else:
            messagebox.showerror("Error", "Produk tidak ditemukan. (Ini seharusnya tidak terjadi)")


    def process_product_id_input(self, event=None):
        """Memproses input ID produk untuk ditambahkan ke keranjang."""
        search_id = self.transaction_search_id_entry.get().strip()
        
        self.transaction_search_id_entry.delete(0, tk.END) # Bersihkan input setelah diproses

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
        """Mengosongkan tampilan detail produk yang ditemukan."""
        self.found_product_name_label.config(text="-")
        self.found_product_price_label.config(text="Rp0.00")
        self.found_product_stock_label.config(text="0")

    def _add_item_to_cart_logic(self, product_id, product_name, product_price, quantity, product_initial_stock):
        """Logika untuk menambahkan item ke keranjang belanja."""
        # Pastikan product_id selalu string yang bersih dari spasi
        product_id = str(product_id).strip() 
        
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
                'initial_stock': product_initial_stock # Simpan stok awal untuk referensi
            }
        
        self.update_cart_treeview()
        self.update_total_label()

    def remove_from_cart(self):
        """Menghapus item yang dipilih dari keranjang belanja."""
        selected_item = self.cart_tree.selection()
        if not selected_item:
            messagebox.showwarning("Tidak Ada Pilihan", "Pilih item di keranjang yang ingin dihapus.")
            return
        
        # Get the internal ID (iid) of the selected item in the Treeview
        tree_item_id = selected_item[0]
        
        # We stored the product_id as the first value in the Treeview item's 'values' tuple
        raw_product_id_from_tree = self.cart_tree.item(tree_item_id)['values'][0]
        
        # Explicitly convert to string and strip any whitespace, ensuring type consistency
        product_id_to_remove = str(raw_product_id_from_tree).strip()
        
        # The product name is at index 1 in the values tuple (after the hidden ID)
        product_name_to_remove = self.cart_tree.item(tree_item_id)['values'][1]

        if messagebox.askyesno("Konfirmasi Hapus", f"Apakah Anda yakin ingin menghapus produk '{product_name_to_remove}' dari keranjang?"):
            if product_id_to_remove in self.cart_items:
                del self.cart_items[product_id_to_remove]
                self.cart_tree.delete(tree_item_id) # Directly delete the item from the Treeview
                self.update_total_label()
                messagebox.showinfo("Berhasil", f"Produk '{product_name_to_remove}' berhasil dihapus dari keranjang.")
            else:
                messagebox.showerror("Error", "Item tidak ditemukan di keranjang. (Ini seharusnya tidak terjadi)")

    def update_cart_treeview(self):
        """Memperbarui tampilan Treeview keranjang belanja."""
        for i in self.cart_tree.get_children():
            self.cart_tree.delete(i)
        
        for prod_id, data in self.cart_items.items():
            name = data['name']
            qty = data['qty']
            price = data['price']
            subtotal = qty * price
            # Memasukkan ID produk sebagai nilai pertama, meskipun kolomnya disembunyikan
            self.cart_tree.insert("", "end", values=(prod_id, name, qty, f"Rp{price:,.2f}", f"Rp{subtotal:,.2f}"))

    def update_total_label(self):
        """Memperbarui label total pembayaran."""
        total = sum(item['qty'] * item['price'] for item in self.cart_items.values())
        self.total_label.config(text=f"TOTAL: Rp{total:,.2f}")
        
    def complete_transaction(self, confirm=True):
        """Menyelesaikan transaksi, mengurangi stok, dan mencetak struk.
           Args:
               confirm (bool): Jika True, akan menampilkan dialog konfirmasi.
                               Jika False, transaksi akan langsung diselesaikan.
        """
        if not self.cart_items:
            messagebox.showwarning("Keranjang Kosong", "Keranjang belanja masih kosong.")
            return
        
        total = sum(item['qty'] * item['price'] for item in self.cart_items.values())
        
        if confirm: # Only show confirmation if confirm is True
            if not messagebox.askyesno("Konfirmasi Pembayaran", f"Total yang harus dibayar: Rp{total:,.2f}\nLanjutkan transaksi?"):
                return

        # Validasi stok terakhir sebelum mengurangi
        for prod_id, data in self.cart_items.items():
            current_db_product = get_product_by_id(prod_id)
            if current_db_product:
                db_id, db_name, db_price, db_stock = current_db_product
                if db_stock < data['qty']:
                    messagebox.showerror("Stok Tidak Cukup", f"Stok {db_name} tidak mencukupi untuk transaksi ini. Hanya tersisa {db_stock}.")
                    return # Batalkan transaksi jika stok tidak cukup
            else:
                messagebox.showerror("Error Stok", f"Produk '{data['name']}' (ID: {prod_id}) tidak ditemukan di database saat mengurangi stok.")
                return # Batalkan transaksi jika produk tidak ditemukan

        try:
            # Kurangi stok untuk setiap item di keranjang
            for prod_id, data in self.cart_items.items():
                current_db_product = get_product_by_id(prod_id)
                db_stock = current_db_product[3] # Ambil stok dari database
                new_stock = db_stock - data['qty']
                update_product_stock(prod_id, new_stock)
        except Exception as e:
            messagebox.showerror("Error Stok", f"Terjadi kesalahan saat mengurangi stok: {e}")
            return

        self.generate_and_print_receipt(self.cart_items, total)

        messagebox.showinfo("Transaksi Selesai", "Transaksi berhasil!\nStruk telah dicetak ke printer.")

        # Reset keranjang dan perbarui tampilan
        self.cart_items = {}
        self.update_cart_treeview()
        self.update_total_label()
        self.transaction_search_id_entry.focus_set()
        self.load_products_to_tree() # Muat ulang produk di tab manajemen untuk menampilkan stok terbaru
        self.load_low_stock_to_tree() # Muat ulang laporan stok rendah

    def generate_and_print_receipt(self, items_in_cart, total_amount):
        """
        Menghasilkan struk transaksi dan mencoba mencetaknya ke printer Blueprint M58 
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
            receipt += b"--------------------------------\n" # Removed .encode()
            # Adjusted header for single-line item display
            receipt += b"Produk        Q x Hrg   Subtotal\n" # Removed .encode()
            receipt += b"--------------------------------\n" # Removed .encode()

            for prod_id, data in items_in_cart.items():
                name = data['name']
                qty = data['qty']
                price = data['price']
                subtotal = qty * price

                # Format string untuk setiap baris item
                price_formatted = f"{price:,.0f}" if price == int(price) else f"{price:,.2f}"
                subtotal_formatted = f"{subtotal:,.0f}" if subtotal == int(subtotal) else f"{subtotal:,.2f}"

                # Combine all item details into a single line with precise padding
                # Name: 12 chars (truncated if longer), Qty: 2 chars, Price: 6 chars, Subtotal: 7 chars
                item_line = f"{name:<12.12} {qty:>2}x{price_formatted:<6} {subtotal_formatted:>7}\n".encode()
                receipt += item_line

            receipt += b"--------------------------------\n" # Removed .encode()
            receipt += b"\x1b\x61\x02"  # Align right
            receipt += b"\x1b\x45\x01"  # Bold on
            receipt += f"TOTAL: Rp{total_amount:,.0f}\n".encode()
            receipt += b"\x1b\x45\x00"  # Bold off

            receipt += b"\x1b\x61\x01"  # Center
            receipt += b"\nTERIMA KASIH!\nSelamat Berbelanja Kembali\n" # Removed .encode()
            receipt += b"================================\n\n\n" # Removed .encode()
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
            self._save_receipt_to_file(items_in_cart, total_amount, current_time, transaction_id) # Tetap simpan ke file meskipun gagal cetak

    def _save_receipt_to_file(self, items_in_cart, total_amount, current_time, transaction_id):
        """Menyimpan detail struk ke file teks."""
        receipt_content_file = f"""
======================================
          STRUK BELANJA TOKO GRAND
======================================
Waktu Transaksi: {current_time}
ID Transaksi: {transaction_id}
--------------------------------------
No. ID Produk | Nama Produk       | Qty | Harga Satuan | Subtotal
--------------------------------------
"""
        item_no = 1
        for prod_id, data in items_in_cart.items():
            name = data['name']
            qty = data['qty']
            price = data['price']
            subtotal = qty * price
            receipt_content_file += f"{item_no:3}. {prod_id:<10} | {name:<17} | {qty:<3} | {price:12,.2f} | {subtotal:10,.2f}\n"
            item_no += 1

        receipt_content_file += f"""
--------------------------------------
TOTAL                                Rp{total_amount:,.2f}
======================================
            TERIMA KASIH!
      Selamat Berbelanja Kembali
======================================
"""
        
        # Ensure the 'receipts' directory exists
        os.makedirs('receipts', exist_ok=True)
        
        file_name = f"receipts/receipt_{transaction_id}.txt"
        try:
            with open(file_name, "w", encoding="utf-8") as f:
                f.write(receipt_content_file)
            print(f"Struk berhasil disimpan ke: {file_name}")
        except Exception as e:
            print(f"Error saat menyimpan struk ke file: {e}")

    # --- UI untuk Laporan Stok Rendah ---
    def create_low_stock_report_ui(self, parent_frame):
        """Membuat antarmuka pengguna untuk laporan stok rendah."""
        parent_frame.columnconfigure(0, weight=1)

        ttk.Label(parent_frame, text="Laporan Stok Rendah", style='Header.TLabel').pack(pady=15)

        low_stock_frame = ttk.LabelFrame(parent_frame, text="Produk dengan Stok Rendah (<= 10)", style='TLabelframe')
        low_stock_frame.pack(pady=10, padx=20, fill="both", expand=True)

        low_stock_columns = ("ID Produk", "Nama Produk", "Stok")
        self.low_stock_tree = ttk.Treeview(low_stock_frame, columns=low_stock_columns, show="headings", selectmode="browse")
        self.low_stock_tree.pack(fill="both", expand=True, padx=10, pady=10)

        for col in low_stock_columns:
            self.low_stock_tree.heading(col, text=col, anchor="center")
            self.low_stock_tree.column(col, anchor="center")
        
        self.low_stock_tree.column("ID Produk", width=100, stretch=tk.NO)
        self.low_stock_tree.column("Nama Produk", width=250, stretch=tk.YES)
        self.low_stock_tree.column("Stok", width=80, stretch=tk.NO)

        low_stock_tree_scrollbar = ttk.Scrollbar(low_stock_frame, orient="vertical", command=self.low_stock_tree.yview)
        self.low_stock_tree.configure(yscrollcommand=low_stock_tree_scrollbar.set)
        low_stock_tree_scrollbar.pack(side="right", fill="y")

        refresh_low_stock_button = ttk.Button(parent_frame, text="Refresh Laporan", command=self.load_low_stock_to_tree, style='TButton')
        refresh_low_stock_button.pack(pady=10)

        self.load_low_stock_to_tree()

    def load_low_stock_to_tree(self):
        """Memuat produk dengan stok rendah ke Treeview laporan stok."""
        for i in self.low_stock_tree.get_children():
            self.low_stock_tree.delete(i)
        
        low_stock_products = get_low_stock_products()
        if low_stock_products:
            for prod_id, name, stock in low_stock_products:
                self.low_stock_tree.insert("", "end", values=(prod_id, name, stock))
        else:
            self.low_stock_tree.insert("", "end", values=("", "Tidak ada produk dengan stok rendah.", ""))

if __name__ == "__main__":
    root = tk.Tk()
    app = POSApp(root)
    root.mainloop()
