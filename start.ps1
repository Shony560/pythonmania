$env:Path = [System.Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [System.Environment]::GetEnvironmentVariable('Path', 'User')
Write-Host "Starting Docker Compose..."
docker compose up -d
Write-Host "Creating Virtual Environment..."
python -m venv venv
Write-Host "Installing requirements..."
.\venv\Scripts\python.exe -m pip install -r requirements.txt
Write-Host "Starting Flask App..."
.\venv\Scripts\python.exe app.py
