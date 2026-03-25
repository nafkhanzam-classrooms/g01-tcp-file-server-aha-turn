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

```

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

| Aspek        | server_sync | server_select  |
|--------------|-------------|----------------|
| Model        | Blocking    | Non-blocking   |
| Client       | 1           | Banyak         |
| Mekanisme    | Loop biasa  | select()       |
| Upload       | Bergantian  | Bersamaan      |
| Chat         | tidak bisa  | bisa           |
| Kompleksitas | Sederhana   | Lebih kompleks |

---

## Kesimpulan

- **server_sync** -> sederhana, cocok untuk belajar dasar  
- **server_select** -> lebih powerful untuk multi-client  
- Menggunakan:
  - **length-prefix framing** -> untuk pesan
  - **chunked transfer** -> untuk file  

Kombinasi ini memastikan komunikasi aman, terstruktur, dan tidak terjadi data corruption
## Screenshot Hasil

### server_select.py

#### penggunaan `/list`, `/upload`, `/download`, serta `/quit`

<img width="1912" height="1195" alt="image" src="https://github.com/user-attachments/assets/b41b1ad1-3fff-4acc-924b-c2fe3865b078" />

<img width="1899" height="1174" alt="image" src="https://github.com/user-attachments/assets/0f433c29-0a28-497a-862e-8f4414634182" />

#### hasil `/download` file `dump.txt` dan `FireFly.jpeg`

<img width="1332" height="1138" alt="image" src="https://github.com/user-attachments/assets/5ceafde1-2e47-44ab-ac91-c015803c92a4" />

<img width="1874" height="1113" alt="image" src="https://github.com/user-attachments/assets/2cafca6f-1d52-4224-8b9d-ac72f6fb2018" />

#### penggunaan fitur broadcast

<img width="1901" height="512" alt="image" src="https://github.com/user-attachments/assets/9129dac3-61fd-458c-83cd-1835a50216ff" />
