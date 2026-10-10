import json
import os
import httpx
from dotenv import load_dotenv

load_dotenv()

# 1. pega o token do app
r = httpx.post(
    "https://api.mercadolibre.com/oauth/token",
    data={
        "grant_type": "client_credentials",
        "client_id": os.environ["ML_CLIENT_ID"],
        "client_secret": os.environ["ML_CLIENT_SECRET"],
    },
    timeout=15,
)
print("Token:", r.status_code)
if r.status_code != 200:
    print(r.text[:300])
    raise SystemExit

# 2. busca de carros usando o token
h = {"Authorization": f"Bearer {r.json()['access_token']}"}

r = httpx.get(
    "https://api.mercadolibre.com/sites/MLB/search",
    params={"category": "MLB1744", "q": "honda civic 2018", "limit": 5},
    headers=h,
    timeout=15,
)
print("Busca:", r.status_code)

if r.status_code == 200:
    data = r.json()
    print("Total:", data["paging"]["total"])
    with open("../dados/ml_exemplo.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("JSON salvo em dados/ml_exemplo.json")
else:
    print(r.text[:300])