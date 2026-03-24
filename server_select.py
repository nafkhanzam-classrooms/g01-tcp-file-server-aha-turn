import socket
import select
import struct
import os

UPLOAD_DIR = "server_files"
os.makedirs(UPLOAD_DIR, exist_ok=True)

HOST = '127.0.0.1'
PORT = 5000

upload_state = {}

recv_buffers = {}

clients = {}

def send_msg(sock, data):
    """Method 5: Length Prefix / Header framing."""
    header = struct.pack(">I", len(data))
    sock.sendall(header + data)


def broadcast(message, exclude=None):
    """Send a message to all connected clients."""
    for sock in list(clients.keys()):
        if sock is exclude:
            continue
        try:
            send_msg(sock, message)
        except Exception:
            pass


def try_recv_msg(sock):
    """
    Try to receive a complete length-prefixed message.
    Uses a per-socket buffer to handle partial reads.
    Returns the message bytes if complete, None otherwise.
    """
    if sock not in recv_buffers:
        recv_buffers[sock] = b""

    buf = recv_buffers[sock]

    chunk = sock.recv(4096)
    if not chunk:
        return b""
    buf += chunk
    recv_buffers[sock] = buf

    if len(buf) < 4:
        return None

    length = struct.unpack(">I", buf[:4])[0]
    if len(buf) < 4 + length:
        return None

    message = buf[4:4 + length]
    recv_buffers[sock] = buf[4 + length:]
    return message


def handle_command(sock, addr, message):
    """Process a command string from a client."""
    text = message.decode(errors='replace').strip()
    print(f"[SELECT] {addr}: {text}")

    if text == "/list":
        files = os.listdir(UPLOAD_DIR)
        reply = ("Files on server:\n" + "\n".join(files)) if files else "No files on server."
        send_msg(sock, reply.encode())

    elif text.startswith("/upload "):
        filename = text[len("/upload "):].strip()
        filepath = os.path.join(UPLOAD_DIR, os.path.basename(filename))
        upload_state[sock] = {"filename": filename, "file": open(filepath, "wb"), "buf": b""}
        send_msg(sock, f"READY_UPLOAD {filename}".encode())

    elif text.startswith("/download "):
        filename = text[len("/download "):].strip()
        filepath = os.path.join(UPLOAD_DIR, os.path.basename(filename))
        if not os.path.exists(filepath):
            send_msg(sock, f"ERROR File not found: {filename}".encode())
        else:
            send_msg(sock, f"READY_DOWNLOAD {filename}".encode())
            with open(filepath, "rb") as f:
                while True:
                    chunk = f.read(4096)
                    if not chunk:
                        break
                    sock.sendall(struct.pack(">I", len(chunk)) + chunk)
            sock.sendall(struct.pack(">I", 0))
            print(f"[SELECT] Sent file: {filename} to {addr}")

    else:
        broadcast_msg = f"MSG {addr[0]}:{addr[1]}: {text}".encode()
        broadcast(broadcast_msg)


def handle_upload_data(sock, addr):
    """
    Receive raw chunked-block data for an in-progress upload.
    Method 6: Chunked Blocks framing from the lecture.
    """
    state = upload_state[sock]
    buf = state["buf"]

    chunk = sock.recv(4096)
    if not chunk:
        return False

    buf += chunk
    state["buf"] = buf

    while True:
        if len(buf) < 4:
            break
        length = struct.unpack(">I", buf[:4])[0]
        if length == 0:
            state["file"].close()
            filename = state["filename"]
            del upload_state[sock]
            send_msg(sock, f"Upload complete: {filename}".encode())
            broadcast(f"[Server] {addr[0]}:{addr[1]} uploaded: {filename}".encode(), exclude=sock)
            print(f"[SELECT] Upload complete: {filename} from {addr}")
            state["buf"] = buf[4:]
            break
        if len(buf) < 4 + length:
            break
        data = buf[4:4 + length]
        state["file"].write(data)
        buf = buf[4 + length:]
        state["buf"] = buf

    return True


def remove_client(sock, input_sockets):
    addr = clients.get(sock, "unknown")
    print(f"[SELECT] Disconnected: {addr}")
    broadcast(f"[Server] {addr[0]}:{addr[1]} disconnected.".encode(), exclude=sock)
    if sock in upload_state:
        upload_state[sock]["file"].close()
        del upload_state[sock]
    if sock in recv_buffers:
        del recv_buffers[sock]
    if sock in clients:
        del clients[sock]
    sock.close()
    input_sockets.remove(sock)


def main():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, PORT))
    server_socket.listen(5)
    print(f"[SELECT] Server listening on {HOST}:{PORT}")

    input_sockets = [server_socket]

    try:
        while True:
            read_ready, _, _ = select.select(input_sockets, [], [])

            for sock in read_ready:
                if sock == server_socket:
                    client_sock, client_addr = server_socket.accept()
                    input_sockets.append(client_sock)
                    clients[client_sock] = client_addr
                    print(f"[SELECT] Connected: {client_addr}")
                    send_msg(client_sock, b"Welcome to the TCP File Server (select mode)!")
                    broadcast(
                        f"[Server] {client_addr[0]}:{client_addr[1]} joined.".encode(),
                        exclude=client_sock
                    )

                else:
                    addr = clients.get(sock, ("?", "?"))

                    if sock in upload_state:
                        ok = handle_upload_data(sock, addr)
                        if not ok:
                            remove_client(sock, input_sockets)
                        continue

                    msg = try_recv_msg(sock)
                    if msg is None:
                        continue
                    if msg == b"":
                        remove_client(sock, input_sockets)
                    else:
                        handle_command(sock, addr, msg)

    except KeyboardInterrupt:
        print("\n[SELECT] Server shutting down.")
    finally:
        server_socket.close()

if __name__ == '__main__':
    main()