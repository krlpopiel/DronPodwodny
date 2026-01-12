import csv
import glob
import pandas as pd

rows = []

for filename in sorted(glob.glob("gps_log_*.csv")):
    with open(filename, newline='', encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            nmea = row["dane"]

            if nmea.startswith("$GPGGA"):
                parts = nmea.split(",")

                if len(parts) >= 9:
                    sats = parts[7].strip()
                    hdop = parts[8].strip()

                    rows.append({
                        "Satelites": int(sats) if sats else None,
                        "HDOP": float(hdop) if hdop else None
                    })

df = pd.DataFrame(rows, columns=["Satelites", "HDOP"])
df.to_excel("gps.xlsx", index=False)

print("Zapisano plik gps.xlsx")
