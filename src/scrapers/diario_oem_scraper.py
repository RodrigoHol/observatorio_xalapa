# src/scrapers/diario_oem_scraper.py
import re
import asyncio
import httpx
from selectolax.lexbor import LexborHTMLParser as HTMLParser
from src.scrapers.base_scraper import BasePortalScraper
from src.database import guardar_publicaciones_batch

class DiarioXalapaScraper(BasePortalScraper):
    def __init__(self):
        super().__init__(id_fuente=1, max_concurrency=10)
        self.sitemap_index = "https://oem.com.mx/diariodexalapa/sitemap.xml"

    async def extraer_nota(self, client: httpx.AsyncClient, url: str, fecha_sitemap: str) -> dict | None:
        html = await self.fetch(client, url)
        if not html:
            return None

        tree = HTMLParser(html)
        titulo_node = tree.css_first("h1")
        titulo = titulo_node.text(strip=True) if titulo_node else ""

        # Extraer todos los párrafos del cuerpo de la nota
        parrafos = [p.text(strip=True) for p in tree.css("article p, .article-body p, .content-body p") if len(p.text(strip=True)) > 25]
        contenido = " ".join(parrafos)

        if not contenido or not self.es_nota_de_xalapa(titulo, contenido):
            return None

        # Detectar fecha exacta en meta tags si está disponible
        meta_fecha = tree.css_first('meta[property="article:published_time"], meta[name="publish-date"]')
        fecha_pub = meta_fecha.attributes.get("content", fecha_sitemap)[:19].replace("T", " ") if meta_fecha else fecha_sitemap

        seccion = "policiaca" if "/policiaca/" in url else "local"
        return {
            "id_fuente": self.id_fuente,
            "id_externo": url.split("-")[-1].replace("/", ""),
            "url": url,
            "fecha_publicacion": fecha_pub,
            "titulo": titulo,
            "contenido_texto": contenido,
            "seccion_origen": seccion,
            "es_xalapa": 1
        }

    async def ejecutar(self):
        total_guardadas = 0
        async with httpx.AsyncClient(headers=self.headers) as client:
            xml_principal = await self.fetch(client, self.sitemap_index)
            if not xml_principal:
                print("[Diario de Xalapa] No se pudo obtener el sitemap principal.")
                return 0

            # Buscar sub-sitemaps o URLs directas correspondientes a 2025 y 2026
            sub_sitemaps = re.findall(r"<loc>(https://oem\.com\.mx/diariodexalapa/[^<]+\.xml)</loc>", xml_principal)
            if not sub_sitemaps:
                sub_sitemaps = [self.sitemap_index]

            for sm_url in sub_sitemaps:
                # Si el nombre del sitemap tiene año y no es 2025 o 2026, lo saltamos
                if re.search(r"201\d|202[0-4]", sm_url):
                    continue

                sm_xml = await self.fetch(client, sm_url)
                if not sm_xml:
                    continue

                # Extraer pares (URL, lastmod) de secciones locales o policiacas
                bloques_url = re.findall(r"<url>(.*?)</url>", sm_xml, re.DOTALL)
                candidatos = []
                for bloque in bloques_url:
                    loc_m = re.search(r"<loc>(https://oem\.com\.mx/diariodexalapa/(?:local|policiaca)/[^<]+)</loc>", bloque)
                    mod_m = re.search(r"<lastmod>(202[56]-[^<]+)</lastmod>", bloque)
                    if loc_m and mod_m:
                        candidatos.append((loc_m.group(1), mod_m.group(1)[:19].replace("T", " ")))

                # Procesar en lotes de 50 para mantener la RAM baja
                for i in range(0, len(candidatos), 50):
                    sublote = candidatos[i:i+50]
                    tareas = [self.extraer_nota(client, u, f) for u, f in sublote]
                    resultados = await asyncio.gather(*tareas)
                    registros_validos = [r for r in resultados if r is not None]
                    insertadas = guardar_publicaciones_batch(registros_validos)
                    total_guardadas += insertadas
                    print(f"[Diario de Xalapa] Lote procesado | Nuevas: {insertadas} | Total: {total_guardadas}")

        return total_guardadas