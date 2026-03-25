import socket
import struct
import os

UPLOAD_DIR = "server_files"
os.makedirs(UPLOAD_DIR, exist_ok=True)

HOST = '127.0.0.1'
PORT = 5000

def send_msg(sock, data):
    """Method 5: Length Prefix / Header framing from the lecture."""
    header = struct.pack(">I", len(data))
    sock.sendall(header + data)

def recv_msg(sock):
    """Receive a length-prefixed message."""
    header = sock.recv(4)
    if not header or len(header) < 4:
        return None
    length = struct.unpack(">I", header)[0]
    buf = b""
    while len(buf) < length:
        chunk = sock.recv(length - len(buf))
        if not chunk:
            return None
        buf += chunk
    return buf

def handle_client(conn, addr):
    """Handle one client — sync, blocks entire server."""
    print(f"[SYNC] Connected: {addr}")
    send_msg(conn, b"Welcome to the TCP File Server (sync mode)!")

    while True:
        data = recv_msg(conn)
        if not data:
            print(f"[SYNC] Disconnected: {addr}")
            break

        message = data.decode(errors='replace').strip()
        print(f"[SYNC] {addr}: {message}")

        if message == "/list":
            files = os.listdir(UPLOAD_DIR)
            if files:
                reply = "Files on server:\n" + "\n".join(files)
            else:
                reply = "No files on server."
            send_msg(conn, reply.encode())

        elif message.startswith("/upload "):
            filename = message[len("/upload "):].strip()
            send_msg(conn, f"READY_UPLOAD {filename}".encode())
            filepath = os.path.join(UPLOAD_DIR, os.path.basename(filename))
            with open(filepath, "wb") as f:
                while True:
                    length_data = conn.recv(4)
                    if not length_data or len(length_data) < 4:
                        break
                    length = struct.unpack(">I", length_data)[0]
                    if length == 0:
                        break
                    buf = b""
                    while len(buf) < length:
                        buf += conn.recv(length - len(buf))
                    f.write(buf)
            send_msg(conn, f"Upload complete: {filename}".encode())
            print(f"[SYNC] Uploaded: {filename}")

        elif message.startswith("/download "):
            filename = message[len("/download "):].strip()
            filepath = os.path.join(UPLOAD_DIR, os.path.basename(filename))
            if not os.path.exists(filepath):
                send_msg(conn, f"ERROR File not found: {filename}".encode())
            else:
                send_msg(conn, f"READY_DOWNLOAD {filename}".encode())
                with open(filepath, "rb") as f:
                    while True:
                        chunk = f.read(4096)
                        if not chunk:
                            break
                        conn.sendall(struct.pack(">I", len(chunk)) + chunk)
                conn.sendall(struct.pack(">I", 0))
                print(f"[SYNC] Downloaded: {filename}")

        else:
            send_msg(conn, f"MSG {addr[0]}:{addr[1]}: {message}".encode())
    conn.close()

def main():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, PORT))
    server_socket.listen(5)
    print(f"[SYNC] Server listening on {HOST}:{PORT} (one client at a time)")

    try:
        while True:
            conn, addr = server_socket.accept()
            handle_client(conn, addr)
    except KeyboardInterrupt:
        print("\n[SYNC] Server shutting down.")
    finally:
        server_socket.close()

if __name__ == '__main__':
    main()