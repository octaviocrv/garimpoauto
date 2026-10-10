"""Testes da fonte OLX. Rodar dentro de scraper/:

    .venv/bin/python -m pytest tests -v

Os testes normais são offline. O canário ao vivo só roda com OLX_LIVE=1.
"""

import json
import os
import sys
import unittest
from datetime import timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from config import LimitesBusca  # noqa: E402
from schemas import Busca  # noqa: E402
from sources import olx  # noqa: E402

FIXTURE = RAIZ / "tests" / "fixtures" / "olx_listagem.html"


def html_com_ads(ads, total=None):
    """Monta uma página mínima no mesmo formato da OLX (payload do Next + dataLayer)."""
    texto = 'a:["$","$L25",null,{"ads":' + json.dumps(ads, ensure_ascii=False) + "}]\n"
    corte = len(texto) // 2
    scripts = "".join(
        "<script>self.__next_f.push(%s)</script>" % json.dumps([1, p], ensure_ascii=False)
        for p in (texto[:corte], texto[corte:])
    )
    dl = ""
    if total is not None:
        corpo = {"page": {"detail": {"totalOfAds": total}}}
        dl = '<script id="datalayer">dataLayer.push(%s)</script>' % json.dumps(corpo)
    return f"<html><head>{dl}</head><body>{scripts}</body></html>"


def anuncio_cru(list_id, **extra):
    base = {
        "listId": list_id,
        "subject": f"Honda Civic {list_id}",
        "priceValue": "R$ 100.000",
        "url": f"https://mg.olx.com.br/x/honda-civic-{list_id}",
        "date": 1791572438,
        "professionalAd": False,
        "location": "Belo Horizonte, Centro",
        "locationDetails": {"municipality": "Belo Horizonte", "neighbourhood": "Centro", "uf": "MG"},
        "images": [{"original": f"https://img.olx.com.br/{list_id}.jpg"}],
        "properties": [
            {"name": "vehicle_brand", "value": "Honda"},
            {"name": "vehicle_model", "value": "Civic EXL"},
            {"name": "regdate", "value": "2018"},
            {"name": "mileage", "value": "80000"},
            {"name": "gearbox", "value": "Automático"},
            {"name": "fuel", "value": "Flex"},
        ],
    }
    base.update(extra)
    return base


class RespostaFalsa:
    def __init__(self, status=200, html=""):
        self.status = status
        self.html_content = html


class SessaoFalsa:
    """Devolve as respostas combinadas, uma por chamada de listagem, e guarda as URLs pedidas.
    Pedidos à API de filtros (marca, modelo, versão) não gastam resposta de listagem: respondem
    com o que estiver em `api` (pedaço do endereço -> lista) ou 404."""

    def __init__(self, respostas, api=None):
        self.respostas = list(respostas)
        self.api = api or {}
        self.urls = []

    def get(self, url, **kw):
        self.urls.append(url)
        if "/api/filters/" in url:
            for trecho, lista in self.api.items():
                if url.endswith(trecho):
                    return RespostaFalsa(200, "<html><body>" + json.dumps(lista) + "</body></html>")
            return RespostaFalsa(404, "")
        return self.respostas.pop(0) if self.respostas else RespostaFalsa(200, html_com_ads([], 0))

    @property
    def urls_de_listagem(self):
        return [u for u in self.urls if "/api/filters/" not in u]


class Relogio:
    """Tempo falso: dormir() só avança o relógio, ninguém espera de verdade."""

    def __init__(self):
        self.agora = 0.0
        self.esperas = []

    def dormir(self, s):
        self.esperas.append(s)
        self.agora += s

    def __call__(self):
        return self.agora


def limites(**kw):
    kw.setdefault("pausa_entre_paginas_segundos", (1.0, 1.0))
    return LimitesBusca(**kw)


def rodar(respostas, **kw):
    sessao, relogio = SessaoFalsa(respostas), Relogio()
    paginas = list(
        olx.buscar_paginas(
            Busca(texto="civic", estado="mg"), limites(**kw),
            sessao=sessao, dormir=relogio.dormir, relogio=relogio,
        )
    )
    return paginas, sessao, relogio


