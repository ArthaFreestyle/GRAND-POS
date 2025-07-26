import tkinter as tk
from tkinter import ttk, messagebox, Toplevel, filedialog
import sqlite3
import os
from datetime import datetime
import csv
import json # Import json for storing cart items in sales history

try:
    import win32print # This module is specific to Windows for printing.
except ImportError:
    win32print = None # Handle cases where win32print is not available (e.g., Linux/macOS)
    print("Warning: 'win32print' module not found. Printing to physical printer will not be available. Receipts will be saved to file.")

# --- Helper Function for Indonesian Currency Formatting ---
def format_currency_id(amount, include_decimals=True):
    """Formats a float as Indonesian Rupiah (RpX.XXX,XX or RpX.XXX)."""
    if not isinstance(amount, (int, float)):
        try:
            amount = float(amount)
        except (ValueError, TypeError):
            return "Rp0,00" if include_decimals else "Rp0"

    integer_part = int(amount)
    
    # Format integer part with dot as thousands separator
    # Use string formatting and then replace default comma with dot
    formatted_integer = "{:,.0f}".format(integer_part).replace(",", "#").replace(".", ",").replace("#", ".")

    if include_decimals:
        decimal_part = int(round((amount - integer_part) * 100))
        return f"Rp{formatted_integer},{decimal_part:02d}"
    else:
        return f"Rp{formatted_integer}"

# --- 1. Fungsi Database SQLite ---
def connect_db():
    """Membangun koneksi ke database SQLite."""
    conn = sqlite3.connect('pos_data.db')
    return conn

def create_table():
    """Membuat tabel 'products' jika belum ada.
    Menambahkan kolom 'stock' jika belum ada.
    """
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

    # Memastikan kolom 'stock' ada di tabel 'products'
    try:
        cursor.execute("ALTER TABLE products ADD COLUMN stock INTEGER DEFAULT 0")
        conn.commit()
    except sqlite3.OperationalError as e:
        # Menangani error jika kolom 'stock' sudah ada
        if "duplicate column name: stock" in str(e):
            pass # Kolom sudah ada, tidak perlu melakukan apa-apa
        else:
            print(f"Error saat menambahkan kolom stock: {e}")
    conn.close()

