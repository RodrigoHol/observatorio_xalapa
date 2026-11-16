# src/database.py
import sqlite3
from pathlib import Path
from typing import List, Dict, Any

DB_PATH = Path("data/observatorio_xalapa.db")

FUENTES_INICIALES = [
    # Portales Web (Banco de datos sin sesgo)
    (1, "Diario de Xalapa (OEM)", "portal_web", "https://oem.com.mx/diariodexalapa/"),
    (2, "Al Calor Político (Portal)", "portal_web", "https://www.alcalorpolitico.com/edicion/inicio.html"),
    (3, "El Heraldo de Xalapa", "portal_web", "https://heraldodexalapa.com.mx/"),
    (4, "AVC Noticias (Portal)", "portal_web", "https://www.avcnoticias.com.mx/"),
    # Páginas de Facebook
    (5, "Página FB ID 100064946853452", "fb_pagina", "https://www.facebook.com/profile.php?id=100064946853452"),
    (6, "Xalapa Noticias Digitales (FB)", "fb_pagina", "https://www.facebook.com/xalapanoticiasdigitales"),
    (7, "AVC Noticias (FB)", "fb_pagina", "https://www.facebook.com/avcnoticias.com.mx"),
    # Grupos de Facebook
    (8, "Grupo FB 266246240411326", "fb_grupo", "https://www.facebook.com/groups/266246240411326"),
    (9, "Grupo Al Calor Político (FB)", "fb_grupo", "https://www.facebook.com/groups/alcalorpolitico"),
]

def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    # Optimización para escrituras rápidas y concurrentes en disco
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn

def init_db() -> None:
    with get_connection() as conn:
        cursor = conn.cursor()

        # 1. Tabla de Fuentes (Para separar exactamente de dónde sale cada dato)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS fuentes (
                id_fuente INTEGER PRIMARY KEY,
                nombre TEXT NOT NULL,
                tipo_origen TEXT NOT NULL CHECK(tipo_origen IN ('portal_web', 'fb_pagina', 'fb_grupo')),
                url_base TEXT NOT NULL UNIQUE
            );
        """)

        # 2. Tabla de Publicaciones (Notas periodísticas y Posts de Facebook)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS publicaciones (
                id_publicacion INTEGER PRIMARY KEY AUTOINCREMENT,
                id_fuente INTEGER NOT NULL,
                id_externo TEXT,
                url TEXT NOT NULL UNIQUE,
                fecha_publicacion TEXT NOT NULL, -- Formato ISO YYYY-MM-DD HH:MM:SS
                titulo TEXT,
                contenido_texto TEXT NOT NULL,
                seccion_origen TEXT,
                es_xalapa INTEGER DEFAULT 1,
                num_reacciones INTEGER DEFAULT 0,
                num_comentarios INTEGER DEFAULT 0,
                -- Campos que llenará la RTX 3050 en la Fase 3 (BERTopic / LLM)
                tema_principal_ia TEXT,
                subtema_ia TEXT,
                colonia_detectada TEXT,
                procesado_ia INTEGER DEFAULT 0,
                fecha_recoleccion TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (id_fuente) REFERENCES fuentes(id_fuente)
            );
        """)

        # 3. Tabla de Comentarios (Con campos demográficos para Género y Edad)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS comentarios (
                id_comentario INTEGER PRIMARY KEY AUTOINCREMENT,
                id_publicacion INTEGER NOT NULL,
                id_fuente INTEGER NOT NULL,
                id_comentario_externo TEXT UNIQUE,
                fecha_comentario TEXT,
                nombre_autor TEXT,
                autor_hash TEXT,
                avatar_url TEXT,
                texto_comentario TEXT NOT NULL,
                likes INTEGER DEFAULT 0,
                -- Campos demográficos y de opinión (Fase 3 en GPU)
                genero_inferido TEXT CHECK(genero_inferido IN ('M', 'F', 'Indeterminado', NULL)),
                rango_edad_estimado TEXT CHECK(rango_edad_estimado IN ('18-29', '30-49', '50+', 'No identificable', NULL)),
                metodo_inferencia_demografica TEXT, -- 'nombre', 'nombre+avatar', 'texto_llm'
                tema_comentario_ia TEXT,
                sentimiento TEXT CHECK(sentimiento IN ('Negativo/Queja', 'Neutral', 'Positivo/Propuesta', NULL)),
                procesado_ia INTEGER DEFAULT 0,
                FOREIGN KEY (id_publicacion) REFERENCES publicaciones(id_publicacion),
                FOREIGN KEY (id_fuente) REFERENCES fuentes(id_fuente)
            );
        """)

        # Índices para acelerar consultas por fecha, fuente y estado de procesamiento
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_pub_fuente_fecha ON publicaciones(id_fuente, fecha_publicacion);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_com_fuente ON comentarios(id_fuente);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_com_demografia ON comentarios(genero_inferido, rango_edad_estimado);")

        cursor.executemany(
            "INSERT OR IGNORE INTO fuentes (id_fuente, nombre, tipo_origen, url_base) VALUES (?, ?, ?, ?);",
            FUENTES_INICIALES
        )
        conn.commit()

def guardar_publicaciones_batch(registros: List[Dict[str, Any]]) -> int:
    """Inserta un lote de notas/publicaciones ignorando URLs duplicadas."""
    if not registros:
        return 0
    query = """
        INSERT OR IGNORE INTO publicaciones 
        (id_fuente, id_externo, url, fecha_publicacion, titulo, contenido_texto, seccion_origen, es_xalapa)
        VALUES (:id_fuente, :id_externo, :url, :fecha_publicacion, :titulo, :contenido_texto, :seccion_origen, :es_xalapa);
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.executemany(query, registros)
        conn.commit()
        return cursor.rowcount
