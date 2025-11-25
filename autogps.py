import serial
import threading
import csv
import os
import time
from datetime import datetime

PORT = 'COM3'
BAUDRATE = 9600

CONNECTION_TIMEOUT = 5.0
RETRY_DELAY = 2.0

is_logging = False
current_log_file = None
csv_writer = None
log_filename = None
stop_event = threading.Event()
writer_lock = threading.Lock()
has_connection = False
last_seen = None
_has_connection_reported = None

def open_log_file():
    global current_log_file, csv_writer, log_filename, is_logging

    log_filename = f"gps_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    filename = log_filename
    new_file = not os.path.exists(filename)

    current_log_file = open(filename, "a", newline='', encoding="utf-8")
    csv_writer = csv.writer(current_log_file)

    if new_file or os.path.getsize(filename) == 0:
        csv_writer.writerow(["timestamp", "dane"])
        current_log_file.flush()

    is_logging = True
    print(f"Plik logu przygotowany: {filename}")

def close_log_file():
    global current_log_file, csv_writer, is_logging
    with writer_lock:
        if current_log_file:
            try:
                current_log_file.flush()
                os.fsync(current_log_file.fileno())
            except Exception:
                pass
            current_log_file.close()

        current_log_file = None
        csv_writer = None
        is_logging = False

def report_connection_status(status):
    global _has_connection_reported
    if status != _has_connection_reported:
        _has_connection_reported = status
        if status:
            print("Połączenie z GPS nawiązane.")
        else:
            print("Brak połączenia z GPS...")

def serial_reader_thread(ser):
    global last_seen, has_connection, csv_writer, current_log_file, is_logging

    while not stop_event.is_set():
        try:
            raw = ser.readline()
        except serial.SerialException as e:
            print("Błąd portu szeregowego:", e)
            stop_event.set()
            break
        except Exception:
            continue

        now = time.time()

        if not raw:
            if last_seen and (now - last_seen) > CONNECTION_TIMEOUT:
                has_connection = False
                report_connection_status(False)
            continue

        try:
            line = raw.decode('utf-8', errors='ignore').strip()
        except:
            continue

        if not line:
            continue

        is_ok = (line == "OK")
        is_nmea = line.startswith("$G")

        if is_ok or is_nmea:
            last_seen = now
            has_connection = True
            report_connection_status(True)

        if is_nmea:
            try:
                if is_logging and csv_writer:
                    with writer_lock:
                        csv_writer.writerow([datetime.now().isoformat(), line])
                        current_log_file.flush()
                        try:
                            os.fsync(current_log_file.fileno())
                        except Exception:
                            pass
            except Exception as e:
                print("Błąd zapisu:", e)

def try_open_serial(port, baudrate, timeout=1):
    while True:
        try:
            ser = serial.Serial(port, baudrate, timeout=timeout)
            print(f"Otwarto port {port} @ {baudrate}")
            return ser
        except KeyboardInterrupt:
            raise
        except Exception as e:
            print(f"Nie można otworzyć portu {port}: {e}. Próba ponownie za {RETRY_DELAY}s...")
            time.sleep(RETRY_DELAY)

def main():
    global is_logging

    open_log_file()

    try:
        ser = try_open_serial(PORT, BAUDRATE, timeout=1)
    except KeyboardInterrupt:
        print("Przerwano przez użytkownika.")
        return

    thread = threading.Thread(target=serial_reader_thread, args=(ser,))
    thread.daemon = True
    thread.start()

    print("Naciśnij Enter, aby zakończyć program.")

    try:
        input()
    except KeyboardInterrupt:
        print("\nPrzerwano (CTRL+C)")

    stop_event.set()
    thread.join(timeout=3.0)

    try:
        ser.close()
    except:
        pass

    close_log_file()
    print("Program zakończony.")

if __name__ == "__main__":
    main()
