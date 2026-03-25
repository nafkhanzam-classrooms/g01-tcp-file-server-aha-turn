import socket
import select
import os
import struct

HOST = '127.0.0.1'
PORT = 5000
FILES_DIR = 'server_files'

os.makedirs(FILES_DIR, exist_ok=True)


# ─── Framing helpers ──────────────────────────────────────────────────────────

def send_msg(conn, data: bytes):
    header = struct.pack('>I', len(data))
    conn.sendall(header + data)


def recv_exact(conn, n: int) -> bytes:
    buf = b''
    while len(buf) < n:
        chunk = conn.recv(n - len(buf))
        if not chunk:
            return b''
        buf += chunk
    return buf


def recv_msg(conn) -> bytes | None:
    raw_len = recv_exact(conn, 4)
    if not raw_len:
        return None
    length = struct.unpack('>I', raw_len)[0]
    return recv_exact(conn, length)


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

def broadcast(fd_map: dict, message: str, sender_fd: int = None, server_fd: int = None):
    data = message.encode()
    for fd, sock in list(fd_map.items()):
        if fd != sender_fd and fd != server_fd:
            try:
                send_msg(sock, data)
            except Exception:
                pass


# ─── Command handlers ─────────────────────────────────────────────────────────

def handle_list(conn):
    files = os.listdir(FILES_DIR)
    response = '\n'.join(files) if files else '(no files)'
    send_msg(conn, response.encode())


def handle_upload(conn, filename: str, addr, fd_map: dict, sender_fd: int, server_fd: int):
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
    broadcast(fd_map, f'[Server] {addr} uploaded "{filename}" ({len(file_data)} bytes).',
              sender_fd=sender_fd, server_fd=server_fd)


def handle_download(conn, filename: str, addr, fd_map: dict, sender_fd: int, server_fd: int):
    filename = os.path.basename(filename)
    filepath = os.path.join(FILES_DIR, filename)
    if not os.path.exists(filepath):
        send_msg(conn, b'ERROR: file not found')
        return
    send_msg(conn, b'READY_DOWNLOAD')         # handshake
    send_file_chunked(conn, filepath)         # send chunked
    print(f'  [DOWNLOAD] {filename}')
    broadcast(fd_map, f'[Server] {addr} downloaded "{filename}".',
              sender_fd=sender_fd, server_fd=server_fd)


# ─── Close & cleanup ──────────────────────────────────────────────────────────

def close_client(fd, poll_obj, fd_map, addr_map, server_fd):
    addr = addr_map.get(fd, fd)
    print(f'[-] Disconnected: {addr}')
    broadcast(fd_map, f'[Server] {addr} has left.', sender_fd=fd, server_fd=server_fd)
    try:
        poll_obj.unregister(fd)
    except Exception:
        pass
    sock = fd_map.pop(fd, None)
    if sock:
        try:
            sock.close()
        except Exception:
            pass
    addr_map.pop(fd, None)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(5)
    server.setblocking(False)

    poll_obj = select.poll()
    poll_obj.register(server.fileno(), select.POLLIN)

    fd_map: dict[int, socket.socket] = {server.fileno(): server}
    addr_map: dict[int, tuple] = {}

    server_fd = server.fileno()

    print(f'[server-poll] Listening on {HOST}:{PORT}')
    print(f'[server-poll] Files directory: {os.path.abspath(FILES_DIR)}')
    print('[server-poll] Mode: I/O multiplexing with poll()\n')

    try:
        while True:
            events = poll_obj.poll()

            for fd, event in events:

                # ── Error / hangup ────────────────────────────────────────────
                if event & (select.POLLHUP | select.POLLERR | select.POLLNVAL):
                    if fd != server_fd:
                        close_client(fd, poll_obj, fd_map, addr_map, server_fd)
                    continue

                # ── New connection ────────────────────────────────────────────
                if fd == server_fd:
                    conn, addr = server.accept()
                    conn.setblocking(False)
                    new_fd = conn.fileno()
                    fd_map[new_fd] = conn
                    addr_map[new_fd] = addr
                    poll_obj.register(new_fd, select.POLLIN)
                    print(f'[+] Connected: {addr}  (fd={new_fd})')
                    # Send welcome — temporarily blocking for framing
                    conn.setblocking(True)
                    send_msg(conn, b'Welcome to TCP File Server (poll)!')
                    conn.setblocking(False)
                    broadcast(fd_map, f'[Server] {addr} has joined.',
                              sender_fd=new_fd, server_fd=server_fd)
                    continue

                # ── Data ready on existing client ─────────────────────────────
                if event & select.POLLIN:
                    sock = fd_map.get(fd)
                    if sock is None:
                        continue

                    # Switch to blocking for framing recv/send
                    sock.setblocking(True)
                    msg = recv_msg(sock)

                    if not msg:
                        sock.setblocking(False)
                        close_client(fd, poll_obj, fd_map, addr_map, server_fd)
                        continue

                    addr = addr_map.get(fd, fd)
                    text = msg.decode(errors='replace').strip()
                    print(f'  [{addr}] Command: {text}')

                    if text == '/list':
                        handle_list(sock)

                    elif text.startswith('/upload '):
                        filename = text[len('/upload '):]
                        handle_upload(sock, filename, addr, fd_map, fd, server_fd)

                    elif text.startswith('/download '):
                        filename = text[len('/download '):]
                        handle_download(sock, filename, addr, fd_map, fd, server_fd)

                    else:
                        broadcast_msg = f'[{addr[0]}:{addr[1]}] {text}'
                        broadcast(fd_map, broadcast_msg, sender_fd=fd, server_fd=server_fd)
                        send_msg(sock, f'[You] {text}'.encode())

                    sock.setblocking(False)

    except KeyboardInterrupt:
        print('\n[server-poll] Shutting down.')
    finally:
        for sock in fd_map.values():
            try:
                sock.close()
            except Exception:
                pass


if __name__ == '__main__':
    main()
