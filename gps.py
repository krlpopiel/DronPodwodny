import serial
import pynmea2
import threading
import csv
import os
from datetime import datetime

# -------------------------------
# Konfiguracja portu COM
# -------------------------------
PORT = 'COM3'        # Zmień na swój port
BAUDRATE = 9600

# -------------------------------
# Zmienne globalne
# -------------------------------
is_logging = False
current_log_file = None
csv_writer = None
log_filename = None
stop_event = threading.Event()
writer_lock = threading.Lock()


# -------------------------------
# Funkcja wyboru lub utworzenia pliku CSV
# -------------------------------
def choose_or_create_file():
    global current_log_file, csv_writer, log_filename
    filename = input("Podaj nazwę pliku (bez rozszerzenia): ") + ".csv"
    log_filename = filename

    new_file = not os.path.exists(filename)
    current_log_file = open(filename, "a", newline='', encoding='utf-8')
    csv_writer = csv.writer(current_log_file)

    if new_file or os.path.getsize(filename) == 0:
        csv_writer.writerow(["timestamp", "latitude", "longitude"])


# -------------------------------
# Wątek odczytu danych z GPS
# -------------------------------
def serial_reader_thread(ser):
    global is_logging, current_log_file, csv_writer

    while not stop_event.is_set():
        try:
            line = ser.readline().decode('utf-8', errors='ignore').strip()
        except:
            continue

        if not line or not line.startswith("$G"):
            continue

        try:
            msg = pynmea2.parse(line)

            # Pobierz wartości GPS lub 0.0 jeśli brak fixa
            lat = getattr(msg, 'latitude', 0.0) or 0.0
            lon = getattr(msg, 'longitude', 0.0) or 0.0

            if is_logging and csv_writer:
                with writer_lock:
                    csv_writer.writerow([datetime.now().isoformat(), lat, lon])
                    current_log_file.flush()

        except:
            # W przypadku błędu parsowania zapisujemy 0,0
            if is_logging and csv_writer:
                with writer_lock:
                    csv_writer.writerow([datetime.now().isoformat(), 0.0, 0.0])
                    current_log_file.flush()


# -------------------------------
# Menu sterujące
# -------------------------------
def main():
    global is_logging, current_log_file, csv_writer

    try:
        ser = serial.Serial(PORT, BAUDRATE, timeout=1)
    except:
        return

    # Uruchom wątek odczytu danych GPS
    thread = threading.Thread(target=serial_reader_thread, args=(ser,))
    thread.daemon = True
    thread.start()

    # Proste menu sterujące
    while True:
        print("\n=== MENU ===")
        print("1 - wybierz/utwórz plik logu")
        print("2 - rozpocznij zapis")
        print("3 - zatrzymaj zapis")
        print("4 - zakończ program")
        cmd = input("Wybór: ").strip()

        if cmd == '1':
            choose_or_create_file()
        elif cmd == '2':
            if current_log_file:
                is_logging = True
        elif cmd == '3':
            is_logging = False
        elif cmd == '4':
            stop_event.set()
            thread.join()
            ser.close()
            if current_log_file:
                current_log_file.close()
            break


if __name__ == "__main__":
    main()
