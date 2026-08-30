import os
import tempfile

_tmpdir = tempfile.mkdtemp(prefix="found_comics_test_")
os.environ["FOUND_COMICS_DB"] = f"sqlite:///{_tmpdir}/test.db".replace("\\", "/")

import io
import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database import Base, engine

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def test_index_serves_html():
    res = client.get("/")
    assert res.status_code == 200
    assert "Found Comics" in res.text


def test_create_list_update_delete_series():
    payload = {"title": "Amazing Spider-Man", "volume": 2022, "last_number": 61}
    res = client.post("/api/series", json=payload)
    assert res.status_code == 201
    created = res.json()
    assert created["next_number"] == 62

    res = client.get("/api/series")
    assert res.status_code == 200
    assert len(res.json()) == 1
    assert res.json()[0]["last_check"] is None

    res = client.put(f"/api/series/{created['id']}", json={**payload, "last_number": 62})
    assert res.status_code == 200
    assert res.json()["last_number"] == 62
    assert res.json()["next_number"] == 63

    res = client.delete(f"/api/series/{created['id']}")
    assert res.status_code == 204
    assert client.get("/api/series").json() == []


def test_missing_series_404():
    assert client.get("/api/series/999").status_code == 404


CSV_CONTENT = "titulo,volumen,editorial,ultimo numero\nAmazing Spider-Man,2022,Panini,61\nDaredevil,2022,Panini,40\n"


def test_import_preview_and_confirm():
    files = {"file": ("coleccion.csv", io.BytesIO(CSV_CONTENT.encode("utf-8")), "text/csv")}
    res = client.post("/api/import/preview", files=files)
    assert res.status_code == 200
    body = res.json()
    assert body["columns"] == ["titulo", "volumen", "editorial", "ultimo numero"]
    assert body["suggested_mapping"]["titulo"] == "title"
    assert body["suggested_mapping"]["ultimo numero"] == "last_number"
    assert len(body["rows"]) == 2

    mapping = {"titulo": "title", "volumen": "volume",
               "editorial": "publisher", "ultimo numero": "last_number"}
    files = {"file": ("coleccion.csv", io.BytesIO(CSV_CONTENT.encode("utf-8")), "text/csv")}
    res = client.post(
        "/api/import/confirm-file",
        files=files,
        data={"mapping": json.dumps(mapping)},
    )
    assert res.status_code == 200
    assert res.json()["created"] == 2
    assert res.json()["skipped"] == []

    series_list = client.get("/api/series").json()
    titles = {s["title"] for s in series_list}
    assert titles == {"Amazing Spider-Man", "Daredevil"}


def test_check_series_error_recorded(monkeypatch):
    from app.services import amazon

    series = client.post(
        "/api/series", json={"title": "Serie X", "last_number": 5}
    ).json()

    async def fake_search(query, client=None, max_retries=0):
        raise amazon.AmazonBlockedError("HTTP 503")

    monkeypatch.setattr(amazon, "search", fake_search)

    res = client.post(f"/api/checks/{series['id']}")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "error"
    assert body["number_searched"] == 6

    checks = client.get(f"/api/series/{series['id']}/checks").json()
    assert len(checks) == 1


def test_check_all_bulk_records_results(monkeypatch):
    """Regresión: 'Comprobar todas' corre en el event loop; el checker no
    debe usar asyncio.run (antes marcaba todo como 'error')."""
    from app.services import amazon, checker

    monkeypatch.setattr(checker, "BULK_DELAY_SECONDS", 0)

    s1 = client.post("/api/series", json={"title": "Serie A", "last_number": 1}).json()
    s2 = client.post("/api/series", json={"title": "Serie B", "last_number": 9}).json()

    async def fake_search(query, client=None, max_retries=0):
        # Devuelve un resultado que encaja con el siguiente número de cada serie.
        number = query.strip().split()[-1]
        return [
            amazon.AmazonSearchResult(
                title=f"{query.rsplit(' ', 1)[0]} {number}",
                url=f"https://www.amazon.es/dp/{number}",
                price=9.99,
            )
        ]

    monkeypatch.setattr(amazon, "search", fake_search)

    # TestClient ejecuta las tareas en segundo plano antes de devolver la respuesta.
    res = client.post("/api/checks/all")
    assert res.status_code == 200

    for s in (s1, s2):
        checks = client.get(f"/api/series/{s['id']}/checks").json()
        assert len(checks) == 1
        assert checks[0]["status"] == "posible", checks[0]
        assert checks[0]["status"] != "error"


def test_update_check_status(monkeypatch):
    from app.services import amazon

    series = client.post(
        "/api/series", json={"title": "Serie Y", "last_number": 3}
    ).json()

    async def fake_search(query, client=None, max_retries=0):
        return [amazon.AmazonSearchResult("Serie Y 4", "https://amazon.es/dp/y", 5.0)]

    monkeypatch.setattr(amazon, "search", fake_search)
    check = client.post(f"/api/checks/{series['id']}").json()
    assert check["status"] == "posible"

    # Confirmar como disponible.
    res = client.patch(f"/api/checks/{check['id']}", json={"status": "disponible"})
    assert res.status_code == 200
    assert res.json()["status"] == "disponible"

    # El listado refleja el nuevo estado en last_check.
    listed = client.get("/api/series").json()[0]
    assert listed["last_check"]["status"] == "disponible"

    # Estado inválido -> 422 (Literal de pydantic).
    assert client.patch(
        f"/api/checks/{check['id']}", json={"status": "cualquiera"}
    ).status_code == 422

    # Comprobación inexistente -> 404.
    assert client.patch(
        "/api/checks/99999", json={"status": "disponible"}
    ).status_code == 404