class ExtratorOffline(unittest.TestCase):
    """Lê o HTML salvo em tests/fixtures/, sem bater na OLX."""

    @classmethod
    def setUpClass(cls):
        if not FIXTURE.exists():
            raise unittest.SkipTest(f"falta o arquivo de exemplo {FIXTURE}")
        cls.itens, cls.total = olx.extrair_pagina(FIXTURE.read_text(encoding="utf-8"))

    def test_ignora_propaganda_e_le_o_total(self):
        self.assertEqual(len(self.itens), 5)  # o array tem 7 itens, 2 são só advertisingId
        self.assertTrue(all("listId" in i for i in self.itens))
        self.assertEqual(self.total, 78)

    def test_campos_do_primeiro_anuncio(self):
        a = olx.normalizar(self.itens[0])
        self.assertEqual(a.source, "olx")
        self.assertEqual(a.external_id, "1542831511")
        self.assertEqual(a.titulo, "Honda Civic EXL CVT 2018")
        self.assertEqual((a.marca, a.modelo), ("Honda", "Civic EXL CVT"))
        self.assertEqual((a.ano, a.km, a.preco), (2018, 118000, 107900))
        self.assertEqual((a.cambio, a.combustivel, a.cor, a.portas), ("Automático", "Flex", "Preto", 4))
        self.assertEqual((a.cidade, a.bairro, a.estado), ("Belo Horizonte", "Dona Clara", "MG"))
        self.assertIs(a.anunciante_profissional, True)
        self.assertEqual(a.nota_anunciante, 4.2)
        self.assertEqual(a.publicado_em.tzinfo, timezone.utc)
        self.assertTrue(a.imagens and all(i.startswith("https://") for i in a.imagens))
        self.assertFalse(a.incompleto)
        self.assertEqual(a.raw["listId"], 1542831511)

    def test_campo_vazio_vira_none_sem_inventar(self):
        sem_cambio = [olx.normalizar(i) for i in self.itens if olx.normalizar(i).cambio is None]
        self.assertEqual(len(sem_cambio), 1)
        self.assertFalse(sem_cambio[0].incompleto)  # câmbio não é obrigatório

    def test_nada_de_anunciante_no_item_cru(self):
        for item in self.itens:
            cru = json.dumps(olx.normalizar(item).raw, ensure_ascii=False).lower()
            for termo in olx._TERMOS_ANUNCIANTE:
                self.assertNotIn(termo, cru)


class Normalizacao(unittest.TestCase):
    def test_preco_de_texto_vira_numero(self):
        self.assertEqual(olx._numero("R$ 107.900"), 107900)
        self.assertEqual(olx._numero("R$ 1.234,56"), 1234)
        self.assertEqual(olx._numero("118000"), 118000)
        self.assertIsNone(olx._numero(None))
        self.assertIsNone(olx._numero("Preço a combinar"))

    def test_incompleto_nao_e_descartado(self):
        sem_preco = olx.normalizar(anuncio_cru(1, priceValue=None))
        self.assertTrue(sem_preco.incompleto)
        self.assertEqual(sem_preco.campos_faltando, ["preco"])
        props = [p for p in anuncio_cru(2)["properties"] if p["name"] not in ("regdate", "vehicle_model")]
        sem_ano_e_modelo = olx.normalizar(anuncio_cru(2, properties=props))
        self.assertEqual(sem_ano_e_modelo.campos_faltando, ["ano", "modelo"])

    def test_remove_nome_e_telefone_de_anunciante_em_qualquer_nivel(self):
        cru = anuncio_cru(
            3,
            transactionalSellerName="Fulano Autos",
            seller={"phone": "31999990000", "storeName": "Loja"},
            properties=anuncio_cru(3)["properties"] + [{"name": "phone", "value": "31988887777"}],
        )
        saida = json.dumps(olx.normalizar(cru).raw).lower()
        for proibido in ("fulano", "31999990000", "31988887777", "transactionalsellername"):
            self.assertNotIn(proibido, saida)

    def test_nota_do_anunciante_so_de_profissional(self):
        prof = olx.normalizar(anuncio_cru(10, professionalAd=True, userGoogleRating=4.6))
        self.assertEqual(prof.nota_anunciante, 4.6)
        self.assertEqual(prof.raw["userGoogleRating"], 4.6)
        inteira = olx.normalizar(anuncio_cru(11, professionalAd=True, userGoogleRating=5))
        self.assertEqual(inteira.nota_anunciante, 5.0)
        self.assertIsInstance(inteira.nota_anunciante, float)

        particular = olx.normalizar(anuncio_cru(12, professionalAd=False, userGoogleRating=4.9))
        self.assertIsNone(particular.nota_anunciante)
        self.assertNotIn("userGoogleRating", particular.raw)  # descartada também do item cru

        sem_tipo = olx.normalizar(anuncio_cru(13, professionalAd=None, userGoogleRating=4.9))
        self.assertIsNone(sem_tipo.nota_anunciante)
        self.assertNotIn("userGoogleRating", sem_tipo.raw)

    def test_nota_invalida_ou_ausente_vira_none(self):
        for valor in (None, "4.5", True, 7, -1):
            a = olx.normalizar(anuncio_cru(20, professionalAd=True, userGoogleRating=valor))
            self.assertIsNone(a.nota_anunciante, valor)
        sem_campo = olx.normalizar(anuncio_cru(21, professionalAd=True))
        self.assertIsNone(sem_campo.nota_anunciante)

    def test_montar_url_com_filtros(self):
        busca = Busca(texto="civic 2018", estado="mg", preco_max=90000, ano_min=2018, km_max=60000)
        url = olx.montar_url(
            busca, 2, cambio="automático", combustivel="flex", anunciante="particular", ordenar="recentes",
        )
        for pedaco in ("estado-mg", "q=civic%202018", "o=2", "pe=90000", "rs=2018", "gb=2",
                       "fu=3", "me=60000", "f=0", "sf=1"):
            self.assertIn(pedaco, url)
        with self.assertRaises(ValueError):
            Busca(texto="civic", estado="minas")


