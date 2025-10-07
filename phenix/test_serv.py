import paramiko
import time
import socket

HOST = "172.21.192.70"
PORT = 22
USERNAME = "user"
PASSWORD = "ubuntu"   # або використай pkey
# PKEY example:
# key = paramiko.RSAKey.from_private_key_file("/home/user/.ssh/id_rsa")

def measure_connect_time():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    t0 = time.perf_counter()
    try:
        client.connect(HOST, port=PORT, username=USERNAME, password=PASSWORD, timeout=10)
    except Exception as e:
        print("Connect failed:", e)
        return None
    t1 = time.perf_counter()
    connect_time_ms = (t1 - t0) * 1000.0
    return client, connect_time_ms

def measure_command_rtt(client, cmd="echo hello"):
    # Виконуємо команду і міряємо час від відправки до повного отримання stdout
    t0 = time.perf_counter()
    stdin, stdout, stderr = client.exec_command(cmd)
    out = stdout.read()   # блокуючий — дочекаємось виконання
    t1 = time.perf_counter()
    rtt_ms = (t1 - t0) * 1000.0
    return rtt_ms, out.decode(errors="ignore")

if __name__ == "__main__":
    # 1) Вимірюємо час підключення
    res = measure_connect_time()
    if res is None:
        raise SystemExit(1)
    client, conn_ms = res
    print(f"Connect time: {conn_ms:.1f} ms")

    # 2) Кілька вимірів RTT для команди
    for i in range(1):
        rtt, out = measure_command_rtt(client, cmd="shutdown now")
        print(f"Command RTT #{i+1}: {rtt:.1f} ms, output: {out.strip()}")

    # 3) Закриваємо зʼєднання
    client.close()
