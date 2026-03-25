# pythonmania — Project State

## What This App Does
A Flask-based **attendance/check-in app** with Kafka event streaming.
- Users log in, then click to mark attendance (Present/Late/Absent)
- Each action fires a Kafka event to the `user-events` topic
- SQLite (`attendance.db`) stores all attendance records

---

## Stack
| Component | Details |
|-----------|---------|
| **Backend** | Flask (Python), port `4567` |
| **Database** | Amazon RDS (**PostgreSQL**) |
| **Messaging** | Kafka on `localhost:9092`, topic: `user-events` |
| **Key files** | `app.py`, `consumer.py`, `requirements.txt`, `docker-compose.yml` |

---

## How to Start (Local)

> Docker Desktop must be running first (green status in system tray)

```powershell
# Usage: Start the app manually
docker compose up -d          # start Kafka
venv\Scripts\python.exe app.py # start Flask
```

Kafka creates venv → installs requirements → starts Flask.

To watch Kafka events in a second terminal:
```powershell
.\venv\Scripts\python.exe consumer.py
```

---

## EC2 Deployment

| Item | Value |
|------|-------|
| **IP** | `43.205.239.247` |
| **SSH Key** | `C:\Users\sho\Downloads\newset.ppk` (PuTTY format) |
| **User** | `ubuntu` |
| **Database** | Amazon RDS (PostgreSQL) |
| **App log** | `/home/ubuntu/pythonmania/app.log` |

### Connect via SSH:
```powershell
echo y | & "C:\Program Files\PuTTY\plink.exe" -i "C:\Users\sho\Downloads\newset.ppk" ubuntu@43.205.239.247
```

### Push local changes to EC2:
```powershell
& "C:\Program Files\PuTTY\pscp.exe" -i "C:\Users\sho\Downloads\newset.ppk" -r `
  app.py consumer.py requirements.txt docker-compose.yml static templates `
  ubuntu@43.205.239.247:/home/ubuntu/pythonmania/
```

### Automatic Deployment (Recommended):
Push to `main` branch. GitHub Actions handles the rest.

### Start services on EC2:
```bash
cd /home/ubuntu/pythonmania
sudo docker-compose up -d          # start Kafka
nohup ./venv/bin/python app.py > app.log 2>&1 &   # start Flask
```

### Watch Kafka events on EC2:
```bash
./venv/bin/python consumer.py
```

---

## Kafka Events Currently Fired

| Action | Kafka Event Sent? |
|--------|-------------------|
| Login | ✅ Yes |
| Register | ✅ Yes |
| **Check-in (mark_attendance)** | ❌ **Not yet — TODO** |

### TODO: Add Kafka event on check-in
In `app.py`, the `mark_attendance()` route (line ~145) saves to SQLite but **does not publish a Kafka event**.

Add this block after `conn.close()` (around line 160):
```python
if producer:
    try:
        event = {
            "username": session['username'],
            "action": "check_in",
            "status": status,
            "date": date_str,
            "time": time_str
        }
        producer.send('user-events', event)
        producer.flush()
    except Exception as e:
        print(f"Kafka error: {e}")
```

---

## Known Issues / Notes
- `bitnami/kafka:latest` is currently broken on Docker Hub — use `apache/kafka:3.7.0`
- Local Docker Desktop has been unstable (500 errors on engine); restart if `docker` commands fail
- WSL 2.6.3 was installed but requires a **reboot** to fully activate
- `docker-compose.yml` has been updated locally and on EC2 to use `apache/kafka:3.7.0`
