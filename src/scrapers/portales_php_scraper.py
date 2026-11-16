# src/scrapers/portales_php_scraper.py
import asyncio
import re
from datetime import date, timedelta
from urllib.parse import urljoin
import httpx
from selectolax.lexbor import LexborHTMLParser as HTMLParser
from src.scrapers.base_scraper import BasePortalScraper
from src.database import guardar_publicaciones_batch

def generar_fechas(inicio: date = date(2025, 1, 1), fin: date = date.today()):
    actual = inicio
    while actual <= fin:
        yield actual
        actual += timedelta(days=1)

class AlCalorPoliticoScraper(BasePortalScraper):
    def __init__(self):
        super().__init__(id_fuente=2, max_concurrency=8)
        self.base_url = "https://www.alcalorpolitico.com/informacion/"

    async def procesar_nota(self, client: httpx.AsyncClient, url: str, fecha_str: str) -> dict | None:
        html = await self.fetch(client, url)
        if not html:
            return None
        tree = HTMLParser(html)
        titulo_node = tree.css_first("h1, .titulonota")
        titulo = titulo_node.text(strip=True) if titulo_node else ""

        cuerpo_node = tree.css_first("#texto_nota, .textonota, article")
        contenido = cuerpo_node.text(separator=" ", strip=True) if cuerpo_node else self.limpiar_html(html)

        if not self.es_nota_de_xalapa(titulo, contenido):
            return None

        id_match = re.search(r"-(\d+)\.html", url)
        return {
            "id_fuente": self.id_fuente,
            "id_externo": id_match.group(1) if id_match else url,
            "url": url,
            "fecha_publicacion": fecha_str,
            "titulo": titulo,
            "contenido_texto": contenido,
            "seccion_origen": "archivo_diario",
            "es_xalapa": 1
        }

    async def ejecutar(self):
        total = 0
        async with httpx.AsyncClient(headers=self.headers) as client:
            for d in generar_fechas():
                fecha_iso = d.strftime("%Y-%m-%d")
                # Endpoint de archivo diario de Al Calor Político
                url_archivo = f"https://www.alcalorpolitico.com/informacion/notasarchivo.php?fecha={d.strftime('%d/%m/%Y')}"
                html_dia = await self.fetch(client, url_archivo)
                if not html_dia:
                    continue

                tree = HTMLParser(html_dia)
                enlaces = set()
                for a in tree.css("a[href]"):
                    href = a.attributes.get("href", "")
                    if href.endswith(".html") and ("/noticias/" in href or re.search(r"-\d+\.html$", href)):
                        enlaces.add(urljoin(self.base_url, href))

                if enlaces:
                    tareas = [self.procesar_nota(client, link, fecha_iso) for link in enlaces]
                    res = await asyncio.gather(*tareas)
                    validos = [r for r in res if r is not None]
                    ins = guardar_publicaciones_batch(validos)
                    total += ins
                    print(f"[Al Calor Político] {fecha_iso} | Enlaces: {len(enlaces)} | Guardadas Xalapa: {ins} | Total: {total}")
        return total


class AVCNoticiasScraper(BasePortalScraper):
    def __init__(self):
        super().__init__(id_fuente=4, max_concurrency=8)
        self.base_url = "https://www.avcnoticias.com.mx/"

    async def procesar_nota_id(self, client: httpx.AsyncClient, id_nota: int) -> dict | None:
        url = f"https://www.avcnoticias.com.mx/noticias-veracruz/xalapa/{id_nota}/resumen.php?idnota={id_nota}"
        html = await self.fetch(client, url)
        if not html or "2025" not in html and "2026" not in html:
            return None

        tree = HTMLParser(html)
        titulo_node = tree.css_first("h1, .titulo_nota, title")
        titulo = titulo_node.text(strip=True) if titulo_node else ""
        contenido = self.limpiar_html(html)

        if not self.es_nota_de_xalapa(titulo, contenido):
            return None

        # Extraer fecha (DD/MM/YYYY) dentro de la nota de AVC
        m_fecha = re.search(r"(\d{2})/(\d{2})/(202[56])", contenido)
        if not m_fecha:
            return None
        fecha_iso = f"{m_fecha.group(3)}-{m_fecha.group(2)}-{m_fecha.group(1)}"

        return {
            "id_fuente": self.id_fuente,
            "id_externo": str(id_nota),
            "url": url,
            "fecha_publicacion": fecha_iso,
            "titulo": titulo,
            "contenido_texto": contenido[:8000],
            "seccion_origen": "barrido_id",
            "es_xalapa": 1
        }