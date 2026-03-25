[![Review Assignment Due Date](https://classroom.github.com/assets/deadline-readme-button-22041afd0340ce965d47ae6ef1cefeee28c7c493a6346c4f15d667ab976d596c.svg)](https://classroom.github.com/a/mRmkZGKe)
# Network Programming - Assignment G01

## Anggota Kelompok
| Nama                | NRP        | Kelas     |
| ---                 | ---        | ----------|
| Bagus Cahya Saputra | 5025241067 |    D      |
| Rafi Aqila Maulana  | 5025241165 |    D      |

## Link Youtube (Unlisted)
Link ditaruh di bawah ini
```
https://youtu.be/cCX5LSRlSnM
```

### Sebelumnya berikut bukti bahwa kami satu Teams
<img width="178" height="118" alt="image" src="https://github.com/user-attachments/assets/25ce883e-be7d-43c0-8b92-ea46759621e7" />


<img width="497" height="557" alt="image" src="https://github.com/user-attachments/assets/70ff8145-70b8-47cf-9fc3-5d60a9f7f03b" />

## Penjelasan Program

### Overview
Program ini merupakan implementasi **TCP File Server** dengan dua pendekatan:
- **server_sync.py** -> server synchronous (blocking, 1 client)
- **server_select.py** -> server non-blocking (multi-client dengan `select`)
- **client.py** -> client untuk upload, download, list, dan chat

---

## server_sync.py (Synchronous Server)

Server ini bekerja secara **blocking**, artinya hanya dapat menangani **1 klien dalam satu waktu**.

---

### Inisialisasi Server
```python
UPLOAD_DIR = "server_files"
os.makedirs(UPLOAD_DIR, exist_ok=True)
```
- Folder `server_files` dibuat sebagai tempat penyimpanan file upload dari client  
- `exist_ok=True` agar tidak error jika folder sudah ada  

```python
HOST = '127.0.0.1'
PORT = 5000
```
- Server berjalan di localhost dan port 5000  

---

### Framing Data (Komunikasi)
```python
def send_msg(sock, data):
    header = struct.pack(">I", len(data))
    sock.sendall(header + data)
```
- Mengirim data dengan **length-prefix framing**
- 4 byte pertama = panjang pesan  
- Tujuannya agar receiver tahu batas pesan

```python
def recv_msg(sock):
```
- Membaca 4 byte pertama (header)
- Lalu membaca isi pesan sesuai panjang tersebut  
- Mencegah data tercampur (karena TCP adalah stream)
---

### Handle Client
```python
def handle_client(conn, addr):
```
- `conn` = socket khusus untuk komunikasi dengan client  
- `addr` = alamat client  

```python
while True:
    data = recv_msg(conn)
```
- Loop terus selama client masih terhubung  
- Menunggu command dari client  

---

### List File
```python
if message == "/list":
```
- Server membaca isi folder `server_files`
- Mengirim daftar file ke client  

---

### Upload File
```python
elif message.startswith("/upload "):
```
Alur:
1. Client mengirim `/upload`
2. Server mengambil nama file
3. Server kirim `READY_UPLOAD`

```python
with open(filepath, "wb") as f:
```
- File dibuka dalam mode write binary  

```python
while True:
    length_data = conn.recv(4)
```
- Server membaca panjang chunk  

```python
if length == 0:
    break
```
- Jika panjang = 0 -> upload selesai  

```python
f.write(buf)
```
- Data chunk ditulis ke file  

Jadi:
> File dikirim bertahap (chunked transfer), bukan langsung sekaligus

---

### Download File
```python
elif message.startswith("/download "):
```
Alur:
1. Server cek apakah file ada
2. Jika ada -> kirim `READY_DOWNLOAD`

```python
with open(filepath, "rb") as f:
```
- File dibaca per 4096 byte  

```python
conn.sendall(struct.pack(">I", len(chunk)) + chunk)
```
- Setiap chunk dikirim dengan header panjang  

```python
conn.sendall(struct.pack(">I", 0))
```
- Mengirim 0 sebagai tanda selesai  

---

### Kelemahan
- Server hanya melayani 1 client
- Client lain harus menunggu (blocking)

---

## server_select.py (Non-blocking Server)

Server ini menggunakan **I/O Multiplexing (`select`)** sehingga bisa melayani banyak client sekaligus.

---

### Struktur Data
```python
upload_state = {}
recv_buffers = {}
clients = {}
```

- `clients` -> menyimpan socket dan alamat client  
- `recv_buffers` -> menyimpan data sementara (partial data)  
- `upload_state` -> menyimpan status upload tiap client  

---

### send_msg
```python
def send_msg(sock, data):
```
Sama seperti pada server_sync (length-prefix framing)

---

### Broadcast
```python
def broadcast(message, exclude=None):
```
- Mengirim pesan ke semua client  
- Digunakan untuk fitur chat  

---

### Non-blocking Receive
```python
def try_recv_msg(sock):
```

Penjelasan:
- Tidak langsung blocking seperti `recv_msg`
- Data disimpan di buffer dulu  

```python
buf += chunk
```
- Data bisa datang sebagian (partial)  

```python
if len(buf) < 4:
    return None
```
- Jika header belum lengkap -> tunggu  

```python
if len(buf) < 4 + length:
    return None
```
- Jika isi pesan belum lengkap -> tunggu  

Intinya:
> Data dikumpulkan dulu sampai lengkap baru diproses

---

### Handle Command
```python
def handle_command(sock, addr, message):
```
- Mengolah semua command dari client  

#### `/list`
Sama seperti server_sync  

#### `/upload`
```python
upload_state[sock] = {...}
```
- Menyimpan status upload per client  
- Karena banyak client bisa upload bersamaan  

#### `/download`
Sama seperti server_sync  

#### Chat
```python
broadcast(...)
```
- Pesan dikirim ke semua client  

---

### Handle Upload (Chunk)
```python
def handle_upload_data(sock, addr):
```

```python
buf += chunk
```
- Data file dikumpulkan di buffer  

```python
length = struct.unpack(">I", buf[:4])[0]
```
- Ambil panjang chunk  

```python
if length == 0:
```
- Upload selesai  

```python
state["file"].write(data)
```
- Data ditulis ke file  

Sama seperti server_sync, tapi:
> Di sini bisa dilakukan oleh banyak client sekaligus

---

### Select Loop (Inti Program)
```python
read_ready, _, _ = select.select(input_sockets, [], [])
```

Penjelasan:
- Mengecek socket mana yang siap dibaca  
- Tidak blocking  

```python
if sock == server_socket:
```
- Jika ada client baru -> accept  

```python
else:
```
- Jika client kirim data -> proses  

Ini yang bikin:
> Server bisa menangani banyak client tanpa thread

---
### Kelebihan
- Multi-client
- Non-blocking
- Lebih efisien
---

## server_poll.py (I/O Multiplexing dengan poll)

Server ini menggunakan *poll()* sebagai alternatif dari select(). Keduanya adalah mekanisme I/O multiplexing, namun poll() tidak memiliki batasan jumlah file descriptor seperti select().

---

### Inisialisasi
python
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind((HOST, PORT))
server.listen(5)
server.setblocking(False)

- Socket dibuat dalam mode *non-blocking*
- SO_REUSEADDR memungkinkan port langsung dipakai ulang setelah server restart

python
poll_obj = select.poll()
poll_obj.register(server.fileno(), select.POLLIN)

- Objek poll dibuat dan server socket didaftarkan untuk dipantau event POLLIN (ada data masuk)

---

### Struktur Data
python
fd_map: dict[int, socket.socket] = {server.fileno(): server}
addr_map: dict[int, tuple] = {}

- fd_map → memetakan file descriptor (fd) ke objek socket
- addr_map → memetakan fd ke alamat client (ip, port)

Berbeda dari select, poll bekerja dengan *file descriptor integer*, bukan objek socket secara langsung. Maka diperlukan dua mapping ini untuk mengelola client.

---

### Poll Loop (Inti Program)
python
events = poll_obj.poll()

- Memanggil poll() yang akan *memblokir* hingga ada minimal satu event terjadi
- Mengembalikan list berisi (fd, event) dari semua socket yang aktif

python
for fd, event in events:

- Iterasi setiap event yang terjadi

python
if event & (select.POLLHUP | select.POLLERR | select.POLLNVAL):
    close_client(fd, poll_obj, fd_map, addr_map, server_fd)

- Menangani kondisi error: koneksi putus (POLLHUP), error (POLLERR), atau fd tidak valid (POLLNVAL)

python
if fd == server_fd:
    conn, addr = server.accept()

- Jika event berasal dari server socket → ada client baru yang mencoba konek

python
if event & select.POLLIN:
    sock = fd_map.get(fd)

- Jika event dari client socket → ada data yang siap dibaca

---

### Penanganan Blocking Sementara
python
sock.setblocking(True)
msg = recv_msg(sock)
# ... proses command ...
sock.setblocking(False)

- Socket di-switch ke *blocking* saat membaca dan memproses command
- Hal ini menyederhanakan logika framing (tidak perlu buffer per-client seperti select)
- Setelah selesai, socket dikembalikan ke *non-blocking*

> Pola ini disebut temporary blocking — praktis untuk implementasi sederhana, meski secara teknis menghentikan loop sejenak saat ada transfer besar.

---

### Koneksi Client Baru
python
conn.setblocking(True)
send_msg(conn, b'Welcome to TCP File Server (poll)!')
conn.setblocking(False)
broadcast(fd_map, f'[Server] {addr} has joined.',
          sender_fd=new_fd, server_fd=server_fd)

- Welcome message dikirim dengan blocking sementara
- Semua client lain dinotifikasi via broadcast bahwa ada client baru bergabung

---

### Fungsi close_client
python
def close_client(fd, poll_obj, fd_map, addr_map, server_fd):
    broadcast(fd_map, f'[Server] {addr} has left.', ...)
    poll_obj.unregister(fd)
    sock = fd_map.pop(fd, None)
    sock.close()
    addr_map.pop(fd, None)

- Unregister fd dari poll agar tidak dipantau lagi
- Hapus dari fd_map dan addr_map
- Broadcast notifikasi ke semua client bahwa seseorang disconnect

---

### Broadcast Upload & Download
python
def handle_upload(conn, filename, addr, fd_map, sender_fd, server_fd):
    ...
    broadcast(fd_map, f'[Server] {addr} uploaded "{filename}" ({len(file_data)} bytes).',
              sender_fd=sender_fd, server_fd=server_fd)

def handle_download(conn, filename, addr, fd_map, sender_fd, server_fd):
    ...
    broadcast(fd_map, f'[Server] {addr} downloaded "{filename}".',
              sender_fd=sender_fd, server_fd=server_fd)

- Setelah upload/download berhasil, semua client lain mendapat notifikasi
- sender_fd dan server_fd dikecualikan dari broadcast

---

### Kelebihan
- Multi-client tanpa thread
- Tidak ada batasan jumlah fd (tidak seperti select yang terbatas 1024)
- Lebih eksplisit dalam menangani event error (POLLHUP, POLLERR)

### Kekurangan
- poll() hanya tersedia di Unix/Linux (tidak tersedia di Windows)
- Temporary blocking masih bisa memperlambat server saat ada transfer besar

---

## server_thread.py (Multi-threading Server)

Server ini menggunakan *satu thread per client*, sehingga setiap client ditangani secara independen dan paralel.

---

### Inisialisasi
python
clients_lock = threading.Lock()
clients: list[socket.socket] = []

- clients → list semua socket client yang sedang terhubung
- clients_lock → *mutex lock* untuk mencegah race condition saat mengakses clients dari banyak thread secara bersamaan

---

### Class ClientHandler
python
class ClientHandler(threading.Thread):
    def __init__(self, conn: socket.socket, addr):
        threading.Thread.__init__(self)
        self.conn = conn
        self.addr = addr
        self.daemon = True

- Setiap client direpresentasikan sebagai sebuah *thread* dengan class ClientHandler
- daemon = True → thread akan otomatis mati saat main thread berhenti

---

### Method run()
python
def run(self):
    with clients_lock:
        clients.append(self.conn)
    send_msg(self.conn, b'Welcome to TCP File Server (thread)!')
    broadcast(f'[Server] {self.addr} has joined.', sender=self.conn)

- Saat thread mulai, socket client ditambahkan ke list clients dengan lock
- Welcome message dikirim ke client baru
- Semua client lain dinotifikasi via broadcast

python
    try:
        while True:
            msg = recv_msg(self.conn)
            if msg is None:
                break
            # proses command...
    except (ConnectionResetError, BrokenPipeError, OSError):
        pass
    finally:
        with clients_lock:
            clients.remove(self.conn)
        self.conn.close()
        broadcast(f'[Server] {self.addr} has left.')

- Loop terus membaca dan memproses command selama client terhubung
- Exception ditangkap untuk koneksi yang terputus secara tiba-tiba
- Blok finally memastikan cleanup selalu terjadi: client dihapus dari list, socket ditutup, dan client lain dinotifikasi

---

### Broadcast dengan Thread Safety
python
def broadcast(message: str, sender: socket.socket = None):
    data = message.encode()
    with clients_lock:
        for c in list(clients):
            if c is not sender:
                try:
                    send_msg(c, data)
                except Exception:
                    pass

- clients_lock digunakan setiap kali mengakses list clients
- list(clients) membuat salinan list agar iterasi tidak terganggu jika ada perubahan di tengah loop
- Sender dikecualikan agar tidak menerima pesannya sendiri

---

### Broadcast Upload & Download
python
def handle_upload(conn, filename, addr, sender):
    ...
    broadcast(f'[Server] {addr} uploaded "{filename}" ({len(file_data)} bytes).', sender=sender)

def handle_download(conn, filename, addr, sender):
    ...
    broadcast(f'[Server] {addr} downloaded "{filename}".', sender=sender)

- Notifikasi broadcast dikirim setelah operasi file selesai
- sender adalah socket client yang melakukan aksi, dikecualikan dari broadcast

---

### Class Server
python
class Server:
    def open_socket(self):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind((self.host, self.port))
        self.server.listen(5)

    def run(self):
        self.open_socket()
        while True:
            conn, addr = self.server.accept()
            t = ClientHandler(conn, addr)
            t.start()
            self.threads.append(t)

- Main thread hanya bertugas menerima koneksi baru (accept)
- Setiap koneksi baru langsung dibuat thread ClientHandler dan dijalankan
- Main thread langsung kembali menunggu koneksi berikutnya

---

### Kelebihan
- Multi-client dengan logika yang mudah dipahami (tiap client punya thread sendiri)
- Tidak perlu buffer per-client atau state machine
- Operasi blocking (seperti recv_msg) aman karena tiap thread independen

### Kekurangan
- Membuat thread baru untuk setiap client → overhead memori dan CPU meningkat seiring jumlah client
- Perlu sinkronisasi (lock) untuk data yang diakses bersama, rawan deadlock jika tidak hati-hati
- Jumlah thread yang bisa dibuat terbatas oleh sistem operasi

---

## client.py

Client digunakan untuk berinteraksi dengan server.

---

### Setup
```python
DOWNLOAD_DIR = "client_downloads"
```
- Folder untuk menyimpan file download  

```python
is_transferring = threading.Event()
```
- Digunakan untuk menandai apakah sedang upload/download  

---

### send_msg & recv_msg
Sama seperti server (length-prefix framing)

---

### Upload File
```python
def upload_file(sock, filename):
```

Alur:
1. Kirim `/upload`
2. Tunggu `READY_UPLOAD`
3. Kirim file per chunk
4. Kirim 0 sebagai tanda selesai  

---

### Download File
```python
def download_file(sock, filename):
```

Alur:
1. Kirim `/download`
2. Terima file dalam chunk
3. Simpan ke folder  

---

### Receive Loop (Thread)
```python
def receive_loop(sock):
```
- Thread terpisah untuk menerima pesan  
- Supaya tidak bentrok dengan input user  

---

### Input User
```python
while True:
    user_input = input(">> ")
```
- User bisa kirim command atau chat  

---

## Perbedaan Utama

| Aspek        | server_sync | server_select  | server_poll | server_thread |
|--------------|-------------|----------------|-------------|---------------|
| Model        | Blocking    | Non-blocking   | non-blocking | blocking per-thread |
| Client       | 1           | Banyak         | Banyak      | Banyak       |
| Mekanisme    | Loop biasa  | select()       | poll()      | thread per koneksi |
| Upload       | Bergantian  | Bersamaan      | Bersamaan   | Bersamaan    |
| Chat         | tidak bisa  | bisa           | bisa        | bisa         |
| Kompleksitas | Sederhana   | Lebih kompleks | Lebih kompleks | Sedikit lebih mudah |

---

## Kesimpulan

- server_sync: paling sederhana, cocok untuk memahami dasar framing + transfer.
- server_select: cocok untuk multi-client, I/O multiplexing dengan `select`, ada chat/broadcast.
- server_poll: mirror select tapi poll()-based, lebih scalable (Unix/Linux) tanpa limit fd.
- server_thread: model per-client thread, implementasi intuitif tetapi overhead lebih tinggi.

## Screenshot Hasil

### server_sync.py

#### akan terjadi blocking ketika lebih dari sama dengan 2 client terhubung pada server_Sync

<img width="1878" height="1196" alt="image" src="https://github.com/user-attachments/assets/f7e005a1-8020-40d0-838c-77795b7482c9" />

### server_select.py

#### penggunaan `/list`, `/upload`, `/download`, serta `/quit`

<img width="1912" height="1195" alt="image" src="https://github.com/user-attachments/assets/b41b1ad1-3fff-4acc-924b-c2fe3865b078" />

<img width="1899" height="1174" alt="image" src="https://github.com/user-attachments/assets/0f433c29-0a28-497a-862e-8f4414634182" />

#### hasil `/download` file `dump.txt` dan `FireFly.jpeg`

<img width="1332" height="1138" alt="image" src="https://github.com/user-attachments/assets/5ceafde1-2e47-44ab-ac91-c015803c92a4" />

<img width="1874" height="1113" alt="image" src="https://github.com/user-attachments/assets/2cafca6f-1d52-4224-8b9d-ac72f6fb2018" />

#### penggunaan fitur broadcast

<img width="1901" height="512" alt="image" src="https://github.com/user-attachments/assets/9129dac3-61fd-458c-83cd-1835a50216ff" />

### server_thread.py

![WhatsApp Image 2026-03-25 at 22 28 33](https://github.com/user-attachments/assets/e34a7ede-4ea8-4edd-90a2-144b0849eeff)

### server_poll.py

![WhatsApp Image 2026-03-25 at 22 29 37](https://github.com/user-attachments/assets/8c988ee8-584a-447f-b891-40288d2753af)
