cd C:\ai-platform\scripts

$env:DATABASE_URL="postgresql+psycopg2://postgres:SterkWachtwoord123@localhost:15432/promati"

python sync_org_rag_files_to_sql.py
pause