from datetime import datetime, date, time, timedelta, timezone
from zoneinfo import ZoneInfo
import csv, uuid

TZ = ZoneInfo("Europe/Prague")

def ics_escape(s: str) -> str:
    return s.replace("\\","\\\\").replace(";","\\;").replace(",","\\,").replace("\n","\\n")

def dt_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

def timed_event(start_local: datetime, end_local: datetime, summary: str, desc: str="") -> str:
    return "\n".join([
        "BEGIN:VEVENT",
        f"UID:{uuid.uuid4()}@shifts",
        f"DTSTAMP:{dt_utc(datetime.now(timezone.utc))}",
        f"DTSTART:{dt_utc(start_local)}",
        f"DTEND:{dt_utc(end_local)}",
        f"SUMMARY:{ics_escape(summary)}",
        *( [f"DESCRIPTION:{ics_escape(desc)}"] if desc else [] ),
        "END:VEVENT"
    ])

def all_day_event(d: date, summary: str, desc: str="") -> str:
    return "\n".join([
        "BEGIN:VEVENT",
        f"UID:{uuid.uuid4()}@shifts",
        f"DTSTAMP:{dt_utc(datetime.now(timezone.utc))}",
        f"DTSTART;VALUE=DATE:{d.strftime('%Y%m%d')}",
        f"DTEND;VALUE=DATE:{(d + timedelta(days=1)).strftime('%Y%m%d')}",  # neinkluzivní
        f"SUMMARY:{ics_escape(summary)}",
        *( [f"DESCRIPTION:{ics_escape(desc)}"] if desc else [] ),
        "END:VEVENT"
    ])

events = []

# def add_day_shift():
#     events.append(timed_event("07:00", "19:00", "Denní"))

# def add_night_shift():
#     events.append(timed_event("07:00", "19:00", "Denní"))

def main():
    global events
    with open("smeny.csv", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            d = datetime.strptime(r["date"], "%Y-%m-%d").date()
            summary = r.get("summary","Směna")
            desc = r.get("description","")
            if r.get("all_day","0") == "1":
                events.append(all_day_event(d, summary, desc))
            else:
                start = datetime.strptime(r["start"], "%H:%M").time()
                end = datetime.strptime(r["end"], "%H:%M").time()
                start_local = datetime.combine(d, start, tzinfo=TZ)
                end_local = datetime.combine(d, end, tzinfo=TZ)
                if end_local <= start_local:  # přes půlnoc
                    end_local += timedelta(days=1)
                events.append(timed_event(start_local, end_local, summary, desc))

    with open("smeny.ics", "w", encoding="utf-8") as out:
        out.write("BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//Shifts//CZ//\nCALSCALE:GREGORIAN\nMETHOD:PUBLISH\n")
        out.write("\n".join(events))
        out.write("\nEND:VCALENDAR\n")

def make_csv():
    start_date = date(2025, 9, 1)
    days = 30
    pattern = [
        ("06:00","14:00","Ranní",0),
        ("06:00","14:00","Ranní",0),
        ("14:00","22:00","Odpolední",0),
        ("14:00","22:00","Odpolední",0),
        ("22:00","06:00","Noční",0),
        ("22:00","06:00","Noční",0),
        ("","","Volno",1),
        ("","","Volno",1),
    ]

    with open("smeny.csv","w",newline="",encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date","start","end","summary","description","all_day"])
        d = start_date
        i = 0
        for _ in range(days):
            start_t, end_t, summary, all_day = pattern[i % len(pattern)]
            desc = "" if all_day == 1 else "Provoz 1"
            w.writerow([d.isoformat(), start_t, end_t, summary, desc, all_day])
            d += timedelta(days=1)
            i += 1

    print("Hotovo: smeny.csv")

main()
