# main_fase1.py
import asyncio
from src.database import init_db
from src.scrapers.heraldo_scraper import HeraldoXalapaScraper
from src.scrapers.diario_oem_scraper import DiarioXalapaScraper
from src.scrapers.portales_php_scraper import AlCalorPoliticoScraper

async def main():
    print("1. Inicializando Base de Datos SQLite (Modo WAL)...")
    init_db()
    print("   Base de datos lista en: data/observatorio_xalapa.db\n")

    print("2. Iniciando extracción de El Heraldo de Xalapa (WP API JSON)...")
    heraldo = HeraldoXalapaScraper()
    await heraldo.ejecutar(fecha_inicio="2025-01-01T00:00:00")

    print("\n3. Iniciando extracción de Diario de Xalapa (Sitemaps XML)...")
    diario = DiarioXalapaScraper()
    await diario.ejecutar()

    print("\n4. Iniciando extracción de Al Calor Político (Archivo histórico 2025-2026)...")
    acp = AlCalorPoliticoScraper()
    await acp.ejecutar()

if __name__ == "__main__":
    asyncio.run(main())