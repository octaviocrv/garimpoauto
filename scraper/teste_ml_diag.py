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
print("Token:", r.status_code)
h = {"Authorization": f"Bearer {r.json()['access_token']}"}

base = "https://api.mercadolibre.com"
testes = [
    ("categorias do site", "/sites/MLB/categories", {}),
    ("categoria de carros", "/categories/MLB1744", {}),
    ("busca sem categoria", "/sites/MLB/search", {"q": "honda civic", "limit": 1}),
    ("busca com categoria", "/sites/MLB/search", {"category": "MLB1744", "limit": 1}),
    ("busca de produtos", "/products/search", {"status": "active", "site_id": "MLB", "q": "honda civic"}),
    ("meu usuario", "/users/me", {}),
]

for nome, caminho, params in testes:
    x = httpx.get(base + caminho, params=params, headers=h, timeout=15)
    print(f"{nome}: {x.status_code}")