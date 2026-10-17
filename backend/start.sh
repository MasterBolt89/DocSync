# DocSync API – startup script
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
fi

source .venv/bin/activate
pip install -q -r requirements.txt

if [ ! -f ".env" ] && [ -f ".env.example" ]; then
  echo "No .env file found. Copying .env.example — remember to add your credentials."
  cp .env.example .env
fi

echo "Starting DocSync backend on http://localhost:8000"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
