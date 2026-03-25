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

## Penjelasan Program

## Penjelasan Program

### Overview
Program ini merupakan implementasi **TCP File Server** dengan dua pendekatan:
- **server_sync.py** -> server synchronous (blocking, 1 client)
- **server_select.py** -> server non-blocking (multi-client dengan `select`)
- **client.py** -> client untuk upload, download, list, dan chat

---

### server_sync.py (Synchronous Server)

Server ini bekerja secara **blocking**, artinya hanya dapat menangani **1 klien dalam satu waktu**.

Alur kerjanya yaitu, setiap klien yang terhubung akan diproses dalam fungsi `handle_client()` yang berisi loop untuk terus menerima pesan dari klien menggunakan `recv_msg()`.

```python
def handle_client(conn, addr):
    while True:
        data = recv_msg(conn)
```

#### List File
Perintah `/list` akan menampilkan seluruh file yang ada di folder server.

#### Upload File
Ketika klien mengirim perintah `/upload`, server akan:
1. Mengambil nama file misalnya `FireFly.jpeg`
2. Menyimpan file `FireFly.jpeg` ke folder `server_files`
3. Menerima data dalam bentuk blok (chunk)

```python
elif message.startswith("/upload "):
    filename = message[len("/upload "):].strip()
    filepath = os.path.join(UPLOAD_DIR, os.path.basename(filename))
    with open(filepath, "wb") as f:
        # menerima data file dalam blok - blok sampai panjang = 0
```

- File disimpan ke:
```python
UPLOAD_DIR = "server_files"
```

- Transfer file dilakukan per **chunk**, dan berhenti saat panjang = 0.

#### Download File
Ketika klien melakukan `/download`:
1. Server mengecek apakah file ada di `server_files`
2. Jika ada, file dibaca
3. Dikirim ke klien dalam bentuk chunk

```python
with open(filepath, "rb") as f:
    while True:
        chunk = f.read(4096)
```

#### Framing Data
Fungsi komunikasi menggunakan **length-prefix framing**:

```python
def send_msg(sock, data):
    header = struct.pack(">I", len(data))
```

- 4 byte pertama -> panjang pesan
- Memastikan data tidak tercampur atau partial read

#### Kelemahan
- Hanya melayani **1 klien dalam satu waktu**
- Jika ada klien upload file besar, klien lain harus menunggu

---

### server_select.py (Non-blocking Server dengan select)

Server ini menggunakan `select` sehingga dapat menangani **banyak klien sekaligus (concurrent)** tanpa blocking.

#### Hal Utama
- `select.select()` → memonitor banyak socket sekaligus
- Tidak perlu thread, cukup 1 loop utama

```python
read_ready, _, _ = select.select(input_sockets, [], [])
```

#### Manajemen Client
```python
clients = {}
recv_buffers = {}
upload_state = {}
```

- `clients` -> menyimpan daftar klien
- `recv_buffers` -> buffer data yang belum lengkap
- `upload_state` -> status upload tiap klien

#### Menerima Pesan (Non-blocking)
Berbeda dari server sync, di sini digunakan buffer:

```python
def try_recv_msg(sock):
```

- Data bisa datang sebagian atau partial
- Disimpan dulu sampai lengkap baru diproses

#### Upload File
Saat klien upload:
1. Server menyimpan state upload
2. Data diterima bertahap melalui `handle_upload_data()`

```python
upload_state[sock] = {
    "filename": filename,
    "file": open(filepath, "wb"),
    "buf": b""
}
```

- Sama seperti sebelumnya, file dikirim dalam bentuk chunk
- Jika panjang = 0 → upload selesai

```python
if length == 0:
    state["file"].close()
```

#### Download File
- Sama seperti pada server_sync  
- Bedanya bisa dilakukan oleh banyak klien secara bersamaan

#### Broadcast (Chat)
```python
def broadcast(message, exclude=None):
```

- Semua pesan non-command akan dikirim ke semua klien
- Menambahkan fitur chat antar user

#### Kelebihan
- Bisa menangani banyak klien sekaligus
- Tidak blocking
- Lebih efisien untuk banyak koneksi

---
## Screenshot Hasil