class CanarioDoPayload(unittest.TestCase):
    """Se estes falham, a OLX mudou o payload (ou bloqueou) e o extrator precisa de ajuste."""

    def test_sem_array_ads_da_erro_claro(self):
        html = "<html><body><script>self.__next_f.push([1,\"nada aqui\"])</script></body></html>"
        with self.assertRaises(olx.PayloadSemAdsError) as ctx:
            olx.extrair_pagina(html)
        self.assertIn("OLX mudou o payload", str(ctx.exception))

    def test_ads_vazio_devolve_lista_vazia(self):
        itens, total = olx.extrair_pagina(html_com_ads([], 0))
        self.assertEqual((itens, total), ([], 0))

    @unittest.skipUnless(os.environ.get("OLX_LIVE") == "1", "ao vivo: rode com OLX_LIVE=1")
    def test_ao_vivo_a_olx_ainda_entrega_anuncios(self):
        paginas = list(olx.buscar_paginas(Busca(texto="civic", estado="mg"), LimitesBusca(max_paginas=1)))
        achados = sum(len(p.anuncios) for p in paginas)
        self.assertGreater(
            achados,
            0,
            "A busca ao vivo não trouxe nenhum anúncio. A OLX mudou o payload (self.__next_f) "
            f"ou bloqueou. Aviso: {[p.aviso for p in paginas]}",
        )


