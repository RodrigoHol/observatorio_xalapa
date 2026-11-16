# src/scrapers/heraldo_scraper.py
import httpx
from src.scrapers.base_scraper import BasePortalScraper
from src.database import guardar_publicaciones_batch

class HeraldoXalapaScraper(BasePortalScraper):
    def __init__(self):
        super().__init__(id_fuente=3, max_concurrency=4)
        self.api_url = "https://heraldodexalapa.com.mx/wp-json/wp/v2/posts"

    async def ejecutar(self, fecha_inicio: str = "2025-01-01T00:00:00"):
        pagina = 1
        total_guardadas = 0

        async with httpx.AsyncClient(headers=self.headers) as client:
            while True:
                params = {
                    "after": fecha_inicio,
                    "per_page": 100,
                    "page": pagina,
                    "_fields": "id,date,link,title,content,categories"
                }
                try:
                    resp = await client.get(self.api_url, params=params, timeout=25.0)
                    if resp.status_code in (400, 404):  # Fin de paginación en WP
                        break
                    resp.raise_for_status()
                    posts = resp.json()
                    if not posts:
                        break
                except Exception as e:
                    print(f"[Heraldo] Fin o error en página {pagina}: {e}")
                    break

                lote = []
                for post in posts:
                    titulo = self.limpiar_html(post.get("title", {}).get("rendered", ""))
                    contenido = self.limpiar_html(post.get("content", {}).get("rendered", ""))

                    if self.es_nota_de_xalapa(titulo, contenido):
                        lote.append({
                            "id_fuente": self.id_fuente,
                            "id_externo": str(post.get("id")),
                            "url": post.get("link"),
                            "fecha_publicacion": post.get("date", "").replace("T", " "),
                            "titulo": titulo,
                            "contenido_texto": contenido,
                            "seccion_origen": "wp_api",
                            "es_xalapa": 1
                        })

                insertadas = guardar_publicaciones_batch(lote)
                total_guardadas += insertadas
                print(f"[Heraldo] Página {pagina} procesada | Nuevas de Xalapa: {insertadas} | Acumulado: {total_guardadas}")
                pagina += 1

        return total_guardadas