import serial
import pynmea2
import time
import sys
import os
import glob
import csv
import json
import webbrowser
from datetime import datetime

PORT = 'COM4'  
BAUDRATE = 9600
PARITY = 'N'          
STOPBITS = 1            
BYTESIZE = 8
TIMEOUT = 0.5   

def generate_map_html(csv_path):
    """
    Generuje plik HTML z mapą trasy na podstawie pliku CSV.
    """
    points = []
    try:
        with open(csv_path, 'r', newline='') as f:
            reader = csv.reader(f)
            try:
                header = next(reader) # Pomiń nagłówek
                if header != ['timestamp', 'latitude', 'longitude']:
                    print("Ostrzeżenie: Plik CSV ma nieoczekiwany nagłówek.")
            except StopIteration:
                print("Błąd: Plik CSV jest pusty.")
                return

            for i, row in enumerate(reader):
                if len(row) >= 3:
                    try:
                        # Format: [lat, lon, timestamp, numer_punktu]
                        points.append([float(row[1]), float(row[2]), row[0], i + 1])
                    except ValueError:
                        print(f"Pominięto błędną linię w CSV: {row}")
                
    except FileNotFoundError:
        print(f"Błąd: Nie znaleziono pliku {csv_path}")
        return
    except Exception as e:
        print(f"Błąd podczas odczytu pliku CSV: {e}")
        return

    if not points:
        print("Brak punktów do wyświetlenia na mapie.")
        return

    # Konwertuj dane na format JSON do osadzenia w HTML
    track_data_json = json.dumps(points)

    # Szablon HTML
    html_content = f"""
    <!DOCTYPE html>
    <html lang="pl">
    <head>
        <meta charset="utf-8">
        <title>Mapa Trasy - {os.path.basename(csv_path)}</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <!-- Leaflet CSS -->
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
             integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="
             crossorigin=""/>
        <!-- Leaflet JS -->
        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
             integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo="
             crossorigin=""></script>
        <style>
            html, body {{
                height: 100%;
                margin: 0;
                padding: 0;
                font-family: 'Arial', sans-serif;
            }}
            #map {{
                height: 95%;
                width: 100%;
            }}
            #title {{
                height: 5%;
                text-align: center;
                padding-top: 5px;
                box-sizing: border-box;
            }}
        </style>
    </head>
    <body>
        <div id="title">
            <h3>Trasa z pliku: {os.path.basename(csv_path)}</h3>
        </div>
        <div id="map"></div>
        <script>
            // Osadzone dane trasy
            const trackData = {track_data_json};

            if (trackData.length === 0) {{
                document.getElementById('map').innerHTML = "Brak danych do wyświetlenia.";
            }} else {{
                // Ustaw widok mapy na pierwszy punkt
                const map = L.map('map').setView([trackData[0][0], trackData[0][1]], 16);

                // Dodaj warstwę mapy (OpenStreetMap)
                L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                }}).addTo(map);

                // Zbierz punkty dla linii
                const latLngs = trackData.map(p => [p[0], p[1]]);

                // Narysuj linię trasy
                const polyline = L.polyline(latLngs, {{ color: 'blue', weight: 5 }}).addTo(map);

                // Dodaj markery dla każdego punktu
                trackData.forEach(p => {{
                    const lat = p[0];
                    const lon = p[1];
                    const timestamp = p[2];
                    const pointNum = p[3];

                    const popupContent = `<b>Punkt #${pointNum}</b><br>Czas: ${timestamp}<br>Lat: ${lat.toFixed(6)}<br>Lon: ${lon.toFixed(6)}`;
                    
                    L.marker([lat, lon])
                        .addTo(map)
                        .bindPopup(popupContent);
                }});

                // Dodaj marker startowy
                L.marker(latLngs[0], {{ title: 'Start' }})
                    .addTo(map)
                    .bindPopup("<b>START</b><br>" + popupContent(trackData[0]));

                // Dodaj marker końcowy
                L.marker(latLngs[latLngs.length - 1], {{ title: 'Koniec' }})
                    .addTo(map)
                    .bindPopup("<b>KONIEC</b><br>" + popupContent(trackData[trackData.length - 1]));
                    
                function popupContent(pointData) {{
                    return `<b>Punkt #${pointData[3]}</b><br>Czas: ${pointData[2]}<br>Lat: ${pointData[0].toFixed(6)}<br>Lon: ${pointData[1].toFixed(6)}`;
                }}

                // Dopasuj mapę, aby pokazać całą trasę
                map.fitBounds(polyline.getBounds().pad(0.1));
            }}
        </script>
    </body>
    </html>
    """

    # Zapisz i otwórz mapę
    map_filename = "mapa_trasy.html"
    try:
        with open(map_filename, "w", encoding="utf-8") as f:
            f.write(html_content)
        webbrowser.open(f"file://{os.path.realpath(map_filename)}")
        print(f"Wygenerowano i otwarto plik: {map_filename}")
    except Exception as e:
        print(f"Nie udało się zapisać lub otworzyć mapy: {e}")


