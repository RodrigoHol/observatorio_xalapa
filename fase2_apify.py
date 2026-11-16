# fase2_apify.py
import json
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

from apify_client import ApifyClient
from src.database import init_db, guardar_post_y_comentarios_fb, get_connection

# =========================================================================
# TOKENS DE APIFY (rotan automáticamente si uno se queda sin saldo)
# =========================================================================
APIFY_TOKENS = [
    token.strip()
    for token in os.getenv("APIFY_TOKENS", "").split(",")
    if token.strip()
]

BACKUP_DIR = PROJECT_ROOT / "data" / "apify_backups"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

FUENTES_PAGINAS = [
    {"id_fuente": 5, "nombre": "Página FB 100064946853452", "url": "https://www.facebook.com/profile.php?id=100064946853452"},
    {"id_fuente": 6, "nombre": "Xalapa Noticias Digitales", "url": "https://www.facebook.com/xalapanoticiasdigitales"},
    {"id_fuente": 7, "nombre": "AVC Noticias FB", "url": "https://www.facebook.com/avcnoticias.com.mx"},
]

FUENTES_GRUPOS = [
    {"id_fuente": 8, "nombre": "Grupo FB 266246240411326", "url": "https://www.facebook.com/groups/266246240411326"},
    {"id_fuente": 9, "nombre": "Grupo Al Calor Político", "url": "https://www.facebook.com/groups/alcalorpolitico"},
]

# Calibrado para gastar ~$1.50 USD por fuente completa y cubrir todo con 1-2 cuentas free
POSTS_POR_PAGINA = 75
POSTS_POR_GRUPO = 80
TOP_POSTS_PARA_COMENTARIOS = 18
MAX_COMENTARIOS_POR_POST = 35


class GestorApify:
    """Administra la rotación automática de tokens cuando se agotan los $5 USD."""
    def __init__(self, tokens: list[str]):
        self.tokens = [t.strip() for t in tokens if t.strip() and "PEGA_AQUI" not in t]
        self.idx = 0

    def cliente_actual(self) -> ApifyClient | None:
        if self.idx >= len(self.tokens):
            return None
        return ApifyClient(self.tokens[self.idx])

    def ejecutar_actor(self, actor_id: str, run_input: dict) -> list | None:
        while self.idx < len(self.tokens):
            client = self.cliente_actual()
            try:
                run = client.actor(actor_id).call(run_input=run_input)
                status = getattr(run, "status", None) or (run.get("status") if isinstance(run, dict) else "")
                dataset_id = getattr(run, "default_dataset_id", None) or getattr(run, "defaultDatasetId", None) or (
                    run.get("defaultDatasetId") if isinstance(run, dict) else None
                )
                items = list(client.dataset(dataset_id).iterate_items()) if dataset_id else []

                if status == "ABORTED":
                    print(f"   [Aviso] El Token #{self.idx + 1} se agotó a mitad de corrida ({len(items)} items rescatados). Cambiando al siguiente token...")
                    self.idx += 1
                    if len(items) > 15:
                        return items
                    continue
                return items
            except Exception as e:
                err_str = str(e)
                if "monthly usage" in err_str or "402" in err_str or "403" in err_str:
                    print(f"   [Rotación] Token #{self.idx + 1} sin saldo disponible. Pasando al Token #{self.idx + 2}...")
                    self.idx += 1
                else:
                    print(f"   [Error Actor {actor_id}]: {e}")
                    return None
        print("   [!] Todos los tokens de la lista agotaron sus $5 USD.")
        return None


def normalizar_fecha(raw_date: str | None) -> str:
    if not raw_date:
        return "2025-06-01 12:00:00"
    return str(raw_date)[:19].replace("T", " ")


def extraer_identificador_fb(url: str) -> str:
    if not url:
        return ""
    url_limpia = url.split("?")[0].rstrip("/")
    m_pfbid = re.search(r"(pfbid[A-Za-z0-9]+)", url)
    if m_pfbid:
        return m_pfbid.group(1)
    m_num = re.search(r"/(?:posts|permalink|videos|reel|photos)/(\d+)", url_limpia)
    if m_num:
        return m_num.group(1)
    return url_limpia.split("/")[-1]


