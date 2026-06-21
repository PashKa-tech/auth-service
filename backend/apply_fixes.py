import os

fixes = {
    'tests/api/v1/test_auth.py': [
        ('json={"email": "login@example.com", "password": "password123"},', 'json={"email": "login@example.com", "password": "password123"},\n        headers=HEADERS\n    )\n    await verify_user("login@example.com")'),
    ],
    'tests/test_2fa.py': [
        ('assert reg_resp.status_code == 201', 'assert reg_resp.status_code == 201\n    await verify_user(email)'),
        ('await client.post("/api/v1/auth/register", headers=headers, json={"email": email, "password": password})', 'await client.post("/api/v1/auth/register", headers=headers, json={"email": email, "password": password})\n    await verify_user(email)'),
    ],
    'tests/test_anomaly.py': [
        ('assert reg_resp.status_code == 201', 'assert reg_resp.status_code == 201\n    await verify_user(email)'),
    ],
    'tests/test_auth.py': [
        ('assert reg_resp.json()["data"]["email"] == email', 'assert reg_resp.json()["data"]["email"] == email\n    await verify_user(email)'),
    ],
    'tests/test_email.py': [
        ('user_obj = me_check.scalar_one()\n        assert user_obj.is_verified is False', 'user_obj = me_check.scalar_one()\n        assert user_obj.is_verified is False\n        await verify_user(email)'),
        ('assert reset_resp.json()["success"] is True\n', 'assert reset_resp.json()["success"] is True\n    await verify_user(email)\n'),
        ('assert reg_resp.status_code == 201', 'assert reg_resp.status_code == 201\n    await verify_user(email)'),
    ],
    'tests/test_metrics.py': [
        ('        await client.post(\n            "/api/v1/auth/register",\n            headers=headers,\n            json={"email": email, "password": password}\n        )', '        await client.post(\n            "/api/v1/auth/register",\n            headers=headers,\n            json={"email": email, "password": password}\n        )\n        await verify_user(email)'),
    ],
    'tests/test_rbac.py': [
        ('user_id = reg_resp.json()["data"]["id"]', 'user_id = reg_resp.json()["data"]["id"]\n    await verify_user(email)'),
    ],
    'tests/test_webauthn.py': [
        ('        await client.post(\n            "/api/v1/auth/register",\n            headers=headers,\n            json={"email": email, "password": password}\n        )', '        await client.post(\n            "/api/v1/auth/register",\n            headers=headers,\n            json={"email": email, "password": password}\n        )\n        await verify_user(email)'),
    ]
}

for file, edits in fixes.items():
    if os.path.exists(file):
        with open(file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        for search, replace in edits:
            # We don't want to replace multiple times if it's already there
            if content.count(replace) == 0:
                content = content.replace(search, replace)
        
        with open(file, 'w', encoding='utf-8') as f:
            f.write(content)

print("Applied precise edits to test files.")
