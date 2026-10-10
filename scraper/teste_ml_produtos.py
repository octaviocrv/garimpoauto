import os
import httpx
from dotenv import load_dotenv

load_dotenv()

r = httpx.post(
    "https://api.mercadolibre.com/oauth/token",
    data={
        "grant_type": "client_credentials",
        "client_id": os.environ["ML_CLIENT_ID"],
        "client_secret": os.environ["ML_CLIENT_SECRET"],
    },
    timeout=15,
)
h = {"Authorization": f"Bearer {r.json()['access_token']}"}

for q in ["honda civic 2018", "gol 2015"]:
    x = httpx.get(
        "https://api.mercadolibre.com/products/search",
        params={"status": "active", "site_id": "MLB", "q": q},
        headers=h,
        timeout=15,
    )
    print(q, "->", x.status_code)
    if x.status_code == 200:
        d = x.json()
        print("total:", d.get("paging", {}).get("total"))
        for p in d.get("results", [])[:5]:
            print(" -", p.get("name"), "|", p.get("domain_id"))