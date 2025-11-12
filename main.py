import serial
import pynmea2
import time
import sys

PORT = 'COM4'  
BAUDRATE = 9600
PARITY = 'N'          
STOPBITS = 1            
BYTESIZE = 8
TIMEOUT = 0.5  

def main():
    polaczenie = None  

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
            print(" 'q' - wyjscie")
            a = input("Wybierz komendę: ")

            if a == 'q':
                print("Zamykanie...")
                break  

            elif a == 'g':
                print("Wysyłam 'g'...")
                polaczenie.write(b'g')

                while True:
                    line = polaczenie.readline().decode('utf-8', errors='ignore').strip()
                    if not line:
                        continue
                    
                    if line.startswith("$G"):
                        try:
                            msg = pynmea2.parse(line)
                            if hasattr(msg, 'latitude'):
                                print(f"[NMEA] {msg.sentence_type}:")
                                print(f"  Czas: {msg.timestamp}")
                                print(f"  Szerokość: {msg.latitude} {msg.lat_dir}")
                                print(f"  Długość:  {msg.longitude} {msg.lon_dir}")
                                if hasattr(msg, 'num_sats'):
                                    print(f"  Saty: {msg.num_sats}")
                            else:
                                print(line)
                        except pynmea2.nmea.ChecksumError:
                            print(f"Błąd sumy kontrolnej: {line}")
                        except Exception as e:
                            print(f"Błąd parsowania: {e}")
                    
                    elif "Koniec odczytu" in line:
                        print("=== Koniec odczytu GPS ===")
                        break

            elif a == 'r':
                print("Wysyłam 'r' (rekonfiguracja)...")
                polaczenie.write(b'r')              
                polaczenie.timeout = 15.0  
                
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
        if polaczenie and polaczenie.is_open:
            polaczenie.close()
            print(f"Połączenie z {PORT} zamknięte.")

if __name__ == "__main__":
    main()