def create_sales_table():
    """Membuat tabel 'sales' jika belum ada."""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            total_amount REAL NOT NULL,
            payment REAL NOT NULL,
            change REAL NOT NULL,
            items TEXT NOT NULL -- Stored as JSON string of product_id, name, price, quantity
        )
    ''')
    conn.commit()
    conn.close()

def insert_product(product_id, name, price, stock):
    """Menambahkan produk baru ke database."""
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO products (id, name, price, stock) VALUES (?, ?, ?, ?)", (product_id, name, price, stock))
        conn.commit()
        return True, "Produk berhasil ditambahkan."
    except sqlite3.IntegrityError as e:
        if "UNIQUE constraint failed: products.id" in str(e):
            return False, f"Produk dengan ID '{product_id}' sudah ada. Harap gunakan ID lain."
        elif "UNIQUE constraint failed: products.name" in str(e):
            return False, f"Produk dengan nama '{name}' sudah ada. Harap gunakan nama lain."
        else:
            return False, f"Terjadi kesalahan database: {e}"
    finally:
        conn.close()

def get_all_products():
    """Mengambil semua produk dari database, diurutkan berdasarkan nama."""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, price, stock FROM products ORDER BY name ASC")
    products = cursor.fetchall()
    conn.close()
    return products

def get_product_by_id(product_id):
    """Mengambil produk berdasarkan ID."""
    conn = connect_db()
    cursor = conn.cursor()
    # Ensure the product_id is stripped before querying the database
    cursor.execute("SELECT id, name, price, stock FROM products WHERE id = ?", (product_id.strip(),))
    product = cursor.fetchone()
    conn.close()
    return product

def get_products_by_search_term(search_term):
    """Mengambil produk berdasarkan istilah pencarian (ID atau Nama)."""
    conn = connect_db()
    cursor = conn.cursor()
    # Use LIKE for partial matching, and COLLATE NOCASE for case-insensitive search
    cursor.execute("SELECT id, name, price, stock FROM products WHERE id LIKE ? OR name LIKE ? ORDER BY name ASC", 
                    ('%' + search_term + '%', '%' + search_term + '%'))
    products = cursor.fetchall()
    conn.close()
    return products

def delete_product_by_id(product_id):
    """Menghapus produk berdasarkan ID."""
    conn = None
    try:
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM products WHERE id = ?", (product_id,))
        conn.commit()
        return True, "Produk berhasil dihapus."
    except sqlite3.Error as e:
        print(f"Error deleting product: {e}")
        return False, f"Gagal menghapus produk: {e}"
    finally:
        if conn:
            conn.close()

def update_product_stock(product_id, new_stock):
    """Memperbarui stok produk berdasarkan ID."""
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE products SET stock = ? WHERE id = ?", (new_stock, product_id))
        conn.commit()
        return True, "Stok berhasil diperbarui."
    except sqlite3.Error as e:
        print(f"Error updating stock: {e}")
        return False, f"Gagal memperbarui stok: {e}"
    finally:
        conn.close()

def get_low_stock_products(threshold=10):
    """Mengambil produk dengan stok di bawah ambang batas tertentu."""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, stock FROM products WHERE stock <= ? ORDER BY stock ASC, name ASC", (threshold,))
    low_stock_products = cursor.fetchall()
    conn.close()
    return low_stock_products

def insert_sale(timestamp, total_amount, payment, change, items):
    """Menambahkan transaksi penjualan baru ke database."""
    conn = connect_db()
    cursor = conn.cursor()
    try:
        # items will be a JSON string of the cart contents
        cursor.execute("INSERT INTO sales (timestamp, total_amount, payment, change, items) VALUES (?, ?, ?, ?, ?)",
                       (timestamp, total_amount, payment, change, items))
        conn.commit()
        return True, "Transaksi berhasil disimpan."
    except sqlite3.Error as e:
        print(f"Error inserting sale: {e}")
        return False, f"Gagal menyimpan transaksi: {e}"
    finally:
        conn.close()

# Inisialisasi tabel saat aplikasi dimulai
create_table()
create_sales_table()

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
        # Increased font size for Cart.Treeview
        self.style.configure("Cart.Treeview", font=('Segoe UI', 18, 'bold'), rowheight=38, background='white', fieldbackground='white')
        self.style.configure("Cart.Treeview.Heading", font=('Segoe UI', 11, 'bold'), background='#3498DB', foreground='white')
        
        # Default Treeview style for others (e.g., product management)
        self.style.configure("Treeview", font=('Segoe UI', 10), rowheight=25, background='white', fieldbackground='white')
        self.style.configure("Treeview.Heading", font=('Segoe UI', 11, 'bold'), background='#3498DB', foreground='white')

        # Style for the delete button
        self.style.configure('Danger.TButton', background='#E74C3C', foreground='white', font=('Segoe UI', 10, 'bold'))
        self.style.map('Danger.TButton',
                        background=[('active', '#C0392B')],
                        foreground=[('active', 'white')])

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(expand=True, fill="both", padx=15, pady=15)

        # Tab Manajemen Produk
        self.product_frame = ttk.Frame(self.notebook, style='TFrame')
        self.notebook.add(self.product_frame, text="Manajemen Produk")
        
        # Tab Transaksi Penjualan
        self.transaction_frame = ttk.Frame(self.notebook, style='TFrame')
        self.notebook.add(self.transaction_frame, text="Transaksi Penjualan")

        # Tab Laporan Stok
        self.low_stock_frame = ttk.Frame(self.notebook, style='TFrame')
        self.notebook.add(self.low_stock_frame, text="Laporan Stok")

        # Initialize cart and total (important to do before UI creation)
        self.cart = {} # {product_id: {'name': name, 'price': price, 'quantity': quantity}}
        self.total = 0.0

        # Debounce variables for scanner input
        self.last_scanned_id = None
        self.scan_debounce_timer = None
        self.SCAN_DEBOUNCE_MS = 200 # Milliseconds to wait before processing same ID again

        # Status bar at the bottom
        self.status_label = ttk.Label(root, text="Siap.", relief=tk.SUNKEN, anchor=tk.W, font=('Segoe UI', 9))
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X, ipadx=5, ipady=2)
        self.status_clear_timer = None # To hold the ID of the after call

        # Call UI creation methods - ensure methods are defined before they are called
        self.create_product_management_ui(self.product_frame)
        self.create_transaction_ui(self.transaction_frame)
        self.create_low_stock_report_ui(self.low_stock_frame)

        # Bind F12 to complete_transaction
        self.root.bind('<F12>', self.complete_transaction_shortcut)

    def update_status(self, message, message_type='info', duration=3000):
        """Updates the status bar with a message for a given duration."""
        if self.status_clear_timer:
            self.root.after_cancel(self.status_clear_timer)
        
        color = 'black'
        if message_type == 'error':
            color = '#E74C3C' # Red
        elif message_type == 'warning':
            color = '#E67E22' # Orange
        elif message_type == 'success':
            color = '#27AE60' # Green

        self.status_label.config(text=message, foreground=color)
        self.status_clear_timer = self.root.after(duration, self._clear_status)

    def _clear_status(self):
        """Clears the status bar."""
        self.status_label.config(text="Siap.", foreground='black')

    # --- Methods for Product Management Tab ---
    def load_products_to_tree(self):
        """Memuat data produk dari database ke Treeview manajemen produk."""
        # This function now only loads ALL products.
        # Filtering is handled by apply_product_management_filter.
        for i in self.product_tree.get_children():
            self.product_tree.delete(i)
        
        products = get_all_products()
        for prod_id, name, price, stock in products:
            # Ensure prod_id is always a string when inserted into Treeview
            self.product_tree.insert("", "end", values=(str(prod_id), name, format_currency_id(price), stock))
        
        # Mengosongkan input setelah produk dimuat
        self.product_id_entry.delete(0, tk.END)
        self.product_name_entry.delete(0, tk.END)
        self.product_price_entry.delete(0, tk.END)
        self.product_stock_entry.delete(0, tk.END)
        self.product_stock_entry.insert(0, "0")
        
        # Clear the search entry when all products are reloaded
        if hasattr(self, 'product_management_search_entry'):
            self.product_management_search_entry.delete(0, tk.END)


    def apply_product_management_filter(self, event=None):
        """Melakukan pencarian langsung dan menampilkan hasilnya di treeview manajemen produk."""
        search_term = self.product_management_search_entry.get().strip()
        
        for i in self.product_tree.get_children():
            self.product_tree.delete(i)
        
        if not search_term:
            products = get_all_products() # Show all if search term is empty
        else:
            products = get_products_by_search_term(search_term)
        
        for prod_id, name, price, stock in products:
            # Ensure prod_id is always a string when inserted into Treeview
            self.product_tree.insert("", "end", values=(str(prod_id), name, format_currency_id(price), stock))

    def add_product(self):
        """Menambahkan produk baru ke database dan memperbarui Treeview."""
        product_id = self.product_id_entry.get().strip()
        name = self.product_name_entry.get().strip()
        price_str = self.product_price_entry.get().strip()
        stock_str = self.product_stock_entry.get().strip()

        if not product_id:
            self.update_status("ID Produk tidak boleh kosong.", 'warning')
            return
        if not name:
            self.update_status("Nama produk tidak boleh kosong.", 'warning')
            return
        if not price_str:
            self.update_status("Harga produk tidak boleh kosong.", 'warning')
            return
        if not stock_str:
            self.update_status("Stok awal tidak boleh kosong.", 'warning')
            return

        try:
            price = float(price_str.replace('.', '').replace(',', '.')) # Ensure correct parsing for Indonesian input
            if price <= 0:
                self.update_status("Harga harus lebih besar dari nol.", 'warning')
                return
        except ValueError:
            self.update_status("Harga harus berupa angka.", 'warning')
            return
        
        try:
            stock = int(stock_str)
            if stock < 0:
                self.update_status("Stok tidak boleh kurang dari nol.", 'warning')
                return
        except ValueError:
            self.update_status("Stok harus berupa angka bulat.", 'warning')
            return
        
        success, message = insert_product(product_id, name, price, stock)
        if success:
            self.update_status(f"Produk '{name}' (ID: {product_id}) berhasil ditambahkan.", 'success')
            # Directly insert into the treeview instead of reloading all
            # Ensure product_id is always a string when inserted into Treeview
            self.product_tree.insert("", "end", values=(str(product_id), name, format_currency_id(price), stock))
            self.live_search_products() # Update transaction tab's live search
            self.load_low_stock_to_tree() # Update low stock report
            # Clear input fields
            self.product_id_entry.delete(0, tk.END)
            self.product_name_entry.delete(0, tk.END)
            self.product_price_entry.delete(0, tk.END)
            self.product_stock_entry.delete(0, tk.END)
            self.product_stock_entry.insert(0, "0")
        else:
            self.update_status(f"Gagal menambahkan produk: {message}", 'error') # Changed to status bar

    def delete_selected_product(self):
        """Menghapus produk yang dipilih dari database dan memperbarui Treeview."""
        selected_item = self.product_tree.selection()
        if not selected_item:
            self.update_status("Pilih produk yang ingin dihapus terlebih dahulu.", 'warning')
            return
        
        product_id = self.product_tree.item(selected_item[0])['values'][0]
        product_name = self.product_tree.item(selected_item[0])['values'][1]

        if messagebox.askyesno("Konfirmasi Hapus", f"Apakah Anda yakin ingin menghapus produk '{product_name}' (ID: {product_id})?"):
            success, message = delete_product_by_id(product_id)
            if success:
                self.update_status(f"Produk '{product_name}' (ID: {product_id}) berhasil dihapus.", 'success')
                self.product_tree.delete(selected_item[0]) # Directly delete from treeview
                self.live_search_products() # Update transaction tab's live search
                self.load_low_stock_to_tree() # Update low stock report
            else:
                self.update_status(f"Gagal menghapus produk: {message}", 'error') # Changed to status bar

    def edit_selected_product_stock(self):
        """Membuka jendela baru untuk mengedit stok produk yang dipilih."""
        selected_item = self.product_tree.selection()
        if not selected_item:
            self.update_status("Pilih produk yang stoknya ingin diedit terlebih dahulu.", 'warning')
            return
        
        # Store the Treeview item ID to update it directly later
        self.selected_tree_item_id = selected_item[0]

        product_id = self.product_tree.item(selected_item[0])['values'][0]
        product_name = self.product_tree.item(selected_item[0])['values'][1]
        current_stock = self.product_tree.item(selected_item[0])['values'][3]

        edit_window = Toplevel(self.root)
        edit_window.title(f"Edit Stok: {product_name}")
        edit_window.transient(self.root)
        edit_window.grab_set()
        edit_window.resizable(False, False)

        input_frame = ttk.Frame(edit_window, padding="15")
        input_frame.pack()

        ttk.Label(input_frame, text="Nama Produk:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        ttk.Label(input_frame, text=product_name, font=('Segoe UI', 10, 'bold')).grid(row=0, column=1, padx=5, pady=5, sticky="w")

        ttk.Label(input_frame, text="Stok Saat Ini:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        ttk.Label(input_frame, text=str(current_stock), font=('Segoe UI', 10, 'bold')).grid(row=1, column=1, padx=5, pady=5, sticky="w")

        ttk.Label(input_frame, text="Stok Baru:").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        new_stock_entry = ttk.Entry(input_frame)
        new_stock_entry.grid(row=2, column=1, padx=5, pady=5, sticky="ew")
        new_stock_entry.insert(0, str(current_stock))
        new_stock_entry.focus_set()

        save_button = ttk.Button(input_frame, text="Simpan", 
                                 command=lambda: self._save_edited_stock(product_id, new_stock_entry.get(), edit_window),
                                 style='TButton')
        save_button.grid(row=3, column=0, columnspan=2, pady=10)

    def _save_edited_stock(self, product_id, new_stock_str, edit_window):
        """Menyimpan stok yang diedit ke database."""
        try:
            new_stock = int(new_stock_str.strip())
            if new_stock < 0:
                self.update_status("Stok baru tidak boleh kurang dari nol.", 'warning')
                return
        except ValueError:
            self.update_status("Stok baru harus berupa angka bulat.", 'warning')
            return
        
        success, message = update_product_stock(product_id, new_stock)
        if success:
            self.update_status(f"Stok produk ID '{product_id}' berhasil diperbarui menjadi {new_stock}.", 'success')
            # Update the specific row in the Treeview directly
            current_values = list(self.product_tree.item(self.selected_tree_item_id)['values'])
            current_values[3] = new_stock # Update the stock column
            self.product_tree.item(self.selected_tree_item_id, values=tuple(current_values))

            self.live_search_products() # Update transaction tab's live search
            self.load_low_stock_to_tree() # Update low stock report
            edit_window.destroy()
        else:
            self.update_status(f"Gagal memperbarui stok: {message}", 'error') # Changed to status bar

    def open_csv_file_dialog(self):
        """Membuka dialog untuk memilih file CSV."""
        file_path = filedialog.askopenfilename(
            title="Pilih File CSV Stok Produk",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if file_path:
            self.selected_csv_file = file_path
            self.csv_file_path_label.config(text=os.path.basename(file_path), foreground='black')
            self.update_status(f"File CSV '{os.path.basename(file_path)}' dipilih.", 'info')
        else:
            self.selected_csv_file = None
            self.csv_file_path_label.config(text="Tidak ada file terpilih", foreground='gray')
            self.update_status("Pemilihan file CSV dibatalkan.", 'info')

    def import_stock_from_csv(self):
        """Mengimpor stok produk dari file CSV yang dipilih.
        Jika ID produk tidak ada, produk baru akan ditambahkan.
        """
        if not self.selected_csv_file:
            self.update_status("Pilih file CSV terlebih dahulu.", 'warning')
            return

        updated_count = 0
        new_product_count = 0
        failed_count = 0
        error_messages = []

        try:
            with open(self.selected_csv_file, 'r', newline='', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                
                required_columns = ['ID Produk', 'Nama Produk', 'Harga', 'Stok']
                if not all(col in reader.fieldnames for col in required_columns):
                    messagebox.showerror("Format CSV Salah", # Keep as critical error
                                         f"File CSV harus memiliki kolom: {', '.join(required_columns)}.")
                    return

                for row_num, row in enumerate(reader, start=2):
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
                        success, msg = update_product_stock(product_id, stock)
                        if success:
                            updated_count += 1
                        else:
                            error_messages.append(f"Baris {row_num} (ID: {product_id}): Gagal memperbarui stok - {msg}")
                            failed_count += 1
                    else:
                        if not name or not price_str:
                            error_messages.append(f"Baris {row_num} (ID: {product_id}): Nama atau Harga kosong untuk produk baru, dilewati.")
                            failed_count += 1
                            continue
                        try:
                            price = float(price_str.replace('.', '').replace(',', '.')) # Ensure correct parsing for Indonesian input
                            if price <= 0:
                                error_messages.append(f"Baris {row_num} (ID: {product_id}): Harga tidak valid (harus > 0), dilewati.")
                                failed_count += 1
                                continue
                        except ValueError:
                            error_messages.append(f"Baris {row_num} (ID: {product_id}): Harga bukan angka, dilewati.")
                            failed_count += 1
                            continue
                        
                        success, msg = insert_product(product_id, name, price, stock)
                        if success:
                            new_product_count += 1
                        else:
                            error_messages.append(f"Baris {row_num} (ID: {product_id}): Gagal menambahkan produk baru - {msg}")
                            failed_count += 1

            summary_message = (f"Impor selesai. Diperbarui: {updated_count}, Baru: {new_product_count}, Gagal: {failed_count}.")
            self.update_status(summary_message, 'info')
            
            if error_messages:
                # Use warning for detailed errors, not critical enough for messagebox.showerror
                self.update_status("Beberapa item gagal diimpor. Lihat detail di bawah.", 'warning', duration=5000)
                # print("\n".join(error_messages)) # For debugging, if needed
                # Consider showing a separate small window for detailed errors if too long
                # For now, just print to console and give a warning status.
            
            # For CSV import, it's safer and simpler to reload all products as multiple changes can occur
            self.load_products_to_tree() 
            self.load_low_stock_to_tree() # Update low stock report
            self.live_search_products() # Update transaction tab's live search
            self.csv_file_path_label.config(text="Tidak ada file terpilih", foreground='gray')
            self.selected_csv_file = None

        except FileNotFoundError:
            messagebox.showerror("File Tidak Ditemukan", "File CSV tidak ditemukan.") # Keep as critical error
        except Exception as e:
            messagebox.showerror("Error Impor CSV", f"Terjadi kesalahan saat mengimpor CSV:\n{e}") # Keep as critical error

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
                    writer.writerow(['ID Produk', 'Nama Produk', 'Harga', 'Stok'])
                self.update_status(f"Template CSV berhasil disimpan ke: {os.path.basename(file_path)}", 'success')
            except Exception as e:
                messagebox.showerror("Error", f"Gagal menyimpan template CSV:\n{e}") # Keep as critical error

    def export_products_to_csv(self):
        """Mengekspor semua data produk ke file CSV."""
        products = get_all_products()
        if not products:
            self.update_status("Tidak ada data produk untuk diekspor.", 'warning')
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
                    writer.writerow(['ID Produk', 'Nama Produk', 'Harga', 'Stok'])
                    for prod_id, name, price, stock in products:
                        writer.writerow([prod_id, name, price, stock])
                self.update_status(f"Data produk berhasil diekspor ke: {os.path.basename(file_path)}", 'success')
            except Exception as e:
                messagebox.showerror("Error", f"Gagal mengekspor data produk ke CSV:\n{e}") # Keep as critical error

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
        self.product_stock_entry.insert(0, "0")
        self.product_stock_entry.grid(row=3, column=1, padx=10, pady=5, sticky="ew")

        add_button = ttk.Button(input_frame, text="Tambah Produk", command=self.add_product, style='TButton')
        add_button.grid(row=4, column=0, columnspan=2, pady=15, padx=10)

        # --- Live Search in Product Management ---
        search_frame = ttk.LabelFrame(parent_frame, text="Cari Produk (ID/Nama)", style='TLabelframe')
        search_frame.pack(pady=10, padx=20, fill="x")
        search_frame.columnconfigure(1, weight=1)

        ttk.Label(search_frame, text="Cari:").grid(row=0, column=0, padx=10, pady=5, sticky="w")
        self.product_management_search_entry = ttk.Entry(search_frame)
        self.product_management_search_entry.grid(row=0, column=1, padx=10, pady=5, sticky="ew")
        self.product_management_search_entry.bind('<KeyRelease>', self.apply_product_management_filter)
        # --- End Live Search in Product Management ---

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

        delete_button = ttk.Button(button_frame, text="Hapus Produk Terpilih", command=self.delete_selected_product, style='Danger.TButton')
        delete_button.pack(side="left", padx=5)

        edit_stock_button = ttk.Button(button_frame, text="Edit Stok Terpilih", command=self.edit_selected_product_stock, style='TButton')
        edit_stock_button.pack(side="left", padx=5)

        csv_frame = ttk.LabelFrame(parent_frame, text="Impor/Ekspor Data Produk (CSV)", style='TLabelframe')
        csv_frame.pack(pady=10, padx=20, fill="x")
        csv_frame.columnconfigure(0, weight=1)
        csv_frame.columnconfigure(1, weight=1)

        ttk.Label(csv_frame, text="Impor Stok dari CSV:").grid(row=0, column=0, padx=10, pady=5, sticky="w")
        self.csv_file_path_label = ttk.Label(csv_frame, text="Tidak ada file terpilih", foreground='gray')
        self.csv_file_path_label.grid(row=0, column=1, padx=10, pady=5, sticky="ew")

        self.select_csv_button = ttk.Button(csv_frame, text="Pilih File CSV", command=self.open_csv_file_dialog, style='TButton')
        self.select_csv_button.grid(row=1, column=0, padx=10, pady=5, sticky="ew")

        self.import_stock_button = ttk.Button(csv_frame, text="Update Stok dari CSV", command=self.import_stock_from_csv, style='TButton')
        self.import_stock_button.grid(row=1, column=1, padx=10, pady=5, sticky="ew")

        ttk.Separator(csv_frame, orient="horizontal").grid(row=2, columnspan=2, sticky="ew", pady=10)

        self.download_template_button = ttk.Button(csv_frame, text="Download Template CSV", command=self.download_csv_template, style='TButton')
        self.download_template_button.grid(row=3, column=0, padx=10, pady=5, sticky="ew")

        self.export_data_button = ttk.Button(csv_frame, text="Export Data Produk ke CSV", command=self.export_products_to_csv, style='TButton')
        self.export_data_button.grid(row=3, column=1, padx=10, pady=5, sticky="ew")

        self.load_products_to_tree() # Initial load of all products

    # --- Methods for Transaction Tab ---
    def process_product_id_input(self, event=None, product_id_override=None):
        """Memproses input ID produk dari barcode scanner atau manual entry.
        product_id_override digunakan saat memanggil fungsi ini secara internal (misal dari edit quantity).
        """
        if product_id_override:
            product_id = product_id_override.strip() # Ensure stripped even if overridden
        else:
            product_id = self.transaction_search_id_entry.get().strip()

            # Debounce mechanism for scanner input
            # Only debounce if product_id is not empty and it's the same as the last scanned ID
            if product_id and product_id == self.last_scanned_id: 
                if self.scan_debounce_timer:
                    self.root.after_cancel(self.scan_debounce_timer)
                self.scan_debounce_timer = self.root.after(self.SCAN_DEBOUNCE_MS, lambda: setattr(self, 'last_scanned_id', None)) # Clear after delay
                self.update_status(f"Scan cepat terdeteksi, mengabaikan duplikat '{product_id}'.", 'info', 1500)
                self.transaction_search_id_entry.delete(0, tk.END) # Clear the entry even if debounced
                return
            self.last_scanned_id = product_id
            # Reset last_scanned_id after a short delay to allow new scans
            self.scan_debounce_timer = self.root.after(self.SCAN_DEBOUNCE_MS, lambda: setattr(self, 'last_scanned_id', None))

        if not product_id:
            self.found_product_name_label.config(text="-")
            self.found_product_price_label.config(text=format_currency_id(0.00, include_decimals=False))
            self.found_product_stock_label.config(text="0")
            self.update_status("Masukkan ID produk.", 'info')
            if not product_id_override:
                self.transaction_search_id_entry.focus_set()
            return

        product = get_product_by_id(product_id) # get_product_by_id now handles stripping
        if product:
            prod_id, name, price, stock = product
            self.found_product_name_label.config(text=name)
            self.found_product_price_label.config(text=format_currency_id(price, include_decimals=False))
            
            # Calculate available stock considering items already in cart
            current_cart_quantity = self.cart.get(prod_id, {}).get('quantity', 0)
            available_for_sale_stock = stock - current_cart_quantity
            self.found_product_stock_label.config(text=str(available_for_sale_stock))
            
            if not product_id_override and available_for_sale_stock > 0: # Only add to cart if it's a new scan/manual input
                self.add_to_cart(prod_id, name, price)
            elif not product_id_override: # If it's a new scan/manual input but stock is 0
                self.update_status(f"Stok untuk '{name}' (ID: {prod_id}) sudah habis atau sudah di keranjang.", 'warning')
        else:
            self.found_product_name_label.config(text="Produk Tidak Ditemukan")
            self.found_product_price_label.config(text=format_currency_id(0.00, include_decimals=False))
            self.found_product_stock_label.config(text="0")
            self.update_status(f"Produk dengan ID '{product_id}' tidak ditemukan.", 'warning')
        
        if not product_id_override: # Only clear entry if it was a manual input/scan
            self.transaction_search_id_entry.delete(0, tk.END)
            self.transaction_search_id_entry.focus_set()

    def live_search_products(self, event=None):
        """Melakukan pencarian produk secara langsung dan menampilkan hasilnya di treeview."""
        search_term = self.live_search_entry.get().strip()
        
        for i in self.live_search_tree.get_children():
            self.live_search_tree.delete(i)
        
        if not search_term:
            products = get_all_products()
        else:
            products = get_products_by_search_term(search_term)
        
        for prod_id, name, price, stock in products:
            # Display available stock considering items already in cart
            current_cart_quantity = self.cart.get(str(prod_id).strip(), {}).get('quantity', 0) # Ensure prod_id is stripped for cart lookup
            available_for_sale_stock = stock - current_cart_quantity
            # Ensure prod_id is always a string when inserted into Treeview
            self.live_search_tree.insert("", "end", values=(str(prod_id), name, format_currency_id(price, include_decimals=False), available_for_sale_stock))

    def add_selected_product_from_search(self, event=None):
        """Menambahkan produk yang dipilih dari live search treeview ke keranjang."""
        selected_item = self.live_search_tree.selection()
        if not selected_item:
            return

        # Explicitly convert to string before stripping
        prod_id = str(self.live_search_tree.item(selected_item[0])['values'][0]).strip() 
        name = self.live_search_tree.item(selected_item[0])['values'][1]
        price_str = self.live_search_tree.item(selected_item[0])['values'][2]
        stock_display = self.live_search_tree.item(selected_item[0])['values'][3] # This is already available_for_sale_stock

        # Convert price string (e.g., "Rp10.000") to float
        price = float(price_str.replace('Rp', '').replace('.', '').replace(',', '.'))
        
        if stock_display > 0: # Check against the displayed available stock
            self.add_to_cart(prod_id, name, price)
        else:
            self.update_status(f"Stok untuk '{name}' (ID: {prod_id}) sudah habis atau sudah di keranjang.", 'warning')

    def add_to_cart(self, product_id, name, price):
        """Menambahkan produk ke keranjang atau menambah jumlah jika sudah ada."""
        product_id = product_id.strip() # Ensure product_id is stripped consistently
        db_product = get_product_by_id(product_id) # get_product_by_id now handles stripping
        if not db_product:
            self.update_status("Produk tidak ditemukan di database.", 'error')
            return
        
        database_stock = db_product[3]

        if product_id in self.cart:
            if self.cart[product_id]['quantity'] < database_stock:
                self.cart[product_id]['quantity'] += 1
                self.update_status(f"Jumlah '{name}' di keranjang ditambahkan.", 'success')
            else:
                self.update_status(f"Tidak bisa menambahkan lebih banyak '{name}'. Stok maksimal tercapai ({database_stock}).", 'warning')
        else:
            if database_stock > 0:
                self.cart[product_id] = {'name': name, 'price': price, 'quantity': 1}
                self.update_status(f"'{name}' ditambahkan ke keranjang.", 'success')
            else:
                self.update_status(f"Stok untuk '{name}' sudah habis.", 'warning')
                return

        self.update_cart_display_and_total()
        # Update the displayed stock for the currently selected/scanned product
        # Ensure that the product_id passed here is also stripped
        current_input_id = self.transaction_search_id_entry.get().strip()
        if current_input_id:
            self.process_product_id_input(product_id_override=current_input_id)
        
        # Update live search results to reflect current cart quantities (stock available for sale)
        self.live_search_products()

    def adjust_cart_item_quantity(self, change):
        """Menambah atau mengurangi jumlah item di keranjang."""
        selected_item = self.cart_tree.selection()
        if not selected_item:
            self.update_status("Pilih item di keranjang terlebih dahulu.", 'warning')
            return
        
        selected_item_id = selected_item[0] # Store the Treeview item ID
        # Explicitly convert to string before stripping
        product_id = str(self.cart_tree.item(selected_item_id)['text']).strip() # Get product_id from 'text' and strip
        
        if product_id in self.cart:
            current_quantity = self.cart[product_id]['quantity']
            new_quantity = current_quantity + change

            db_product = get_product_by_id(product_id) # get_product_by_id now handles stripping
            database_stock = db_product[3] if db_product else 0

            if new_quantity > 0:
                if new_quantity <= database_stock:
                    self.cart[product_id]['quantity'] = new_quantity
                    self.update_status(f"Jumlah '{self.cart[product_id]['name']}' di keranjang diubah menjadi {new_quantity}.", 'success')
                    self.update_cart_display_and_total()
                    self.cart_tree.selection_set(selected_item_id) # Re-select the item
                    self.cart_tree.focus(selected_item_id) # Focus on the item
                else:
                    self.update_status(f"Tidak bisa menambahkan lebih banyak '{self.cart[product_id]['name']}'. Stok maksimal tercapai ({database_stock}).", 'warning')
            else:
                self.remove_from_cart() # This will trigger its own confirmation
                return

            # Update the displayed stock for the currently selected/scanned product if it matches
            current_input_id = self.transaction_search_id_entry.get().strip()
            if current_input_id:
                self.process_product_id_input(product_id_override=current_input_id)
            
            # Update live search results to reflect current cart quantities (stock available for sale)
            self.live_search_products()

    def edit_cart_item_quantity(self):
        """Membuka jendela baru untuk mengedit jumlah item di keranjang."""
        selected_item = self.cart_tree.selection()
        if not selected_item:
            self.update_status("Pilih item di keranjang yang ingin diedit jumlahnya terlebih dahulu.", 'warning')
            return
        
        selected_item_id = selected_item[0]
        # Explicitly convert to string before stripping
        product_id = str(self.cart_tree.item(selected_item_id)['text']).strip() # Get product_id from 'text' and strip
        product_name = self.cart_tree.item(selected_item_id)['values'][0] # Name is now at index 0 of values
        current_quantity = self.cart_tree.item(selected_item_id)['values'][2] # Quantity is now at index 2 of values

        edit_window = Toplevel(self.root)
        edit_window.title(f"Edit Jumlah: {product_name}")
        edit_window.transient(self.root)
        edit_window.grab_set()
        edit_window.resizable(False, False)

        input_frame = ttk.Frame(edit_window, padding="15")
        input_frame.pack()

        ttk.Label(input_frame, text="Nama Produk:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        ttk.Label(input_frame, text=product_name, font=('Segoe UI', 10, 'bold')).grid(row=0, column=1, padx=5, pady=5, sticky="w")

        ttk.Label(input_frame, text="Jumlah Saat Ini:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        ttk.Label(input_frame, text=str(current_quantity), font=('Segoe UI', 10, 'bold')).grid(row=1, column=1, padx=5, pady=5, sticky="w")

        ttk.Label(input_frame, text="Jumlah Baru:").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        new_quantity_entry = ttk.Entry(input_frame)
        new_quantity_entry.grid(row=2, column=1, padx=5, pady=5, sticky="ew")
        new_quantity_entry.insert(0, str(current_quantity))
        new_quantity_entry.focus_set()

        save_button = ttk.Button(input_frame, text="Simpan", 
                                 command=lambda: self._save_edited_cart_quantity(product_id, new_quantity_entry.get(), edit_window, selected_item_id),
                                 style='TButton')
        save_button.grid(row=3, column=0, columnspan=2, pady=10)

    def _save_edited_cart_quantity(self, product_id, new_quantity_str, edit_window, tree_item_id):
        """Menyimpan jumlah item yang diedit ke keranjang."""
        product_id = product_id.strip() # Ensure product_id is stripped consistently
        try:
            new_quantity = int(new_quantity_str.strip())
            if new_quantity < 0:
                self.update_status("Jumlah baru tidak boleh kurang dari nol.", 'warning')
                return
        except ValueError:
            self.update_status("Jumlah baru harus berupa angka bulat.", 'warning')
            return
        
        db_product = get_product_by_id(product_id) # get_product_by_id now handles stripping
        database_stock = db_product[3] if db_product else 0

        if new_quantity > database_stock:
            self.update_status(f"Jumlah baru ({new_quantity}) melebihi stok tersedia ({database_stock}).", 'warning')
            return
        
        if new_quantity == 0:
            if messagebox.askyesno("Konfirmasi Hapus", f"Apakah Anda yakin ingin menghapus '{self.cart[product_id]['name']}' dari keranjang (jumlah menjadi 0)?"):
                del self.cart[product_id]
                self.update_status(f"'{db_product[1]}' berhasil dihapus dari keranjang.", 'success') # Use db_product name as cart might be deleted
            else:
                return # User cancelled deletion
        else:
            self.cart[product_id]['quantity'] = new_quantity
            self.update_status(f"Jumlah '{self.cart[product_id]['name']}' di keranjang diperbarui menjadi {new_quantity}.", 'success')
        
        self.update_cart_display_and_total()
        # Re-select the item if it still exists (not deleted by setting quantity to 0)
        if product_id in self.cart:
            # Find the new tree_item_id if it was recreated (due to clear-and-repopulate)
            new_tree_item_id = None
            for item_id in self.cart_tree.get_children():
                if self.cart_tree.item(item_id)['text'] == product_id:
                    new_tree_item_id = item_id
                    break
            if new_tree_item_id:
                self.cart_tree.selection_set(new_tree_item_id)
                self.cart_tree.focus(new_tree_item_id)

        # Update the displayed stock for the currently selected/scanned product
        current_input_id = self.transaction_search_id_entry.get().strip()
        if current_input_id:
            self.process_product_id_input(product_id_override=current_input_id)
        
        # Update live search results to reflect current cart quantities (stock available for sale)
        self.live_search_products()
        edit_window.destroy()

    def remove_from_cart(self):
        """Menghapus item dari keranjang."""
        selected_item = self.cart_tree.selection()
        if not selected_item:
            self.update_status("Pilih item yang ingin dihapus dari keranjang.", 'warning')
            return
        
        selected_item_id = selected_item[0] # Store the Treeview item ID
        # Explicitly convert to string before stripping
        product_id = str(self.cart_tree.item(selected_item_id)['text']).strip() # Get product_id from 'text' and strip
        product_name = self.cart_tree.item(selected_item_id)['values'][0] # Name is now at index 0 of values

        if messagebox.askyesno("Konfirmasi Hapus", f"Apakah Anda yakin ingin menghapus '{product_name}' dari keranjang?"):
            if product_id in self.cart:
                del self.cart[product_id]
                self.update_status(f"'{product_name}' berhasil dihapus dari keranjang.", 'success')
                self.update_cart_display_and_total()
                
                # Update the displayed stock for the currently selected/scanned product if it matches
                current_input_id = self.transaction_search_id_entry.get().strip()
                if current_input_id:
                    self.process_product_id_input(product_id_override=current_input_id)

                # Update live search results to reflect current cart quantities (stock available for sale)
                self.live_search_products()

    def update_cart_display_and_total(self):
        """Memperbarui tampilan keranjang dan menghitung ulang total.
        Menggunakan pendekatan yang lebih efisien untuk memperbarui Treeview
        tanpa menghapus dan menambahkan ulang semua item.
        """
        # Get current selection's product_id to re-select after update
        selected_prod_id = None
        if self.cart_tree.selection():
            selected_item_id = self.cart_tree.selection()[0]
            # Explicitly convert to string before stripping
            selected_prod_id = str(self.cart_tree.item(selected_item_id)['text']).strip()

        # Create a map of product_id to current Treeview item ID for quick lookup
        # Ensure product_id from Treeview is also stripped for consistent mapping
        tree_items_map = {str(self.cart_tree.item(item_id)['text']).strip(): item_id for item_id in self.cart_tree.get_children()}
        
        self.total = 0.0
        newly_selected_item_id = None

        # First pass: Add/Update items in Treeview based on self.cart
        for prod_id, item_data in self.cart.items():
            prod_id = prod_id.strip() # Ensure consistency for map key
            name = item_data['name']
            price = item_data['price']
            quantity = item_data['quantity']
            subtotal = price * quantity
            self.total += subtotal

            if prod_id in tree_items_map:
                # Item exists, update its values
                item_id = tree_items_map[prod_id]
                self.cart_tree.item(item_id, values=(name, format_currency_id(price, include_decimals=False), 
                                                        quantity, format_currency_id(subtotal, include_decimals=False)))
                if prod_id == selected_prod_id:
                    newly_selected_item_id = item_id
                del tree_items_map[prod_id] # Mark as processed
            else:
                # Item is new, insert it
                new_item_id = self.cart_tree.insert("", "end", text=prod_id, 
                                                    values=(name, format_currency_id(price, include_decimals=False), 
                                                            quantity, format_currency_id(subtotal, include_decimals=False)))
                if prod_id == selected_prod_id:
                    newly_selected_item_id = new_item_id
        
        # Second pass: Remove items from Treeview that are no longer in self.cart
        # These are the remaining items in tree_items_map
        for prod_id_to_remove in tree_items_map:
            self.cart_tree.delete(tree_items_map[prod_id_to_remove])

        self.total_label.config(text=format_currency_id(self.total, include_decimals=False))

        # Re-select the item that was previously selected, if it still exists
        if newly_selected_item_id:
            self.cart_tree.selection_set(newly_selected_item_id)
            self.cart_tree.focus(newly_selected_item_id)
        elif self.cart_tree.get_children(): # If no specific item was selected, but there are items, select the first one
             self.cart_tree.selection_set(self.cart_tree.get_children()[0])
             self.cart_tree.focus(self.cart_tree.get_children()[0])


    def complete_transaction_shortcut(self, event=None):
        """Wrapper method for F12 shortcut to complete transaction."""
        self.complete_transaction()

    def complete_transaction(self):
        """Menyelesaikan transaksi, memperbarui stok, dan mencetak struk."""
        self.update_status("Memproses transaksi...", 'info', duration=5000)

        if not self.cart:
            self.update_status("Keranjang belanja kosong. Tambahkan produk terlebih dahulu.", 'warning')
            return
        
        # No payment input, assume payment is exact (or handled externally)
        payment_amount = self.total
        change = 0.0 # Always 0 since payment is assumed exact

        # No messagebox.askyesno here, directly proceed to process transaction
        
        # 1. Update stock in database
        stock_update_success = True
        for prod_id, item_data in self.cart.items():
            quantity_sold = item_data['quantity']
            current_product_in_db = get_product_by_id(prod_id) # get_product_by_id now handles stripping
            if current_product_in_db:
                current_stock = current_product_in_db[3]
                new_stock = current_stock - quantity_sold
                success, msg = update_product_stock(prod_id, new_stock)
                if not success:
                    stock_update_success = False
                    print(f"Error updating stock for {prod_id}: {msg}") # Log error
                    self.update_status(f"Gagal memperbarui stok untuk {item_data['name']}: {msg}. Transaksi dibatalkan.", 'error', duration=7000)
                    return # Abort transaction if stock update fails
            else:
                stock_update_success = False
                print(f"Warning: Product {prod_id} not found in DB during stock update.")
                self.update_status(f"Produk '{item_data['name']}' tidak ditemukan saat memperbarui stok. Transaksi dibatalkan.", 'error', duration=7000)
                return # Abort transaction if product not found

        if not stock_update_success:
            self.update_status("Transaksi dibatalkan karena masalah stok.", 'error', duration=7000)
            return

        # 2. Record sale in sales history
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        items_json = json.dumps(self.cart) 
        success, message = insert_sale(timestamp, self.total, payment_amount, change, items_json)

        if success:
            self.update_status("Transaksi berhasil diselesaikan!", 'success')
            self.print_receipt(self.cart, self.total, payment_amount, change, timestamp)

            # 3. Reset UI
            self.cart = {}
            self.update_cart_display_and_total()
            # Removed payment_entry and change_label reset
            self.found_product_name_label.config(text="-")
            self.found_product_price_label.config(text=format_currency_id(0.00, include_decimals=False))
            self.found_product_stock_label.config(text="0")
            self.transaction_search_id_entry.delete(0, tk.END)
            self.live_search_entry.delete(0, tk.END)
            
            # These reloads are necessary here as database stock has changed
            self.load_products_to_tree() # Refresh product management tree
            self.load_low_stock_to_tree() # Refresh low stock report
            self.live_search_products() # Refresh live search in transaction tab
        else:
            self.update_status(f"Gagal mencatat transaksi: {message}", 'error', duration=7000)


    def print_receipt(self, cart_items, total, payment, change, timestamp):
        """Mencetak struk transaksi."""
        # Define a general line width for centering based on 58mm paper (approx 32 chars)
        LINE_WIDTH = 32 
        ADDRESS_LINE_1 = "Jl. Moh Saleh Bantilan"
        ADDRESS_LINE_2 = "(Depan Pasar Sandana)"

        receipt_content = f"--------------------------------\n" # 32 dashes
        receipt_content += f"{'Toko GRAND':^{LINE_WIDTH}}\n" # Centered, no bolding simulation
        receipt_content += f"{ADDRESS_LINE_1:^{LINE_WIDTH}}\n"
        receipt_content += f"{ADDRESS_LINE_2:^{LINE_WIDTH}}\n"
        receipt_content += f"{timestamp:^{LINE_WIDTH}}\n"
        
        # Space between header and body
        receipt_content += "\n\n" # Add 2 newlines for spacing
        
        receipt_content += f"--------------------------------\n" # 32 dashes

        for prod_id, item_data in cart_items.items():
            name = item_data['name']
            price = item_data['price']
            quantity = item_data['quantity']
            subtotal = price * quantity

            # Item name line (without ID)
            receipt_content += f"{name}\n" 
            # Format quantity, unit price, and subtotal, right-aligned
            qty_price_subtotal_line = (
                f"{quantity} x {format_currency_id(price, include_decimals=False)} = {format_currency_id(subtotal, include_decimals=False)}"
            )
            # Ensure this line is right-aligned to the LINE_WIDTH
            receipt_content += f"{qty_price_subtotal_line:>{LINE_WIDTH}}\n"
        
        # Space between body and footer
        receipt_content += "\n" # Add 1 newline for spacing

        receipt_content += f"--------------------------------\n" # 32 dashes
        # Total line, right-aligned
        receipt_content += f"{'TOTAL: ' + format_currency_id(total, include_decimals=False):>{LINE_WIDTH}}\n"
        receipt_content += f"--------------------------------\n" # 32 dashes
        receipt_content += f"{'Terima Kasih!':^{LINE_WIDTH}}\n" # Center the thank you message
        receipt_content += f"--------------------------------\n" # 32 dashes

        # Space at the very bottom for tearing
        receipt_content += "\n\n\n\n\n" # Add 5 newlines for tearing

        try:
            if win32print: # Check if win32print module was imported successfully
                printer_name = "Blueprint_M58" # Use the specified printer name
                # You might want to add a check here if the specified printer exists
                # For simplicity, we'll assume it exists or rely on win32print's error handling
                hPrinter = win32print.OpenPrinter(printer_name)
                try:
                    hJob = win32print.StartDocPrinter(hPrinter, 1, ("Struk Belanja", None, "RAW"))
                    try:
                        win32print.StartPagePrinter(hPrinter)
                        # Encode to bytes for printer
                        win32print.WritePrinter(hPrinter, receipt_content.encode('utf-8'))
                        win32print.EndPagePrinter(hPrinter)
                    finally:
                        win32print.EndDocPrinter(hPrinter)
                finally:
                    win32print.ClosePrinter(hPrinter)
                self.update_status(f"Struk berhasil dikirim ke printer '{printer_name}'.", 'success')
            else:
                self._save_receipt_to_file(receipt_content)
        except Exception as e:
            self.update_status(f"Gagal mencetak struk ke printer: {e}. Struk akan disimpan ke file.", 'warning')
            self._save_receipt_to_file(content) # Pass content directly

    def _save_receipt_to_file(self, content):
        """Menyimpan konten struk ke file teks."""
        try:
            if not os.path.exists("receipts"):
                os.makedirs("receipts")
            
            filename = datetime.now().strftime("receipt_%Y%m%d_%H%M%S.txt")
            filepath = os.path.join("receipts", filename)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            self.update_status(f"Struk berhasil disimpan ke: {os.path.basename(filepath)}", 'success')
        except Exception as e:
            messagebox.showerror("Error", f"Gagal menyimpan struk ke file:\n{e}") # Keep this as critical error

    def create_transaction_ui(self, parent_frame):
        """Membuat antarmuka pengguna untuk transaksi penjualan."""
        parent_frame.columnconfigure(0, weight=1)
        parent_frame.columnconfigure(1, weight=1)
        
        parent_frame.rowconfigure(0, weight=0)
        parent_frame.rowconfigure(1, weight=1)
        parent_frame.rowconfigure(2, weight=0) # Row for total
        parent_frame.rowconfigure(3, weight=0) # Row for complete transaction button

        ttk.Label(parent_frame, text="Transaksi Penjualan", style='Header.TLabel').grid(row=0, column=0, columnspan=2, pady=15, sticky="ew")

        left_panel_frame = ttk.Frame(parent_frame, style='TFrame')
        left_panel_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)
        left_panel_frame.columnconfigure(0, weight=1)
        left_panel_frame.rowconfigure(1, weight=1)

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
        self.found_product_price_label = ttk.Label(search_id_transaction_frame, text=format_currency_id(0.00, include_decimals=False), font=('Segoe UI', 10, 'bold'), foreground='#2980B9')
        self.found_product_price_label.grid(row=2, column=1, padx=10, pady=5, sticky="w", columnspan=2)

        ttk.Label(search_id_transaction_frame, text="Stok Tersedia (di luar keranjang):").grid(row=3, column=0, padx=10, pady=5, sticky="w") # Updated label
        self.found_product_stock_label = ttk.Label(search_id_transaction_frame, text="0", font=('Segoe UI', 10, 'bold'), foreground='#E67E22')
        self.found_product_stock_label.grid(row=3, column=1, padx=10, pady=5, sticky="w", columnspan=2)

        live_search_frame = ttk.LabelFrame(left_panel_frame, text="Cari Produk (Live Search)", style='TLabelframe')
        live_search_frame.grid(row=1, column=0, sticky="nsew")
        live_search_frame.columnconfigure(0, weight=1)
        live_search_frame.columnconfigure(1, weight=1) 
        live_search_frame.rowconfigure(1, weight=1)

        ttk.Label(live_search_frame, text="Cari Nama/ID:").grid(row=0, column=0, padx=10, pady=5, sticky="w")
        self.live_search_entry = ttk.Entry(live_search_frame)
        self.live_search_entry.grid(row=0, column=1, padx=10, pady=5, sticky="ew")
        self.live_search_entry.bind('<KeyRelease>', self.live_search_products)

        search_results_columns = ("ID", "Nama Produk", "Harga", "Stok")
        self.live_search_tree = ttk.Treeview(live_search_frame, columns=search_results_columns, show="headings", selectmode="browse")
        self.live_search_tree.grid(row=1, column=0, columnspan=2, padx=10, pady=5, sticky="nsew")

        for col in search_results_columns:
            self.live_search_tree.heading(col, text=col, anchor="center")
            self.live_search_tree.column(col, anchor="center")
        
        self.live_search_tree.column("ID", width=80, stretch=tk.NO)
        self.live_search_tree.column("Nama Produk", width=200, stretch=tk.YES)
        self.live_search_tree.column("Harga", width=100, stretch=tk.NO)
        self.live_search_tree.column("Stok", width=70, stretch=tk.NO)

        live_search_tree_scrollbar = ttk.Scrollbar(live_search_frame, orient="vertical", command=self.live_search_tree.yview)
        self.live_search_tree.configure(yscrollcommand=live_search_tree_scrollbar.set)
        live_search_tree_scrollbar.grid(row=1, column=2, sticky="ns")

        self.live_search_tree.bind('<<TreeviewSelect>>', self.add_selected_product_from_search)

        cart_frame = ttk.LabelFrame(parent_frame, text="Keranjang Belanja", style='TLabelframe')
        cart_frame.grid(row=1, column=1, sticky="nsew", padx=20, pady=10)
        cart_frame.columnconfigure(0, weight=1)
        cart_frame.rowconfigure(0, weight=1)

        # Define visible columns for the cart Treeview
        cart_columns_visible = ("Nama Produk", "Harga", "Jumlah", "Subtotal") 
        self.cart_tree = ttk.Treeview(cart_frame, columns=cart_columns_visible, show="headings", style="Cart.Treeview")
        self.cart_tree.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        # Configure the hidden #0 column (which stores product_id as 'text')
        self.cart_tree.column("#0", width=0, stretch=tk.NO) # Hide the default first column

        # Configure visible columns with updated widths and centering
        self.cart_tree.heading("Nama Produk", text="Nama Produk", anchor="center")
        self.cart_tree.column("Nama Produk", width=180, stretch=tk.YES, anchor="center") 
        self.cart_tree.heading("Harga", text="Harga", anchor="center")
        self.cart_tree.column("Harga", width=180, stretch=tk.NO, anchor="center") # Increased width
        self.cart_tree.heading("Jumlah", text="Jumlah", anchor="center")
        self.cart_tree.column("Jumlah", width=60, stretch=tk.NO, anchor="center") 
        self.cart_tree.heading("Subtotal", text="Subtotal", anchor="center")
        self.cart_tree.column("Subtotal", width=200, stretch=tk.NO, anchor="center") # Increased width

        cart_tree_scrollbar = ttk.Scrollbar(cart_frame, orient="vertical", command=self.cart_tree.yview)
        self.cart_tree.configure(yscrollcommand=cart_tree_scrollbar.set)
        cart_tree_scrollbar.grid(row=0, column=1, sticky="ns")

        cart_buttons_frame = ttk.Frame(cart_frame, style='TFrame')
        cart_buttons_frame.grid(row=1, column=0, columnspan=2, pady=5, sticky="ew")
        cart_buttons_frame.columnconfigure(0, weight=1)
        cart_buttons_frame.columnconfigure(1, weight=1)
        cart_buttons_frame.columnconfigure(2, weight=1)
        cart_buttons_frame.columnconfigure(3, weight=1) # For new edit button

        ttk.Button(cart_buttons_frame, text="Tambah Jumlah", command=lambda: self.adjust_cart_item_quantity(1), style='TButton').grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        ttk.Button(cart_buttons_frame, text="Kurangi Jumlah", command=lambda: self.adjust_cart_item_quantity(-1), style='TButton').grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        ttk.Button(cart_buttons_frame, text="Edit Jumlah", command=self.edit_cart_item_quantity, style='TButton').grid(row=0, column=2, padx=5, pady=5, sticky="ew") # New button
        ttk.Button(cart_buttons_frame, text="Hapus Item", command=self.remove_from_cart, style='Danger.TButton').grid(row=0, column=3, padx=5, pady=5, sticky="ew")

        total_payment_frame = ttk.Frame(parent_frame, style='TFrame')
        total_payment_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=20, pady=10)
        total_payment_frame.columnconfigure(1, weight=1)

        ttk.Label(total_payment_frame, text="Total Belanja:", font=('Segoe UI', 18, 'bold')).grid(row=0, column=0, padx=10, pady=5, sticky="w")
        self.total_label = ttk.Label(total_payment_frame, text=format_currency_id(0.00, include_decimals=False), style='Total.TLabel')
        self.total_label.grid(row=0, column=1, padx=10, pady=5, sticky="e")

        # Removed Jumlah Bayar and Kembalian UI elements
        # ttk.Label(total_payment_frame, text="Jumlah Bayar (Rp):", font=('Segoe UI', 12)).grid(row=1, column=0, padx=10, pady=5, sticky="w")
        # self.payment_entry = ttk.Entry(total_payment_frame, font=('Segoe UI', 12))
        # self.payment_entry.grid(row=1, column=1, padx=10, pady=5, sticky="ew")
        # self.payment_entry.bind('<KeyRelease>', self.calculate_change)

        # ttk.Label(total_payment_frame, text="Kembalian:", font=('Segoe UI', 12)).grid(row=2, column=0, padx=10, pady=5, sticky="w")
        # self.change_label = ttk.Label(total_payment_frame, text=format_currency_id(0.00, include_decimals=False), font=('Segoe UI', 14, 'bold'), foreground='#27AE60')
        # self.change_label.grid(row=2, column=1, padx=10, pady=5, sticky="e")

        complete_transaction_button = ttk.Button(parent_frame, text="Selesaikan Transaksi", command=self.complete_transaction, style='TButton')
        complete_transaction_button.grid(row=3, column=0, columnspan=2, pady=15, padx=20, sticky="ew")

        self.live_search_products()

    # --- Methods for Low Stock Report Tab ---
    def load_low_stock_to_tree(self):
        """Memuat data produk dengan stok rendah ke Treeview laporan stok."""
        for i in self.low_stock_tree.get_children():
            self.low_stock_tree.delete(i)
        
        low_stock_products = get_low_stock_products()
        if not low_stock_products:
            self.low_stock_tree.insert("", "end", values=("", "Tidak ada produk dengan stok rendah.", ""))
        else:
            for prod_id, name, stock in low_stock_products:
                self.low_stock_tree.insert("", "end", values=(prod_id, name, stock))

    def create_low_stock_report_ui(self, parent_frame):
        """Membuat antarmuka pengguna untuk laporan stok rendah."""
        parent_frame.columnconfigure(0, weight=1)

        ttk.Label(parent_frame, text="Laporan Stok Produk Rendah", style='Header.TLabel').pack(pady=15)

        report_frame = ttk.LabelFrame(parent_frame, text="Produk dengan Stok Rendah (Ambang Batas: 10)", style='TLabelframe')
        report_frame.pack(pady=10, padx=20, fill="both", expand=True)
        report_frame.columnconfigure(0, weight=1)
        report_frame.rowconfigure(0, weight=1)

        low_stock_columns = ("ID", "Nama Produk", "Stok")
        self.low_stock_tree = ttk.Treeview(report_frame, columns=low_stock_columns, show="headings", selectmode="browse")
        self.low_stock_tree.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        for col in low_stock_columns:
            self.low_stock_tree.heading(col, text=col, anchor="center")
            self.low_stock_tree.column(col, anchor="center")
        
        self.low_stock_tree.column("ID", width=100, stretch=tk.NO)
        self.low_stock_tree.column("Nama Produk", width=300, stretch=tk.YES)
        self.low_stock_tree.column("Stok", width=80, stretch=tk.NO)

        low_stock_tree_scrollbar = ttk.Scrollbar(report_frame, orient="vertical", command=self.low_stock_tree.yview)
        self.low_stock_tree.configure(yscrollcommand=low_stock_tree_scrollbar.set)
        low_stock_tree_scrollbar.grid(row=0, column=1, sticky="ns")

        refresh_button = ttk.Button(report_frame, text="Refresh Laporan Stok", command=self.load_low_stock_to_tree, style='TButton')
        refresh_button.grid(row=1, column=0, pady=10, padx=10, sticky="ew")

        self.load_low_stock_to_tree()

if __name__ == "__main__":
    root = tk.Tk()
    app = POSApp(root)
    root.mainloop()
