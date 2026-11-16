# ampliar_facebook.py
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.database import init_db, get_connection
import fase2_apify as fb

# =========================================================================
# CONFIGURACIÓN DE AMPLIACIÓN MASIVA
# =========================================================================

# Aumentamos límites para aprovechar los ~$6 USD disponibles
fb.POSTS_POR_PAGINA = 250
fb.POSTS_POR_GRUPO = 250
fb.TOP_POSTS_PARA_COMENTARIOS = 45
fb.MAX_COMENTARIOS_POR_POST = 60

# Fuentes donde queremos inyectar más volumen (priorizando [7] AVC que está en 0, y los grupos [8] y [9])
FUENTES_A_AMPLIAR = [
    {"id_fuente": 7, "tipo": "pagina", "nombre": "AVC Noticias FB", "url": "https://www.facebook.com/avcnoticias.com.mx"},
    {"id_fuente": 8, "tipo": "grupo",  "nombre": "Grupo FB 266246240411326", "url": "https://www.facebook.com/groups/266246240411326"},
    {"id_fuente": 9, "tipo": "grupo",  "nombre": "Grupo Al Calor Político", "url": "https://www.facebook.com/groups/alcalorpolitico"},
    {"id_fuente": 6, "tipo": "pagina", "nombre": "Xalapa Noticias Digitales", "url": "https://www.facebook.com/xalapanoticiasdigitales"},
]


def main():
    init_db()
    gestor = fb.GestorApify(fb.APIFY_TOKENS)

    if not gestor.tokens:
        print("[!] Configura APIFY_TOKENS en el archivo .env (consulta .env.example).")
        return

    for fuente in FUENTES_A_AMPLIAR:
        id_f = fuente["id_fuente"]
        print(f"\n=======================================================")
        print(f" AMPLIANDO FUENTE [{id_f}]: {fuente['nombre']}")
        print(f"=======================================================")

        backup_posts = fb.BACKUP_DIR / f"fuente_{id_f}_posts_amp.json"
        backup_coms = fb.BACKUP_DIR / f"fuente_{id_f}_comentarios_amp.json"

        # 1. Descargar lote ampliado de posts
        if backup_posts.exists():
            items_posts = json.loads(backup_posts.read_text(encoding="utf-8"))
        else:
            if fuente["tipo"] == "pagina":
                print(f"   [Apify Cloud] Extrayendo hasta {fb.POSTS_POR_PAGINA} posts de {fuente['nombre']}...")
                items_posts = gestor.ejecutar_actor("apify/facebook-posts-scraper", {
                    "startUrls": [{"url": fuente["url"]}],
                    "resultsLimit": fb.POSTS_POR_PAGINA,
                    "onlyPostsNewerThan": "2025-01-01",
                })
            else:
                print(f"   [Apify Cloud] Extrayendo hasta {fb.POSTS_POR_GRUPO} posts del grupo {fuente['nombre']}...")
                items_posts = gestor.ejecutar_actor("apify/facebook-groups-scraper", {
                    "startUrls": [{"url": fuente["url"]}],
                    "resultsLimit": fb.POSTS_POR_GRUPO,
                    "viewOption": "TOP_POSTS",  # Priorizar los posts con más comentarios del grupo
                    "onlyPostsNewerThan": "2025-01-01",
                })

            if not items_posts:
                print(f"   [Aviso] No se devolvieron posts para {fuente['nombre']}.")
                continue
            backup_posts.write_text(json.dumps(items_posts, ensure_ascii=False, indent=2), encoding="utf-8")

        origen_tag = "apify_fb_page_amp" if fuente["tipo"] == "pagina" else "apify_fb_group_amp"
        top_posts = fb.procesar_y_guardar_posts(items_posts, id_f, origen_tag)
        print(f"   [SQLite] {len(items_posts)} posts revisados | {len(top_posts)} con alta interacción listos para comentarios.")

        # 2. Descargar lote ampliado de comentarios
        if top_posts:
            # Redirigir temporalmente el archivo de backup para no chocar con el lote 1
            urls_input = [{"url": p["url"]} for p in top_posts]
            print(f"   [Apify Cloud] Descargando hasta {len(urls_input) * fb.MAX_COMENTARIOS_POR_POST} comentarios en {fuente['nombre']}...")
            comentarios_raw = gestor.ejecutar_actor("apify/facebook-comments-scraper", {
                "startUrls": urls_input,
                "resultsLimit": len(urls_input) * fb.MAX_COMENTARIOS_POR_POST,
                "includeNestedComments": False,
                "viewOption": "RANKED_UNFILTERED",
            })
            if comentarios_raw:
                backup_coms.write_text(json.dumps(comentarios_raw, ensure_ascii=False, indent=2), encoding="utf-8")
                # Reutilizar la lógica de emparejamiento guardando el archivo como el esperado
                (fb.BACKUP_DIR / f"fuente_{id_f}_comentarios.json").write_text(
                    json.dumps(comentarios_raw, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                fb.extraer_comentarios_lote(gestor, fuente, top_posts)

    with get_connection() as conn:
        print("\n=====================================================================")
        print(" RESUMEN ACTUALIZADO FASE 2 - FACEBOOK EN SQLITE")
        print("=====================================================================")
        filas = conn.execute("""
            SELECT f.id_fuente, f.nombre,
                   (SELECT COUNT(*) FROM publicaciones p WHERE p.id_fuente = f.id_fuente) as posts,
                   (SELECT COUNT(*) FROM comentarios c WHERE c.id_fuente = f.id_fuente) as coms,
                   (SELECT COUNT(*) FROM comentarios c WHERE c.id_fuente = f.id_fuente AND c.avatar_url != '') as con_avatar
            FROM fuentes f
            WHERE f.tipo_origen IN ('fb_pagina', 'fb_grupo')
            ORDER BY f.id_fuente;
        """).fetchall()
        suma_p, suma_c = 0, 0
        for r in filas:
            suma_p += r["posts"]
            suma_c += r["coms"]
            print(f" [{r['id_fuente']}] {r['nombre']:<30} | Posts: {r['posts']:>5} | Comentarios: {r['coms']:>6} | Con Avatar: {r['con_avatar']:>6}")
        print("---------------------------------------------------------------------")
        print(f" TOTAL FACEBOOK -> Posts: {suma_p} | Comentarios Ciudadanos: {suma_c}")
        print("=====================================================================\n")


if __name__ == "__main__":
    main()