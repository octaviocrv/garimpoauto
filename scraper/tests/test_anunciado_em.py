"""anunciado_em: a data única do anúncio (renovação, senão publicação). Offline."""

import sys
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from sources import olx  # noqa: E402
from tests.test_olx import anuncio_cru  # noqa: E402
from tests.test_server import FonteFalsa, cliente  # noqa: E402

DATA = 1791572438
ISO = datetime.fromtimestamp(DATA, timezone.utc).isoformat()


def test_anuncio_nunca_renovado_usa_a_publicacao():
    a = olx.normalizar(anuncio_cru("1", date=DATA, lastBumpAgeSecs="0"))
    assert a.anunciado_em == a.publicado_em and a.renovado_em is None
    assert a.anunciado_em.isoformat() == ISO


def test_anuncio_renovado_usa_a_renovacao():
    a = olx.normalizar(anuncio_cru("2", date=DATA, lastBumpAgeSecs="3600"))
    assert a.anunciado_em == a.renovado_em and a.publicado_em is None
    assert a.anunciado_em.isoformat() == ISO


def test_se_tem_as_duas_datas_a_renovacao_ganha():
    a = olx.normalizar(anuncio_cru("3", date=DATA, lastBumpAgeSecs="0"))
    a.renovado_em = datetime(2026, 10, 9, tzinfo=timezone.utc)
    assert a.anunciado_em == a.renovado_em


def test_sem_certeza_da_data_fica_vazio():
    a = olx.normalizar(anuncio_cru("4", date=DATA))
    assert a.anunciado_em is None


def test_servidor_devolve_anunciado_em_e_mantem_os_dois_campos():
    c, _ = cliente(FonteFalsa(paginas=1, total=2))
    ads = [
        olx.normalizar(anuncio_cru("10", date=DATA, lastBumpAgeSecs="0")),
        olx.normalizar(anuncio_cru("11", date=DATA, lastBumpAgeSecs="900")),
        olx.normalizar(anuncio_cru("12", date=DATA)),
    ]
    from server import _anuncio_json
    novo, renovado, sem = (_anuncio_json(a) for a in ads)
    assert (novo["publicado_em"], novo["renovado_em"], novo["anunciado_em"]) == (ISO, None, ISO)
    assert (renovado["publicado_em"], renovado["renovado_em"], renovado["anunciado_em"]) == (None, ISO, ISO)
    assert (sem["publicado_em"], sem["renovado_em"], sem["anunciado_em"]) == (None, None, None)
    for rota in ("/buscar", "/buscar/pagina"):
        for a in c.get(rota, params={"texto": "gol"}).json()["anuncios"]:
            assert "anunciado_em" in a and "publicado_em" in a and "renovado_em" in a
