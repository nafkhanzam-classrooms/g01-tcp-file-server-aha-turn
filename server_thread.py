import socket
import os
import struct
import threading

HOST = '127.0.0.1'
PORT = 5000
FILES_DIR = 'server_files'

os.makedirs(FILES_DIR, exist_ok=True)

clients_lock = threading.Lock()
clients: list[socket.socket] = []


# ─── Framing helpers ──────────────────────────────────────────────────────────

def send_msg(conn, data: bytes):
    header = struct.pack('>I', len(data))
    conn.sendall(header + data)


def recv_msg(conn) -> bytes | None:
    raw_len = recv_exact(conn, 4)
    if not raw_len:
        return None
    length = struct.unpack('>I', raw_len)[0]
    return recv_exact(conn, length)


def recv_exact(conn, n: int) -> bytes:
    buf = b''
    while len(buf) < n:
        chunk = conn.recv(n - len(buf))
        if not chunk:
            return b''
        buf += chunk
    return buf


def send_file_chunked(conn, filepath: str):
    """Method 6: Chunked Blocks."""
    with open(filepath, 'rb') as f:
        while True:
            chunk = f.read(4096)
            if not chunk:
                break
            conn.sendall(struct.pack('>I', len(chunk)) + chunk)
    conn.sendall(struct.pack('>I', 0))


def recv_file_chunked(conn) -> bytes:
    buf = b''
    while True:
        length_data = recv_exact(conn, 4)
        if not length_data:
            break
        length = struct.unpack('>I', length_data)[0]
        if length == 0:
            break
        buf += recv_exact(conn, length)
    return buf


# ─── Broadcast ────────────────────────────────────────────────────────────────

def broadcast(message: str, sender: socket.socket = None):
    data = message.encode()
    with clients_lock:
        for c in list(clients):
            if c is not sender:
                try:
                    send_msg(c, data)
                except Exception:
                    pass


# ─── Command handlers ─────────────────────────────────────────────────────────

def handle_list(conn):
    files = os.listdir(FILES_DIR)
    response = '\n'.join(files) if files else '(no files)'
    send_msg(conn, response.encode())


def handle_upload(conn, filename: str, addr, sender: socket.socket):
    filename = os.path.basename(filename)
    send_msg(conn, b'READY_UPLOAD')           # handshake
    file_data = recv_file_chunked(conn)       # receive chunked
    if not file_data:
        send_msg(conn, b'ERROR: empty file data')
        return
    filepath = os.path.join(FILES_DIR, filename)
    with open(filepath, 'wb') as f:
        f.write(file_data)
    print(f'  [UPLOAD] {filename} ({len(file_data)} bytes)')
    send_msg(conn, f'OK: uploaded {filename}'.encode())
    broadcast(f'[Server] {addr} uploaded "{filename}" ({len(file_data)} bytes).', sender=sender)


def handle_download(conn, filename: str, addr, sender: socket.socket):
    filename = os.path.basename(filename)
    filepath = os.path.join(FILES_DIR, filename)
    if not os.path.exists(filepath):
        send_msg(conn, b'ERROR: file not found')
        return
    send_msg(conn, b'READY_DOWNLOAD')         # handshake
    send_file_chunked(conn, filepath)         # send chunked
    print(f'  [DOWNLOAD] {filename}')
    broadcast(f'[Server] {addr} downloaded "{filename}".', sender=sender)


# ─── Client thread ────────────────────────────────────────────────────────────

class ClientHandler(threading.Thread):
    def __init__(self, conn: socket.socket, addr):
        threading.Thread.__init__(self)
        self.conn = conn
        self.addr = addr
        self.daemon = True

    def run(self):
        print(f'[+] Connected: {self.addr}  (thread: {self.name})')
        with clients_lock:
            clients.append(self.conn)
        send_msg(self.conn, b'Welcome to TCP File Server (thread)!')
        broadcast(f'[Server] {self.addr} has joined.', sender=self.conn)

        try:
            while True:
                msg = recv_msg(self.conn)
                if msg is None:
                    break

                text = msg.decode(errors='replace').strip()
                print(f'  [{self.addr}] Command: {text}')

                if text == '/list':
                    handle_list(self.conn)

                elif text.startswith('/upload '):
                    filename = text[len('/upload '):]
                    handle_upload(self.conn, filename, self.addr, self.conn)

                elif text.startswith('/download '):
                    filename = text[len('/download '):]
                    handle_download(self.conn, filename, self.addr, self.conn)

                else:
                    broadcast_msg = f'[{self.addr[0]}:{self.addr[1]}] {text}'
                    broadcast(broadcast_msg, sender=self.conn)
                    send_msg(self.conn, f'[You] {text}'.encode())

        except (ConnectionResetError, BrokenPipeError, OSError):
            pass
        finally:
            with clients_lock:
                if self.conn in clients:
                    clients.remove(self.conn)
            self.conn.close()
            print(f'[-] Disconnected: {self.addr}')
            broadcast(f'[Server] {self.addr} has left.')


# ─── Main server ──────────────────────────────────────────────────────────────

class Server:
    def __init__(self):
        self.host = HOST
        self.port = PORT
        self.server = None
        self.threads: list[ClientHandler] = []

    def open_socket(self):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind((self.host, self.port))
        self.server.listen(5)

    def run(self):
        self.open_socket()
        print(f'[server-thread] Listening on {self.host}:{self.port}')
        print(f'[server-thread] Files directory: {os.path.abspath(FILES_DIR)}')
        print('[server-thread] Mode: threaded (one thread per client)\n')

        try:
            while True:
                conn, addr = self.server.accept()
                t = ClientHandler(conn, addr)
                t.start()
                self.threads.append(t)
        except KeyboardInterrupt:
            print('\n[server-thread] Shutting down.')
        finally:
            self.server.close()
            for t in self.threads:
                t.join(timeout=2)


if __name__ == '__main__':
    server = Server()
    server.run()
