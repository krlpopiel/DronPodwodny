#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Skrypt nawigacji GPS dla Raspberry Pi
Prowadzi użytkownika przez trasę punktów nawigacyjnych w czasie rzeczywistym.
"""

import serial
import pynmea2
import threading
import json
import os
import time
import math
from datetime import datetime

# ================================
# KONFIGURACJA
# ================================
PORT = '/dev/ttyACM0'  # Linux/Raspberry Pi (zmień na 'COM3' dla Windows)
BAUDRATE = 9600
PROMIEN_DOTARCIA = 5.0  # Odległość w metrach uznawana za "dotarcie" do punktu

# ================================
# ZMIENNE GLOBALNE
# ================================
stop_event = threading.Event()
gps_lock = threading.Lock()
current_lat = None
current_lon = None
current_heading = None  # Kierunek ruchu (z RMC)
has_fix = False


# ================================
# FUNKCJE NAWIGACYJNE
# ================================

def haversine(lat1, lon1, lat2, lon2):
    """
    Oblicza odległość między dwoma punktami GPS (w metrach).
    Używa wzoru Haversine.
    """
    R = 6371000  # Promień Ziemi w metrach
    
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    
    a = math.sin(delta_phi / 2) ** 2 + \
        math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return R * c


def oblicz_azymut(lat1, lon1, lat2, lon2):
    """
    Oblicza azymut (bearing) od punktu 1 do punktu 2.
    Zwraca kąt w stopniach (0-360, gdzie 0=północ, 90=wschód).
    """
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lon = math.radians(lon2 - lon1)
    
    x = math.sin(delta_lon) * math.cos(lat2_rad)
    y = math.cos(lat1_rad) * math.sin(lat2_rad) - \
        math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(delta_lon)
    
    azymut = math.atan2(x, y)
    azymut_deg = math.degrees(azymut)
    
    # Normalizuj do 0-360
    return (azymut_deg + 360) % 360


def roznica_katow(kat1, kat2):
    """
    Oblicza różnicę między dwoma kątami.
    Zwraca wartość od -180 do 180 stopni.
    Dodatnia = skręt w prawo, Ujemna = skręt w lewo.
    """
    diff = kat2 - kat1
    while diff > 180:
        diff -= 360
    while diff < -180:
        diff += 360
    return diff


def kierunek_do_tekstu(roznica):
    """
    Zamienia różnicę kątów na instrukcję tekstową.
    """
    if abs(roznica) < 10:
        return "↑ IDŹ PROSTO"
    elif abs(roznica) < 45:
        if roznica > 0:
            return f"↗ LEKKO W PRAWO (~{abs(int(roznica))}°)"
        else:
            return f"↖ LEKKO W LEWO (~{abs(int(roznica))}°)"
    elif abs(roznica) < 90:
        if roznica > 0:
            return f"→ SKRĘĆ W PRAWO (~{abs(int(roznica))}°)"
        else:
            return f"← SKRĘĆ W LEWO (~{abs(int(roznica))}°)"
    elif abs(roznica) < 135:
        if roznica > 0:
            return f"↘ OSTRO W PRAWO (~{abs(int(roznica))}°)"
        else:
            return f"↙ OSTRO W LEWO (~{abs(int(roznica))}°)"
    else:
        return f"↓ ZAWRÓĆ (~{abs(int(roznica))}°)"


def azymut_do_kierunku(azymut):
    """
    Zamienia azymut na kierunek świata.
    """
    kierunki = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    idx = int((azymut + 22.5) // 45) % 8
    return kierunki[idx]


# ================================
# OBSŁUGA PLIKU TRASY
# ================================

def wczytaj_trase(sciezka):
    """
    Wczytuje trasę z pliku JSON.
    """
    if not os.path.exists(sciezka):
        print(f"❌ Plik trasy nie istnieje: {sciezka}")
        return None
    
    try:
        with open(sciezka, 'r', encoding='utf-8') as f:
            trasa = json.load(f)
        print(f"✅ Wczytano trasę: {trasa.get('nazwa', 'Bez nazwy')}")
        print(f"📍 Liczba punktów: {len(trasa.get('punkty', []))}")
        return trasa
    except Exception as e:
        print(f"❌ Błąd wczytywania trasy: {e}")
        return None


def zapisz_trase(sciezka, trasa):
    """
    Zapisuje trasę do pliku JSON (aktualizacja statusu odwiedzonych punktów).
    """
    try:
        with open(sciezka, 'w', encoding='utf-8') as f:
            json.dump(trasa, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"❌ Błąd zapisu trasy: {e}")
        return False


def znajdz_nastepny_punkt(trasa):
    """
    Znajduje pierwszy nieodwiedzony punkt na trasie.
    """
    for punkt in trasa.get('punkty', []):
        if not punkt.get('odwiedzony', False):
            return punkt
    return None


def oznacz_jako_odwiedzony(trasa, punkt_id):
    """
    Oznacza punkt jako odwiedzony.
    """
    for punkt in trasa.get('punkty', []):
        if punkt.get('id') == punkt_id:
            punkt['odwiedzony'] = True
            return True
    return False


def policz_odwiedzone(trasa):
    """
    Liczy odwiedzone i nieodwiedzone punkty.
    """
    punkty = trasa.get('punkty', [])
    odwiedzone = sum(1 for p in punkty if p.get('odwiedzony', False))
    return odwiedzone, len(punkty)


# ================================
# ODCZYT GPS
# ================================

def parsuj_nmea(line):
    """
    Parsuje linię NMEA i aktualizuje globalne zmienne GPS.
    """
    global current_lat, current_lon, current_heading, has_fix
    
    try:
        msg = pynmea2.parse(line)
        
        # GGA - pozycja
        if isinstance(msg, pynmea2.GGA):
            if msg.latitude and msg.longitude:
                with gps_lock:
                    current_lat = msg.latitude
                    current_lon = msg.longitude
                    has_fix = True
        
        # RMC - pozycja i kierunek ruchu
        elif isinstance(msg, pynmea2.RMC):
            if msg.latitude and msg.longitude:
                with gps_lock:
                    current_lat = msg.latitude
                    current_lon = msg.longitude
                    has_fix = True
                    if msg.true_course:
                        current_heading = msg.true_course
                        
    except pynmea2.ParseError:
        pass
    except Exception:
        pass


def gps_reader_thread(ser):
    """
    Wątek odczytujący dane GPS z portu szeregowego.
    """
    while not stop_event.is_set():
        try:
            raw = ser.readline()
            if raw:
                line = raw.decode('utf-8', errors='ignore').strip()
                if line.startswith('$G'):
                    parsuj_nmea(line)
        except serial.SerialException as e:
            print(f"❌ Błąd portu szeregowego: {e}")
            break
        except Exception:
            continue


# ================================
# GŁÓWNA PĘTLA NAWIGACJI
# ================================

def wyswietl_status(cel, dystans, instrukcja, odwiedzone, wszystkie):
    """
    Wyświetla status nawigacji w konsoli.
    """
    os.system('cls' if os.name == 'nt' else 'clear')
    
    print("=" * 50)
    print("🧭 NAWIGACJA GPS - Raspberry Pi")
    print("=" * 50)
    
    with gps_lock:
        if has_fix:
            print(f"📡 GPS: {current_lat:.6f}, {current_lon:.6f}")
            if current_heading is not None:
                print(f"🧭 Kierunek ruchu: {current_heading:.0f}° ({azymut_do_kierunku(current_heading)})")
        else:
            print("📡 GPS: Oczekiwanie na sygnał...")
    
    print("-" * 50)
    
    if cel:
        print(f"🎯 CEL: {cel.get('nazwa', 'Punkt ' + str(cel.get('id', '?')))}")
        print(f"📏 Odległość: {dystans:.1f} m")
        print(f"\n{instrukcja}")
    else:
        print("✅ TRASA UKOŃCZONA!")
    
    print("-" * 50)
    print(f"📊 Postęp: {odwiedzone}/{wszystkie} punktów")
    print("\n[Ctrl+C] aby zakończyć")


def nawiguj(sciezka_trasy):
    """
    Główna funkcja nawigacji.
    """
    global current_lat, current_lon, current_heading, has_fix
    
    # Wczytaj trasę
    trasa = wczytaj_trase(sciezka_trasy)
    if not trasa:
        return
    
    # Otwórz port szeregowy
    try:
        ser = serial.Serial(PORT, BAUDRATE, timeout=1)
        print(f"✅ Połączono z GPS na porcie {PORT}")
    except Exception as e:
        print(f"❌ Nie można otworzyć portu {PORT}: {e}")
        print("Uruchamiam tryb symulacji (losowe współrzędne)...")
        ser = None
    
    # Uruchom wątek GPS
    if ser:
        gps_thread = threading.Thread(target=gps_reader_thread, args=(ser,))
        gps_thread.daemon = True
        gps_thread.start()
    
    print("⏳ Oczekiwanie na sygnał GPS...")
    time.sleep(2)
    
    try:
        while not stop_event.is_set():
            # Znajdź następny cel
            cel = znajdz_nastepny_punkt(trasa)
            odwiedzone, wszystkie = policz_odwiedzone(trasa)
            
            if not cel:
                wyswietl_status(None, 0, "", odwiedzone, wszystkie)
                print("\n🎉 Gratulacje! Ukończyłeś całą trasę!")
                break
            
            with gps_lock:
                lat = current_lat
                lon = current_lon
                heading = current_heading
                fix = has_fix
            
            if fix and lat and lon:
                # Oblicz odległość do celu
                dystans = haversine(lat, lon, cel['lat'], cel['lon'])
                
                # Sprawdź czy dotarliśmy do punktu
                if dystans <= PROMIEN_DOTARCIA:
                    print(f"\n✅ Dotarłeś do: {cel.get('nazwa', 'Punkt ' + str(cel.get('id', '?')))}")
                    oznacz_jako_odwiedzony(trasa, cel['id'])
                    zapisz_trase(sciezka_trasy, trasa)
                    time.sleep(2)
                    continue
                
                # Oblicz azymut do celu
                azymut_do_celu = oblicz_azymut(lat, lon, cel['lat'], cel['lon'])
                
                # Oblicz instrukcję skrętu
                if heading is not None:
                    roznica = roznica_katow(heading, azymut_do_celu)
                    instrukcja = kierunek_do_tekstu(roznica)
                else:
                    # Jeśli nie mamy kierunku ruchu, podaj azymut
                    instrukcja = f"🧭 Kieruj się na: {azymut_do_celu:.0f}° ({azymut_do_kierunku(azymut_do_celu)})"
                
                wyswietl_status(cel, dystans, instrukcja, odwiedzone, wszystkie)
            else:
                wyswietl_status(cel, 0, "⏳ Oczekiwanie na GPS...", odwiedzone, wszystkie)
            
            time.sleep(1)  # Odświeżaj co sekundę
            
    except KeyboardInterrupt:
        print("\n\n👋 Zakończono nawigację.")
    finally:
        stop_event.set()
        if ser:
            ser.close()


# ================================
# MAIN
# ================================

def main():
    """
    Główna funkcja programu.
    """
    print("=" * 50)
    print("🧭 SYSTEM NAWIGACJI GPS")
    print("=" * 50)
    print("\nOpcje:")
    print("1 - Nawiguj po trasie")
    print("3 - Wyjdź")
    
    while True:
        wybor = input("\nWybór: ").strip()
        
        if wybor == '1':
            sciezka = input("Podaj ścieżkę do pliku trasy (JSON): ").strip()
            if not sciezka:
                sciezka = "trasa.json"
            nawiguj(sciezka)
            break
            
        elif wybor == '3':
            print("👋 Do widzenia!")
            break
        else:
            print("❌ Nieprawidłowy wybór")


if __name__ == "__main__":
    main()
