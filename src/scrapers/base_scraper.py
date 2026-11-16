# src/scrapers/base_scraper.py
import asyncio
import re
import httpx
from selectolax.lexbor import LexborHTMLParser as HTMLParser

# Marcadores clave para asegurar que la nota pertenece a la problemática de Xalapa
MARCADORES_XALAPA = re.compile(
    r"\b(xalapa|xalapeñ[oa]s|cmas|ayuntamiento de xalapa|centro histórico|"
    r"coatepec|trancas|las trancas|ánimas|las ánimas|bugambilias|emiliano zapata|"
    r"sumidero|higueras|castillo|el castillo|progreso macuiltépetl|21 de marzo|"
    r"revolución|lázaro cárdenas|araucaria|rébsamen|circuitos presidentes|arco sur|"
    r"murillo vidal|américas|clavijero|enríquez|plaza lerdo|uv|universidad veracruzana)\b",
    re.IGNORECASE
)

class BasePortalScraper:
    def __init__(self, id_fuente: int, max_concurrency: int = 8):
        self.id_fuente = id_fuente
        self.semaphore = asyncio.Semaphore(max_concurrency)
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "es-MX,es;q=0.9",
        }

    async def fetch(self, client: httpx.AsyncClient, url: str) -> str | None:
        async with self.semaphore:
            for intento in range(3):
                try:
                    resp = await client.get(url, timeout=20.0, follow_redirects=True)
                    if resp.status_code == 200:
                        return resp.text
                    elif resp.status_code == 429:
                        await asyncio.sleep(3 * (intento + 1))
                except httpx.RequestError:
                    await asyncio.sleep(1.5 * (intento + 1))
            return None

    @staticmethod
    def limpiar_html(raw_html: str) -> str:
        if not raw_html:
            return ""
        tree = HTMLParser(raw_html)
        for tag in tree.css("script, style, iframe, nav, footer, aside"):
            tag.decompose()
        texto = tree.text(separator=" ", strip=True)
        return re.sub(r"\s+", " ", texto).strip()

    @staticmethod
    def es_nota_de_xalapa(titulo: str, contenido: str) -> bool:
        texto_completo = f"{titulo} {contenido[:1200]}"
        return bool(MARCADORES_XALAPA.search(texto_completo))