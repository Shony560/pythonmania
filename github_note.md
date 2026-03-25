# Attendance App (Pythonmania)

A Flask-based attendance tracking application with Kafka event streaming and automated EC2 deployment.

## Features
- **User Authentication**: Simple login and registration.
- **Attendance Tracking**: Users can mark "Check In" and "Check Out".
- **Real-time Events**: Every action (Login, Check-in, Check-out) triggers a Kafka event to the `user-events` topic.
- **Dashboard**: View your own attendance history in a clean, modern interface.
- **Persistent Storage**: Data is stored in a local SQLite database (`attendance.db`).

## Tech Stack
- **Frontend**: Bootstrap 5, Jinja2 templates.
- **Backend**: Python Flask.
- **Messaging**: Apache Kafka.
- **Database**: SQLite3.
- **Infrastructure**: AWS EC2 (Ubuntu).

## How to Use

### Local Development
1. **Start Kafka**:
   ```powershell
   docker-compose up -d
   ```
2. **Setup Virtual Environment & Run**:
   ```powershell
   python -m venv venv
   .\venv\Scripts\activate
   pip install -r requirements.txt
   python app.py
   ```
3. **Access**: Visit `http://localhost:4567`.

### Monitoring Kafka Streams
To see the live event stream, run:
```powershell
python consumer.py
```

### Deployment
This app is set up for deployment to an EC2 instance. The GitHub action in `.github/workflows/deploy.yml` automatically deploys changes to the server on every push to the `main` branch.

**Requirements for Deployment:**
- `EC2_SSH_KEY`: Private SSH key as a GitHub secret.
- `EC2_HOST`: `43.205.239.247`.
- `EC2_USER`: `ubuntu`.