def procesar_y_guardar_posts(items: list, id_fuente: int, origen_tag: str) -> list[dict]:
    posts_con_comentarios = []
    for item in items:
        url_post = item.get("url") or item.get("postUrl") or item.get("topLevelUrl") or ""
        texto = (item.get("text") or item.get("message") or "").strip()
        if not url_post or not texto:
            continue

        fecha_iso = normalizar_fecha(item.get("time") or item.get("date") or item.get("createdAt"))
        if not (fecha_iso.startswith("2025") or fecha_iso.startswith("2026")):
            continue

        num_coms = int(item.get("comments") or item.get("commentsCount") or 0)
        num_likes = int(item.get("likes") or item.get("likesCount") or item.get("reactionCount") or 0)
        post_id = str(item.get("postId") or item.get("id") or extraer_identificador_fb(url_post))

        post_data = {
            "id_fuente": id_fuente,
            "id_externo": post_id,
            "url": url_post,
            "fecha_publicacion": fecha_iso,
            "titulo": texto[:120].replace("\n", " "),
            "contenido_texto": texto[:8000],
            "seccion_origen": origen_tag,
            "num_reacciones": num_likes,
            "num_comentarios": num_coms,
        }

        coms_preview = []
        for c in (item.get("topComments") or []):
            if isinstance(c, dict) and c.get("text"):
                coms_preview.append({
                    "id_comentario_externo": str(c.get("id") or ""),
                    "nombre_autor": c.get("profileName") or c.get("authorName") or "",
                    "avatar_url": c.get("profilePicture") or "",
                    "texto_comentario": c.get("text", ""),
                    "fecha_comentario": normalizar_fecha(c.get("date") or fecha_iso),
                    "likes": int(c.get("likesCount") or 0),
                })

        guardar_post_y_comentarios_fb(post_data, coms_preview)

        if num_coms > 0:
            posts_con_comentarios.append({
                "url": url_post,
                "post_id": post_id,
                "fb_key": extraer_identificador_fb(url_post),
                "num_comentarios": num_coms,
                "post_data": post_data
            })

    posts_con_comentarios.sort(key=lambda x: x["num_comentarios"], reverse=True)
    return posts_con_comentarios[:TOP_POSTS_PARA_COMENTARIOS]


def extraer_comentarios_lote(gestor: GestorApify, fuente: dict, posts_objetivo: list[dict]):
    if not posts_objetivo:
        print(f"   [{fuente['nombre']}] Sin posts con comentarios públicos.")
        return

    id_fuente = fuente["id_fuente"]
    backup_coms_file = BACKUP_DIR / f"fuente_{id_fuente}_comentarios.json"

    if backup_coms_file.exists():
        print(f"   [Caché Local] Ya existe {backup_coms_file.name}, cargando sin gastar saldo...")
        comentarios_raw = json.loads(backup_coms_file.read_text(encoding="utf-8"))
    else:
        urls_input = [{"url": p["url"]} for p in posts_objetivo]
        print(f"   [Apify Cloud] Extrayendo comentarios de los {len(urls_input)} posts principales en {fuente['nombre']}...")
        run_input = {
            "startUrls": urls_input,
            "resultsLimit": len(urls_input) * MAX_COMENTARIOS_POR_POST,
            "includeNestedComments": False,
            "viewOption": "RECENT_ACTIVITY",
        }
        comentarios_raw = gestor.ejecutar_actor("apify/facebook-comments-scraper", run_input)
        if not comentarios_raw:
            return
        backup_coms_file.write_text(json.dumps(comentarios_raw, ensure_ascii=False, indent=2), encoding="utf-8")

    mapa_por_url = {p["url"]: p["post_data"] for p in posts_objetivo}
    mapa_por_id = {p["post_id"]: p["url"] for p in posts_objetivo if p.get("post_id")}
    mapa_por_key = {p["fb_key"]: p["url"] for p in posts_objetivo if p.get("fb_key")}
    agrupados: dict[str, list] = {p["url"]: [] for p in posts_objetivo}

    for c in comentarios_raw:
        texto_c = (c.get("text") or "").strip()
        if not texto_c:
            continue
        c_url = c.get("inputUrl") or c.get("facebookUrl") or c.get("postUrl") or ""
        c_post_id = str(c.get("postId") or "")
        c_key = extraer_identificador_fb(c_url)

        target_url = None
        if c_url in agrupados:
            target_url = c_url
        elif c_post_id in mapa_por_id:
            target_url = mapa_por_id[c_post_id]
        elif c_key in mapa_por_key:
            target_url = mapa_por_key[c_key]
        else:
            for u_orig in agrupados:
                if u_orig in c_url or c_url in u_orig:
                    target_url = u_orig
                    break
        if not target_url:
            continue

        likes_str = str(c.get("likesCount") or c.get("likes") or "0")
        agrupados[target_url].append({
            "id_comentario_externo": str(c.get("id") or c.get("commentId") or ""),
            "nombre_autor": c.get("profileName") or c.get("authorName") or "",
            "avatar_url": c.get("profilePicture") or c.get("profileAvatar") or "",
            "texto_comentario": texto_c,
            "fecha_comentario": normalizar_fecha(c.get("date") or c.get("time")),
            "likes": int(likes_str) if likes_str.isdigit() else 0,
        })

    total_coms = 0
    for u, lista_c in agrupados.items():
        if lista_c:
            _, ins_c = guardar_post_y_comentarios_fb(mapa_por_url[u], lista_c)
            total_coms += ins_c
    print(f"   [SQLite] +{total_coms} comentarios nuevos guardados en {fuente['nombre']}.")