def select_file(create_new=False):
    """
    Wyświetla listę plików .csv i pozwala użytkownikowi wybrać lub utworzyć nowy.
    """
    print("\nWybierz plik logu:")
    files = sorted(glob.glob("*.csv"))
    
    if not files and not create_new:
        print("Nie znaleziono żadnych plików .csv.")
        return None

    for i, f in enumerate(files):
        print(f" {i+1}. {f}")
    
    if create_new:
        print(" 0. [Utwórz nowy plik]")
    
    choice = input("Twój wybór: ")

    try:
        choice_num = int(choice)
        if create_new and choice_num == 0:
            new_filename = input("Podaj nazwę dla nowego pliku (bez .csv): ")
            if not new_filename:
                print("Anulowano.")
                return None
            if not new_filename.endswith(".csv"):
                new_filename += ".csv"
            print(f"Utworzono plik: {new_filename}")
            return new_filename
        elif 0 < choice_num <= len(files):
            return files[choice_num - 1]
        else:
            print("Nieprawidłowy wybór.")
            return None
    except ValueError:
        print("Nieprawidłowy wybór.")
        return None


def main():
    polaczenie = None
    is_logging = False
    current_log_file = None
    csv_writer = None
    log_filename = ""

    try:
        polaczenie = serial.Serial(
            port=PORT,
            baudrate=BAUDRATE,
            parity=PARITY,
            stopbits=STOPBITS,
            bytesize=BYTESIZE,
            timeout=TIMEOUT
        )
        print(f"Połączono z {PORT}. Oczekiwanie na STM32...")

        while True:
            line = polaczenie.readline().decode('utf-8', errors='ignore').strip()
            if line:
                print(line)
                if "Nasluch DMA" in line or "READY" in line:
                    break
            else:
                print("Nie odebrano komunikatu startowego z STM32.")
                break

        while True:
            print("\n=== MENU BOI ===")
            print(" 'g' - odczyt danych GPS")
            print(" 'r' - (ponowna) rekonfiguracja GPS (Brute Force)")
            if is_logging:
                print(f" 's' - Zakończ zapis trasy do pliku ({log_filename})")
            else:
                print(" 's' - Rozpocznij zapis trasy do pliku")
            print(" 'm' - Wyświetl trasę na mapie z pliku")
            print(" 'q' - wyjscie")
            a = input("Wybierz komendę: ")

            if a == 'q':
                print("Zamykanie...")
                break  

            elif a == 's': # Start/Stop logowania
                if not is_logging:
                    filename = select_file(create_new=True)
                    if filename:
                        try:
                            file_is_new = not os.path.exists(filename) or os.path.getsize(filename) == 0
                            
                            # Użyj 'a' (append) aby nie nadpisywać istniejących danych
                            current_log_file = open(filename, 'a', newline='', encoding='utf-8')
                            csv_writer = csv.writer(current_log_file)
                            
                            if file_is_new:
                                # Zapisz nagłówek tylko jeśli plik jest nowy
                                csv_writer.writerow(["timestamp", "latitude", "longitude"])
                                current_log_file.flush()
                            
                            log_filename = filename
                            is_logging = True
                            print(f"Rozpoczęto zapis do pliku: {log_filename}")

                        except IOError as e:
                            print(f"Błąd otwierania pliku {filename}: {e}")
                            if current_log_file:
                                current_log_file.close()
                            current_log_file = None
                            csv_writer = None
                else:
                    if current_log_file:
                        current_log_file.close()
                        current_log_file = None
                        csv_writer = None
                    is_logging = False
                    print(f"Zakończono zapis do pliku: {log_filename}")
                    log_filename = ""
            
            elif a == 'm': # Generuj mapę
                print("Wybierz plik CSV do wygenerowania mapy:")
                filename = select_file(create_new=False)
                if filename:
                    generate_map_html(filename)

            elif a == 'g':
                print("Wysyłam 'g'...")
                polaczenie.write(b'g')
                
                print("Odbieranie danych GPS... (Naciśnij Ctrl+C aby wrócić do menu)")
                try:
                    while True:
                        line = polaczenie.readline().decode('utf-8', errors='ignore').strip()
                        if not line:
                            continue
                        
                        if line.startswith("$G"):
                            try:
                                msg = pynmea2.parse(line)
                                if hasattr(msg, 'latitude') and msg.latitude is not None and msg.latitude != 0.0:
                                    # Generuj pełny timestamp jeśli brakuje daty (powszechne w RMC/GGA)
                                    if isinstance(msg.timestamp, time.struct_time):
                                        display_time = msg.timestamp.strftime('%H:%M:%S')
                                        log_timestamp = f"{datetime.now().date()}T{display_time}Z"
                                    elif msg.timestamp:
                                        display_time = str(msg.timestamp)
                                        log_timestamp = f"{datetime.now().date()}T{display_time}Z"
                                    else:
                                        display_time = "Brak czasu"
                                        log_timestamp = datetime.now().isoformat()

                                    print(f"[NMEA] {msg.sentence_type}:")
                                    print(f"  Czas: {display_time}")
                                    print(f"  Szerokość: {msg.latitude:.6f} {msg.lat_dir}")
                                    print(f"  Długość:  {msg.longitude:.6f} {msg.lon_dir}")
                                    if hasattr(msg, 'num_sats'):
                                        print(f"  Saty: {msg.num_sats}")

                                    # Logowanie do pliku CSV
                                    if is_logging and csv_writer:
                                        csv_writer.writerow([log_timestamp, msg.latitude, msg.longitude])
                                        current_log_file.flush() # Wymuś zapis na dysk
                                else:
                                    if "GGA" in line or "RMC" in line:
                                        print(f"Odebrano {msg.sentence_type}, ale brak fixa (lat: {msg.latitude})")
                                    # print(line) # Drukuj inne linie NMEA
                            
                            except pynmea2.nmea.ChecksumError:
                                print(f"Błąd sumy kontrolnej: {line}")
                            except Exception as e:
                                print(f"Błąd parsowania: {e} | Linia: {line}")
                        
                        elif "Koniec odczytu" in line:
                            print("=== Koniec odczytu GPS (sygnał z STM32) ===")
                            break
                        else:
                            # Drukuj inne komunikaty z STM32
                            print(f"[STM32] {line}")

                except KeyboardInterrupt:
                    print("\nZatrzymano odczyt GPS. Powrót do menu...")
                    # Wyślij do STM32 sygnał zatrzymania, jeśli taki istnieje (np. 'x')
                    # polaczenie.write(b'x') 


            elif a == 'r':
                print("Wysyłam 'r' (rekonfiguracja)...")
                polaczenie.write(b'r')          
                polaczenie.timeout = 15.0  
                
                print("Oczekiwanie na zakończenie rekonfiguracji...")
                while True:
                    line = polaczenie.readline().decode('utf-8', errors='ignore').strip()
                    if line:
                        print(line)
                        if "Koniec 'Brute Force'" in line:
                            break
                    else:
                        print("[Timeout podczas 'Brute Force']")
                        break
                polaczenie.timeout = TIMEOUT 

            else:
                print(f"Nieznana komenda: '{a}'")

    except serial.SerialException as e:
        print(f"KRYTYCZNY BŁĄD: Nie można otworzyć portu {PORT}.")
        print(f"Szczegóły: {e}")
        print("Upewnij się, że STM32 jest podłączony i nie jest używany przez inny program (np. terminal).")
    except KeyboardInterrupt:
        print("\nPrzerwano przez użytkownika.")
    finally:
        if is_logging and current_log_file:
            current_log_file.close()
            print(f"Zamknięto plik logu: {log_filename}")
        if polaczenie and polaczenie.is_open:
            polaczenie.close()
            print(f"Połączenie z {PORT} zamknięte.")

if __name__ == "__main__":
    main()