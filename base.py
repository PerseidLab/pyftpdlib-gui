import sys
import os
import urllib.request
import json
import tarfile
import tempfile
import shutil
import socket

LOCAL_LIB = os.path.join(os.getcwd(), ".ftp_libs")
sys.path.insert(0, LOCAL_LIB)

def download_and_extract(package_name, subfolder_name):
    dest_path = os.path.join(LOCAL_LIB, subfolder_name)
    if os.path.exists(dest_path):
        return

    print(f"[*] Downloading '{package_name}' locally...")
    api_url = f"https://pypi.org/pypi/{package_name}/json"
    req = urllib.request.urlopen(api_url)
    data = json.loads(req.read().decode("utf-8"))

    sdist_url = None
    for file_info in data["urls"]:
        if file_info["packagetype"] == "sdist":
            sdist_url = file_info["url"]
            break
    if not sdist_url:
        sdist_url = data["releases"][data["info"]["version"]][0]["url"]

    with tempfile.TemporaryDirectory() as temp_dir:
        tar_path = os.path.join(temp_dir, f"{package_name}.tar.gz")
        urllib.request.urlretrieve(sdist_url, tar_path)

        with tarfile.open(tar_path, "r:*") as tar:
            if sys.version_info >= (3, 14):
                tar.extractall(path=temp_dir, filter='data')
            else:
                tar.extractall(path=temp_dir)

        for folder in os.listdir(temp_dir):
            folder_path = os.path.join(temp_dir, folder)
            if os.path.isdir(folder_path):
                pkg_src = os.path.join(folder_path, subfolder_name)
                if os.path.exists(pkg_src):
                    if os.path.exists(dest_path):
                        shutil.rmtree(dest_path)
                    shutil.copytree(pkg_src, dest_path)
                    break

try:
    import pyftpdlib
    import asynchat
    import asyncore
except ImportError:
    os.makedirs(LOCAL_LIB, exist_ok=True)
    try:
        download_and_extract("pyasyncore", "asyncore")
        download_and_extract("pyasynchat", "asynchat")
        download_and_extract("pyftpdlib", "pyftpdlib")
        print("[*] Successfully downloaded and configured all dependencies!")
    except Exception as e:
        print(f"[!] Failed to automatically download dependencies: {e}")
        sys.exit(1)

import threading
import tkinter as tk
from tkinter import filedialog, scrolledtext, messagebox
from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer

class FTPServerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Python Tkinter FTP Server")
        self.root.geometry("550x570")
        self.root.resizable(False, False)

        self.server = None
        self.server_thread = None

        ip_frame = tk.LabelFrame(root, text=" Network / IP Address(es) ", padx=10, pady=8)
        ip_frame.pack(fill="x", padx=15, pady=(10, 0))

        ips = self.get_local_ips()
        ip_text = ", ".join(ips) if ips else "127.0.0.1 (Localhost only)"

        self.ip_label = tk.Label(ip_frame, text=f"Available IPs: {ip_text}", fg="blue", font=("Bold", 10))
        self.ip_label.pack(anchor="w")

        tk.Label(root, text="Shared Directory:").pack(anchor="w", padx=15, pady=(10, 0))
        dir_frame = tk.Frame(root)
        dir_frame.pack(fill="x", padx=15, pady=5)

        self.dir_entry = tk.Entry(dir_frame, width=45)
        self.dir_entry.pack(side="left", padx=(0, 5))
        self.dir_entry.insert(0, os.getcwd())

        tk.Button(dir_frame, text="Browse", command=self.browse_directory).pack(side="left")

        cred_frame = tk.LabelFrame(root, text=" Server Credentials, Port & Permissions ", padx=10, pady=10)
        cred_frame.pack(fill="x", padx=15, pady=10)

        tk.Label(cred_frame, text="Port:").grid(row=0, column=0, sticky="w", pady=2)
        self.port_entry = tk.Entry(cred_frame, width=20)
        self.port_entry.grid(row=0, column=1, sticky="w", pady=2, columnspan=2)
        self.port_entry.insert(0, "2121")

        tk.Label(cred_frame, text="Username:").grid(row=1, column=0, sticky="w", pady=2)
        self.user_entry = tk.Entry(cred_frame, width=20)
        self.user_entry.grid(row=1, column=1, sticky="w", pady=2, columnspan=2)
        self.user_entry.insert(0, "user")

        tk.Label(cred_frame, text="Password:").grid(row=2, column=0, sticky="w", pady=2)
        self.pass_entry = tk.Entry(cred_frame, width=20, show="*")
        self.pass_entry.grid(row=2, column=1, sticky="w", pady=2)
        self.pass_entry.insert(0, "12345")

        self.show_pass_var = tk.IntVar()
        self.show_pass_chk = tk.Checkbutton(cred_frame, text="Show", variable=self.show_pass_var, command=self.toggle_password)
        self.show_pass_chk.grid(row=2, column=2, sticky="w", padx=(5, 0))

        self.readonly_var = tk.IntVar()
        self.readonly_chk = tk.Checkbutton(cred_frame, text="Read-Only", variable=self.readonly_var)
        self.readonly_chk.grid(row=3, column=0, columnspan=3, sticky="w", pady=(8, 0))

        btn_frame = tk.Frame(root)
        btn_frame.pack(fill="x", padx=15, pady=5)

        self.start_btn = tk.Button(btn_frame, text="Start Server", bg="green", fg="white", font=("Bold", 10), command=self.start_server)
        self.start_btn.pack(side="left", expand=True, fill="x", padx=(0, 5))

        self.stop_btn = tk.Button(btn_frame, text="Stop Server", bg="red", fg="white", font=("Bold", 10), state="disabled", command=self.stop_server)
        self.stop_btn.pack(side="right", expand=True, fill="x", padx=(5, 0))

        tk.Label(root, text="Server Activity Log:").pack(anchor="w", padx=15, pady=(5, 0))
        self.log_area = scrolledtext.ScrolledText(root, height=7, state="disabled", bg="#f4f4f4")
        self.log_area.pack(fill="both", padx=15, pady=(0, 15))

    def toggle_password(self):
        if self.show_pass_var.get() == 1:
            self.pass_entry.config(show="")
        else:
            self.pass_entry.config(show="*")

    def get_local_ips(self):
        ips = []
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("10.255.255.255", 1))
            ips.append(s.getsockname()[0])
            s.close()
        except Exception:
            pass
        try:
            for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
                ip = info[4][0]
                if ip not in ips and not ip.startswith("127."):
                    ips.append(ip)
        except Exception:
            pass
        return ips

    def browse_directory(self):
        chosen_dir = filedialog.askdirectory()
        if chosen_dir:
            self.dir_entry.delete(0, tk.END)
            self.dir_entry.insert(0, chosen_dir)

    def log_message(self, message):
        self.log_area.config(state="normal")
        self.log_area.insert(tk.END, message + "\n")
        self.log_area.see(tk.END)
        self.log_area.config(state="disabled")

    def run_ftp(self):
        try:
            path = self.dir_entry.get()
            port = int(self.port_entry.get())
            username = self.user_entry.get()
            password = self.pass_entry.get()
            is_readonly = self.readonly_var.get() == 1

            permissions = "elr" if is_readonly else "elradfmwMT"

            authorizer = DummyAuthorizer()
            authorizer.add_user(username, password, path, perm=permissions)

            handler = FTPHandler
            handler.authorizer = authorizer

            mode_str = "Read-Only" if is_readonly else "Full Access (Read/Write)"
            self.server = FTPServer(("0.0.0.0", port), handler)
            self.log_message(f"[*] Server started on port {port} [{mode_str}], sharing: {path}")
            self.server.serve_forever()
        except Exception as e:
            self.log_message(f"[!] Error: {e}")
            self.stop_server()

    def start_server(self):
        if not os.path.exists(self.dir_entry.get()):
            messagebox.showerror("Error", "The specified shared directory does not exist.")
            return

        self.server_thread = threading.Thread(target=self.run_ftp, daemon=True)
        self.server_thread.start()

        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.dir_entry.config(state="disabled")
        self.port_entry.config(state="disabled")
        self.user_entry.config(state="disabled")
        self.pass_entry.config(state="disabled")
        self.show_pass_chk.config(state="disabled")
        self.readonly_chk.config(state="disabled")

    def stop_server(self):
        if self.server:
            self.server.close_all()
            self.server = None

        self.log_message("[*] Server stopped.")
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.dir_entry.config(state="normal")
        self.port_entry.config(state="normal")
        self.user_entry.config(state="normal")
        self.pass_entry.config(state="normal")
        self.show_pass_chk.config(state="normal")
        self.readonly_chk.config(state="normal")

if __name__ == "__main__":
    root = tk.Tk()
    app = FTPServerApp(root)
    root.mainloop()