def main():
    if not APIFY_TOKENS:
        print("[!] Configura APIFY_TOKENS en el archivo .env (consulta .env.example).")
        return

    init_db()
    gestor = GestorApify(APIFY_TOKENS)

    for fuente in FUENTES_PAGINAS:
        print(f"\n=======================================================")
        print(f" PÁGINA [{fuente['id_fuente']}]: {fuente['nombre']}")
        print(f"=======================================================")
        backup_posts_file = BACKUP_DIR / f"fuente_{fuente['id_fuente']}_posts.json"

        if backup_posts_file.exists():
            print(f"   [Caché Local] Usando {backup_posts_file.name} (0 créditos gastados)...")
            items_posts = json.loads(backup_posts_file.read_text(encoding="utf-8"))
        else:
            items_posts = gestor.ejecutar_actor("apify/facebook-posts-scraper", {
                "startUrls": [{"url": fuente["url"]}],
                "resultsLimit": POSTS_POR_PAGINA,
                "onlyPostsNewerThan": "2025-01-01",
            })
            if not items_posts:
                continue
            backup_posts_file.write_text(json.dumps(items_posts, ensure_ascii=False, indent=2), encoding="utf-8")

        top_posts = procesar_y_guardar_posts(items_posts, fuente["id_fuente"], "apify_fb_page")
        extraer_comentarios_lote(gestor, fuente, top_posts)

    for fuente in FUENTES_GRUPOS:
        print(f"\n=======================================================")
        print(f" GRUPO [{fuente['id_fuente']}]: {fuente['nombre']}")
        print(f"=======================================================")
        backup_group_file = BACKUP_DIR / f"fuente_{fuente['id_fuente']}_posts.json"

        if backup_group_file.exists():
            print(f"   [Caché Local] Usando {backup_group_file.name} (0 créditos gastados)...")
            items_grupo = json.loads(backup_group_file.read_text(encoding="utf-8"))
        else:
            items_grupo = gestor.ejecutar_actor("apify/facebook-groups-scraper", {
                "startUrls": [{"url": fuente["url"]}],
                "resultsLimit": POSTS_POR_GRUPO,
                "viewOption": "CHRONOLOGICAL",
                "onlyPostsNewerThan": "2025-01-01",
            })
            if not items_grupo:
                continue
            backup_group_file.write_text(json.dumps(items_grupo, ensure_ascii=False, indent=2), encoding="utf-8")

        top_posts_g = procesar_y_guardar_posts(items_grupo, fuente["id_fuente"], "apify_fb_group")
        extraer_comentarios_lote(gestor, fuente, top_posts_g)

    with get_connection() as conn:
        print("\n=====================================================================")
        print(" RESUMEN FASE 2 - FACEBOOK EN SQLITE (POSTS, COMENTARIOS Y AVATARES)")
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
        for r in filas:
            print(f" [{r['id_fuente']}] {r['nombre']:<30} | Posts: {r['posts']:>5} | Comentarios: {r['coms']:>6} | Con Avatar: {r['con_avatar']:>6}")
        print("=====================================================================\n")


if __name__ == "__main__":
    main()