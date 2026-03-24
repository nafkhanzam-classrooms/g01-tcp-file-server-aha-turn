import socket
import struct
import os
import threading
import sys

HOST = '127.0.0.1'
PORT = 5000

DOWNLOAD_DIR = "client_downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


def send_msg(sock, data):
    """Method 5: Length Prefix / Header framing."""
    header = struct.pack(">I", len(data))
    sock.sendall(header + data)


def recv_msg(sock):
    """Receive a complete length-prefixed message (blocking)."""
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


def upload_file(sock, filename):
    """
    Send a file to the server using Method 6: Chunked Blocks framing.
    (stream file without knowing total size — from the lecture)
    """
    if not os.path.exists(filename):
        print(f"[Client] File not found: {filename}")
        return

    send_msg(sock, f"/upload {os.path.basename(filename)}".encode())

    response = recv_msg(sock)
    if not response:
        print("[Client] No response from server.")
        return
    resp_text = response.decode(errors='replace')
    if not resp_text.startswith("READY_UPLOAD"):
        print(f"[Client] Unexpected response: {resp_text}")
        return

    print(f"[Client] Uploading: {filename} ...")

    with open(filename, "rb") as f:
        while True:
            chunk = f.read(4096)
            if not chunk:
                break
            sock.sendall(struct.pack(">I", len(chunk)) + chunk)
    sock.sendall(struct.pack(">I", 0))

    result = recv_msg(sock)
    if result:
        print(f"[Client] {result.decode(errors='replace')}")


def download_file(sock, filename):
    """
    Receive a file from the server using Method 6: Chunked Blocks framing.
    """
    send_msg(sock, f"/download {filename}".encode())

    response = recv_msg(sock)
    if not response:
        print("[Client] No response from server.")
        return
    resp_text = response.decode(errors='replace')

    if resp_text.startswith("ERROR"):
        print(f"[Client] {resp_text}")
        return

    if not resp_text.startswith("READY_DOWNLOAD"):
        print(f"[Client] Unexpected response: {resp_text}")
        return

    print(f"[Client] Downloading: {filename} ...")

    save_path = os.path.join(DOWNLOAD_DIR, os.path.basename(filename))
    with open(save_path, "wb") as f:
        while True:
            length_data = sock.recv(4)
            if not length_data or len(length_data) < 4:
                break
            length = struct.unpack(">I", length_data)[0]
            if length == 0:
                break
            buf = b""
            while len(buf) < length:
                buf += sock.recv(length - len(buf))
            f.write(buf)

    print(f"[Client] Saved to: {save_path}")


def receive_loop(sock):
    """
    Background thread: continuously receive broadcast / server messages
    and print them. Runs concurrently with the input loop.
    Uses Method 2: Target Function (from lecture threading section).
    """
    while True:
        try:
            data = recv_msg(sock)
            if data is None:
                print("\n[Client] Disconnected from server.")
                os._exit(0)
            text = data.decode(errors='replace')
            print(f"\n{text}")
            print(">> ", end='', flush=True)
        except Exception:
            print("\n[Client] Connection error.")
            os._exit(0)

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((HOST, PORT))
    except ConnectionRefusedError:
        print(f"[Client] Cannot connect to {HOST}:{PORT}. Is the server running?")
        sys.exit(1)

    print(f"[Client] Connected to {HOST}:{PORT}")
    print("[Client] Commands: /list  |  /upload <file>  |  /download <file>  |  /quit")
    print("[Client] Any other text is broadcast as a chat message.\n")

    welcome = recv_msg(sock)
    if welcome:
        print(f"[Server] {welcome.decode(errors='replace')}")

    recv_thread = threading.Thread(target=receive_loop, args=(sock,))
    recv_thread.daemon = True
    recv_thread.start()

    try:
        while True:
            try:
                user_input = input(">> ").strip()
            except (EOFError, KeyboardInterrupt):
                break

            if not user_input:
                continue

            if user_input == "/quit":
                print("[Client] Disconnecting.")
                break

            elif user_input == "/list":
                send_msg(sock, b"/list")

            elif user_input.startswith("/upload "):
                filename = user_input[len("/upload "):].strip()
                upload_file(sock, filename)

            elif user_input.startswith("/download "):
                filename = user_input[len("/download "):].strip()
                download_file(sock, filename)

            else:
                send_msg(sock, user_input.encode())

    except Exception as e:
        print(f"[Client] Error: {e}")
    finally:
        sock.close()

if __name__ == '__main__':
    main()