import hashlib

def guardar_post_y_comentarios_fb(post_data: Dict[str, Any], comentarios_lista: List[Dict[str, Any]]) -> tuple[int, int]:
    """Guarda un post de Facebook y su lista de comentarios vinculada."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO publicaciones 
            (id_fuente, id_externo, url, fecha_publicacion, titulo, contenido_texto, seccion_origen, es_xalapa, num_reacciones, num_comentarios)
            VALUES (:id_fuente, :id_externo, :url, :fecha_publicacion, :titulo, :contenido_texto, :seccion_origen, 1, :num_reacciones, :num_comentarios);
        """, post_data)

        # Obtener el id_publicacion (ya sea recién insertado o existente)
        row = cursor.execute("SELECT id_publicacion FROM publicaciones WHERE url = ?;", (post_data["url"],)).fetchone()
        if not row:
            conn.commit()
            return 0, 0
        id_pub = row["id_publicacion"]

        com_insertados = 0
        for c in comentarios_lista:
            autor = (c.get("nombre_autor") or "").strip()
            texto = (c.get("texto_comentario") or "").strip()
            if not texto:
                continue
            autor_hash = hashlib.sha256(autor.encode("utf-8")).hexdigest()[:16] if autor else "anonimo"
            id_ext_com = c.get("id_comentario_externo") or hashlib.md5(f"{id_pub}_{autor}_{texto[:40]}".encode("utf-8")).hexdigest()

            cursor.execute("""
                INSERT OR IGNORE INTO comentarios
                (id_publicacion, id_fuente, id_comentario_externo, fecha_comentario, nombre_autor, autor_hash, avatar_url, texto_comentario, likes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                id_pub,
                post_data["id_fuente"],
                id_ext_com,
                c.get("fecha_comentario", post_data["fecha_publicacion"]),
                autor,
                autor_hash,
                c.get("avatar_url", ""),
                texto,
                c.get("likes", 0)
            ))
            com_insertados += cursor.rowcount

        conn.commit()
        return 1, com_insertados