class ComportamentoDaBusca(unittest.TestCase):
    def test_para_no_total_ads_e_tira_repetidos(self):
        p1 = html_com_ads([anuncio_cru(1), anuncio_cru(2)], total=3)
        p2 = html_com_ads([anuncio_cru(2), anuncio_cru(3)], total=3)  # o 2 repete
        paginas, sessao, relogio = rodar([RespostaFalsa(200, p1), RespostaFalsa(200, p2)])
        self.assertEqual([p.numero for p in paginas], [1, 2])
        self.assertEqual([a.external_id for p in paginas for a in p.anuncios], ["1", "2", "3"])
        self.assertEqual(paginas[-1].parou_por, olx.TOTAL_ADS)
        self.assertIsNone(paginas[0].parou_por)
        self.assertEqual(len(relogio.esperas), 1)  # uma pausa entre as duas páginas
        self.assertIn("o=2", sessao.urls[1])

    def test_para_no_max_paginas(self):
        resp = [RespostaFalsa(200, html_com_ads([anuncio_cru(i)], total=99)) for i in (1, 2, 3)]
        paginas, sessao, _ = rodar(resp, max_paginas=2)
        self.assertEqual(len(paginas), 2)
        self.assertEqual(paginas[-1].parou_por, olx.MAX_PAGINAS)
        self.assertEqual(len(sessao.urls), 2)

    def test_para_em_pagina_vazia(self):
        p1 = html_com_ads([anuncio_cru(1)], total=99)
        paginas, _, _ = rodar([RespostaFalsa(200, p1), RespostaFalsa(200, html_com_ads([], 99))])
        self.assertEqual(paginas[-1].parou_por, olx.PAGINA_VAZIA)
        self.assertEqual(paginas[-1].acumulado, 1)

    def test_pausa_fica_dentro_do_intervalo(self):
        resp = [RespostaFalsa(200, html_com_ads([anuncio_cru(i)], total=99)) for i in (1, 2, 3)]
        _, _, relogio = rodar(resp, max_paginas=3, pausa_entre_paginas_segundos=(6.0, 14.0))
        self.assertEqual(len(relogio.esperas), 2)
        self.assertTrue(all(6.0 <= e <= 14.0 for e in relogio.esperas))

    def test_bloqueio_tenta_so_duas_vezes_e_devolve_o_que_juntou(self):
        p1 = html_com_ads([anuncio_cru(1), anuncio_cru(2)], total=99)
        bloqueios = [RespostaFalsa(403), RespostaFalsa(403), RespostaFalsa(403), RespostaFalsa(200, p1)]
        paginas, sessao, relogio = rodar([RespostaFalsa(200, p1)] + bloqueios)
        self.assertEqual(paginas[0].acumulado, 2)
        ultima = paginas[-1]
        self.assertEqual(ultima.parou_por, olx.BLOQUEIO)
        self.assertEqual(ultima.acumulado, 2)  # não perdeu o que já tinha
        self.assertIn("bloqueio", ultima.aviso.lower())
        self.assertEqual(len(sessao.urls), 1 + 3)  # página 1 + (1 tentativa + 2 repetições)
        esperas_backoff = relogio.esperas[1:]  # a primeira é a pausa normal entre páginas
        self.assertEqual(len(esperas_backoff), 2)
        self.assertLess(esperas_backoff[0], esperas_backoff[1])  # backoff crescente
        self.assertEqual(len(sessao.respostas), 1)  # a resposta boa que sobrou nunca foi pedida

    def test_pagina_sem_ads_conta_como_bloqueio(self):
        sem_ads = RespostaFalsa(200, "<html><body>captcha</body></html>")
        paginas, sessao, _ = rodar([sem_ads, sem_ads, sem_ads])
        self.assertEqual(paginas[0].parou_por, olx.BLOQUEIO)
        self.assertEqual(paginas[0].anuncios, [])
        self.assertEqual(len(sessao.urls), 3)

    def test_recupera_se_o_bloqueio_passar(self):
        p1 = html_com_ads([anuncio_cru(1)], total=1)
        paginas, _, _ = rodar([RespostaFalsa(429), RespostaFalsa(200, p1)])
        self.assertEqual(paginas[0].acumulado, 1)
        self.assertEqual(paginas[0].parou_por, olx.TOTAL_ADS)

    def test_respeita_o_tempo_maximo(self):
        resp = [RespostaFalsa(200, html_com_ads([anuncio_cru(i)], total=99)) for i in (1, 2, 3, 4)]
        paginas, sessao, _ = rodar(resp, max_paginas=4, pausa_entre_paginas_segundos=(10.0, 10.0), tempo_max_segundos=15.0)
        self.assertEqual(paginas[-1].parou_por, olx.TEMPO_MAXIMO)
        self.assertEqual(len(sessao.urls), 2)

    def test_buscar_tudo_junta_as_paginas(self):
        sessao, relogio = SessaoFalsa([
            RespostaFalsa(200, html_com_ads([anuncio_cru(1), anuncio_cru(2, priceValue=None)], total=2))
        ]), Relogio()
        resultado = olx.buscar_tudo(Busca(texto="civic", estado="mg"), sessao=sessao, dormir=relogio.dormir, relogio=relogio)
        self.assertEqual((len(resultado.anuncios), resultado.paginas_lidas, resultado.incompletos), (2, 1, 1))
        self.assertEqual(resultado.motivo_parada, "acabaram_paginas")


if __name__ == "__main__":
    unittest.main()
