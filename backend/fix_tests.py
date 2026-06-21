import re
import glob

test_files = glob.glob('tests/**/*.py', recursive=True)

for file in test_files:
    with open(file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find async def test_...
    # Replace def test_name(client: AsyncClient): with def test_name(client: AsyncClient, verify_user):
    # Replace def test_name(client: AsyncClient, db_session): with def test_name(client: AsyncClient, db_session, verify_user):
    # Replace def test_name(client: AsyncClient, db_session, monkeypatch): with def test_name(client: AsyncClient, db_session, monkeypatch, verify_user):
    
    content = re.sub(r'def test_([a-zA-Z0-9_]+)\(client: AsyncClient\):', r'def test_\1(client: AsyncClient, verify_user):', content)
    content = re.sub(r'def test_([a-zA-Z0-9_]+)\(client: AsyncClient, db_session\):', r'def test_\1(client: AsyncClient, db_session, verify_user):', content)
    content = re.sub(r'def test_([a-zA-Z0-9_]+)\(client: AsyncClient, db_session, monkeypatch\):', r'def test_\1(client: AsyncClient, db_session, monkeypatch, verify_user):', content)
    
    # Now, find ssert reg_resp.status_code == 201 and insert wait verify_user(email)
    # Or find /api/v1/auth/register" ... json={"email": email, ...} 
    
    # Some tests use json={"email": email and some use json={"email": "..."}
    # We can just look for the first POST to /api/v1/auth/register and add a verify_user call.
    
    with open(file, 'w', encoding='utf-8') as f:
        f.write(content)

print('Updated signatures')
