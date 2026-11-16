# fase3_temas_ia.py
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import NMF
from src.database import get_connection

EXPORT_DIR = PROJECT_ROOT / "data" / "dashboard_exports"
EXPORT_DIR.mkdir(parents=True, exist_ok=True)

# Municipios externos que suelen colarse por el menú lateral de los portales estatales
MUNICIPIOS_EXTERNOS = re.compile(
    r"\b(poza rica|boca del r[ií]o|orizaba|coatzacoalcos|minatitl[aá]n|c[oó]rdoba|"
    r"san andr[eé]s tuxtla|papantla|tuxpan|mart[ií]nez de la torre|cosoleacaque|"
    r"acayucan|tierra blanca|p[aá]nuco|tantoyuca|maryjose gamboa)\b",
    re.IGNORECASE
)

MARCADORES_XALAPA_ESTRICTO = re.compile(
    r"\b(xalapa|xalapeñ[oa]s|cmas|ayuntamiento de xalapa|coatepec|banderilla|"
    r"emiliano zapata|las trancas|las [aá]nimas|macuilt[eé]petl|los berros|"
    r"plaza lerdo|enr[ií]quez|l[aá]zaro c[aá]rdenas|circuito presidentes|"
    r"arco sur|r[eé]bsamen|murillo vidal|atenas veracruzana)\b",
    re.IGNORECASE
)

# Basura de maquetación web de los portales que no debe entrar al clustering NMF
BASURA_PORTALES = re.compile(
    r"\b(avc|avc noticias|noticias|relacionadas|contacto|resumen|edici[oó]n|"
    r"informaci[oó]n|derechos reservados|publicidad|s[ií]guenos|compartir|"
    r"facebook|twitter|whatsapp|instagram|suscr[ií]bete|leer m[aá]s)\b",
    re.IGNORECASE
)

TAXONOMIA_PROBLEMAS = {
    "Agua Potable, Fugas y Tandeos (CMAS)": [
        r"\bagua\b", r"\bcmas\b", r"\btandeo\b", r"\btandeos\b", r"\bfuga\b", r"\bfugas\b",
        r"\bdesabasto\b", r"\btuber[ií]a\b", r"\bpipas?\b", r"\bsin agua\b", r"\brecibo de agua\b",
        r"\bpozo\b", r"\bpresa\b", r"\bestiaje\b", r"\bv[aá]lvula\b", r"\bpotable\b"
    ],
    "Basura, Residuos Sólidos y Limpia Pública": [
        r"\bbasura\b", r"\bresiduos?\b", r"\blimpia p[uú]blica\b", r"\brecolecci[oó]n\b",
        r"\brelleno sanitario\b", r"\bbasurero\b", r"\bdesechos?\b", r"\bcami[oó]n de la basura\b",
        r"\bcampana\b", r"\bbolsas de basura\b", r"\bpepena\b", r"\bcontenedor\b", r"\btronconal\b"
    ],
    "Calles, Baches, Obras y Vialidad": [
        r"\bbaches?\b", r"\bcalles?\b", r"\bpavimentaci[oó]n\b", r"\basfalto\b", r"\bconcreto\b",
        r"\bobras?\b", r"\btr[aá]fico\b", r"\bvialidad\b", r"\bsem[aá]foros?\b", r"\bbanquetas?\b",
        r"\bpuente\b", r"\btragatormentas\b", r"\balcantarilla\b", r"\bsocav[oó]n\b", r"\bl[aá]zaro c[aá]rdenas\b",
        r"\bcircuito presidentes\b", r"\barco sur\b", r"\br[eé]bsamen\b", r"\bbloqueo\b", r"\bcierre vial\b",
        r"\baccidente\b", r"\bchoque\b", r"\batropellad[oa]\b", r"\bvolcadura\b", r"\bmotociclista\b"
    ],
    "Delincuencia, Inseguridad y Justicia": [
        r"\bdelincuencia\b", r"\binseguridad\b", r"\brobo\b", r"\brobos\b", r"\basalto\b",
        r"\basaltos\b", r"\bladr[oó]n\b", r"\bpolic[ií]a\b", r"\bssp\b", r"\barmados?\b",
        r"\bhomicidio\b", r"\bviolencia\b", r"\bsecuestro\b", r"\bextorsi[oó]n\b", r"\bdetenido\b",
        r"\bfiscal[ií]a\b", r"\bcristalazo\b", r"\bpatrulla\b", r"\bdisparos\b", r"\bdesaparecid[oa]s?\b",
        r"\bdelito\b", r"\bdenuncia\b", r"\bcateo\b", r"\bvinculado\b"
    ],
    "Transporte Público, Taxis y Movilidad": [
        r"\btransporte p[uú]blico\b", r"\bcamiones\b", r"\bautob[uú]s\b", r"\bcombis?\b",
        r"\btaxis?\b", r"\btaxistas?\b", r"\bpasaje\b", r"\btarifa\b", r"\bchofer\b",
        r"\bparada de cami[oó]n\b", r"\bulises\b", r"\btr[aá]nsito\b", r"\bvial\b", r"\bconcesionarios?\b"
    ],
    "Alumbrado Público y Apagones (CFE)": [
        r"\balumbrado\b", r"\bluminarias?\b", r"\bapag[oó]n\b", r"\bapagones\b", r"\bcfe\b",
        r"\bsin luz\b", r"\benerg[ií]a el[eé]ctrica\b", r"\btransformador\b", r"\bcables?\b",
        r"\bposte de luz\b", r"\boscuras\b"
    ],
    "Inundaciones, Drenaje y Clima (Protección Civil)": [
        r"\binundaci[oó]n\b", r"\binundaciones\b", r"\bdrenaje\b", r"\baguas negras\b",
        r"\blluvias?\b", r"\bprotecci[oó]n civil\b", r"\bdeslave\b", r"\bbarranca\b",
        r"\b[aá]rbol ca[ií]do\b", r"\banegamiento\b", r"\bcolector\b", r"\bfrente fr[ií]o\b", r"\btormenta\b"
    ],
    "Salud Pública, Dengue y Hospitales": [
        r"\bsalud\b", r"\bdengue\b", r"\bhospital\b", r"\bimss\b", r"\bissste\b",
        r"\bmedicamentos?\b", r"\bcl[ií]nica\b", r"\bfumigaci[oó]n\b", r"\bmosquitos?\b",
        r"\bcentro de salud\b", r"\bcae\b", r"\bnach[oó]n\b", r"\bpacientes?\b", r"\bm[eé]dicos?\b"
    ],
    "Economía Local, Empleo, Comercio e Impuestos": [
        r"\bempleo\b", r"\bdesempleo\b", r"\bcomercio\b", r"\bambulantes?\b", r"\btianguis\b",
        r"\bmercado\b", r"\bpredial\b", r"\binflaci[oó]n\b", r"\bprecios?\b", r"\beconom[ií]a\b",
        r"\bnegocios?\b", r"\bempresas?\b", r"\bcanaco\b", r"\bcoparmex\b", r"\bturismo\b"
    ],
    "Medio Ambiente, Áreas Verdes y Maltrato Animal": [
        r"\bmedio ambiente\b", r"\b[aá]rboles\b", r"\btala\b", r"\bparque\b", r"\b[aá]reas verdes\b",
        r"\bperros?\b", r"\bgatos?\b", r"\bmaltrato animal\b", r"\bmascotas?\b", r"\bcallejeros?\b",
        r"\bcontaminaci[oó]n\b", r"\bruido\b", r"\bsantuario\b", r"\bmacuilt[eé]petl\b", r"\blos berros\b"
    ],
    "Educación, Escuelas y Comunidad UV": [
        r"\bescuelas?\b", r"\buniversidad veracruzana\b", r"\buv\b", r"\bestudiantes?\b",
        r"\bmaestros?\b", r"\bsev\b", r"\bclases\b", r"\bplantel\b", r"\bfacultad\b", r"\bbecas?\b"
    ],
    "Gobierno Municipal, Trámites y Protestas": [
        r"\bayuntamiento\b", r"\balcalde\b", r"\balcaldesa\b", r"\bcabildo\b", r"\bmanifestaci[oó]n\b",
        r"\bprotesta\b", r"\btr[aá]mites?\b", r"\bcorrupci[oó]n\b", r"\bservidor p[uú]blico\b"
    ]
}

PATRONES_PROBLEMAS = {
    tema: re.compile("|".join(patrones), re.IGNORECASE)
    for tema, patrones in TAXONOMIA_PROBLEMAS.items()
}

COLONIAS_XALAPA = [
    "Centro", "Revolución", "Las Ánimas", "Las Trancas", "Bugambilias", "El Castillo",
    "Sumidero", "Higueras", "Progreso Macuiltépetl", "21 de Marzo", "Emiliano Zapata",
    "Lázaro Cárdenas", "Murillo Vidal", "Rébsamen", "Arco Sur", "Circuito Presidentes",
    "Araucarias", "Indeco Ánimas", "Jardines de Xalapa", "Fovissste", "Infonavit Pomona",
    "Agua Santa", "Banderilla", "Coatepec", "San Bruno", "Obrero Campesina", "Carolino Anaya",
    "Casa Blanca", "La Haciendita", "Xalapa 2000", "Nuevo Xalapa", "Los Sauces", "Los Berros",
    "Zona UV", "Avenida Xalapa", "Américas", "Clavijero", "Enríquez", "El Mirador", "2 de Abril"
]

PATRON_COLONIAS = re.compile(
    r"\b(" + "|".join(re.escape(c) for c in COLONIAS_XALAPA) + r")\b",
    re.IGNORECASE
)

PALABRAS_QUEJA = re.compile(
    r"\b(urge|p[eé]simo|harto|hartos|harta|basura|inseguridad|robo|asalto|baches|fuga|"
    r"sin agua|no hay agua|corrupci[oó]n|ineptos|verg[uü]enza|peligro|queja|"
    r"denuncia|mal estado|abandono|nunca hacen|no sirven|problema|caos|bloqueo|afectados|"
    r"inundaci[oó]n|apag[oó]n|falta de|exigen|molestia|negligencia|fatal|horrible|accidente)\b",
    re.IGNORECASE
)
PALABRAS_PROPUESTA = re.compile(
    r"\b(gracias|excelente|felicidades|buen trabajo|propongo|sugiero|soluci[oó]n|"
    r"repararon|atendieron|mejor[oó]|apoyo|limpio|seguro|reconocimiento|bendiciones)\b",
    re.IGNORECASE
)

STOPWORDS_ES = {
    "de", "la", "que", "el", "en", "y", "a", "los", "del", "se", "las", "por", "un", "para",
    "con", "no", "una", "su", "al", "lo", "como", "más", "mas", "pero", "sus", "le", "ya",
    "o", "este", "sí", "si", "porque", "esta", "entre", "cuando", "muy", "sin", "sobre",
    "también", "tambien", "me", "hasta", "hay", "donde", "quien", "desde", "todo", "nos",
    "durante", "todos", "uno", "les", "ni", "contra", "otros", "ese", "eso", "ante", "ellos",
    "e", "esto", "mí", "antes", "algunos", "qué", "unos", "yo", "otro", "otras", "otra",
    "él", "tanto", "esa", "estos", "mucho", "quienes", "nada", "muchos", "cual", "poco",
    "ella", "estar", "estas", "algunas", "algo", "nosotros", "mi", "mis", "tú", "te", "ti",
    "xalapa", "veracruz", "ver", "año", "anos", "años", "día", "dias", "días", "hoy", "ser",
    "son", "fue", "han", "ha", "tiene", "tienen", "hacer", "hace", "solo", "sólo", "así",
    "está", "estan", "están", "es", "era", "fueron", "sea", "sido", "ahí", "ahi", "allí",
    "dijo", "señaló", "informó", "comentó", "expresó", "indicó", "tras", "dos", "tres", "cada"
}


def limpiar_texto_para_nmf(texto: str) -> str:
    """Elimina cabeceras de navegación de AVC/portales para que el clustering sea 100% puro."""
    t = BASURA_PORTALES.sub(" ", texto)
    t = MUNICIPIOS_EXTERNOS.sub(" ", t)
    return re.sub(r"\s+", " ", t).strip()


def guardar_topicos_nmf_en_bd(conn, textos: list[str], n_topicos: int = 10):
    print("\n=========================================================================")
    print(" 1. DESCUBRIMIENTO AUTOMÁTICO DE PROBLEMAS EN XALAPA (GUARDADO EN SQLITE)")
    print("=========================================================================")
    textos_limpios = [limpiar_texto_para_nmf(t) for t in textos if len(t) > 30]

    vectorizer = TfidfVectorizer(
        max_df=0.80,
        min_df=10,
        max_features=3500,
        stop_words=list(STOPWORDS_ES),
        ngram_range=(1, 2),
        token_pattern=r"(?u)\b[a-záéíóúñA-ZÁÉÍÓÚÑ]{3,}\b"
    )
    tfidf = vectorizer.fit_transform(textos_limpios)
    nmf = NMF(n_components=n_topicos, random_state=42, init="nndsvd", max_iter=300)
    W = nmf.fit_transform(tfidf)

    # Contar cuántos documentos dominan en cada clúster
    dominantes = Counter(W.argmax(axis=1))
    palabras = vectorizer.get_feature_names_out()

    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS topicos_emergentes_ia;")
    cursor.execute("""
        CREATE TABLE topicos_emergentes_ia (
            id_topico INTEGER PRIMARY KEY,
            palabras_clave TEXT NOT NULL,
            documentos_asociados INTEGER NOT NULL,
            porcentaje_muestra REAL NOT NULL,
            fecha_calculo TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)

    total_docs = len(textos_limpios)
    registros_nmf = []
    for idx, topico in enumerate(nmf.components_):
        top_indices = topico.argsort()[:-10:-1]
        terminos = ", ".join(palabras[i] for i in top_indices)
        n_docs = dominantes.get(idx, 0)
        pct = round((n_docs * 100.0) / total_docs, 2) if total_docs else 0.0
        registros_nmf.append((idx + 1, terminos, n_docs, pct))
        print(f" Clúster #{idx+1:02d} ({pct:>5}%): {terminos}")

    cursor.executemany("""
        INSERT INTO topicos_emergentes_ia (id_topico, palabras_clave, documentos_asociados, porcentaje_muestra)
        VALUES (?, ?, ?, ?);
    """, registros_nmf)
    conn.commit()
    print(" -> Guardados permanentemente en la tabla `topicos_emergentes_ia`.\n")


def clasificar_texto(texto: str, texto_contexto_padre: str = "") -> tuple[str, str | None, str]:
    puntajes = Counter()
    for tema, regex in PATRONES_PROBLEMAS.items():
        coincidencias = len(regex.findall(texto))
        if coincidencias > 0:
            puntajes[tema] += coincidencias * 2

    if not puntajes and texto_contexto_padre:
        for tema, regex in PATRONES_PROBLEMAS.items():
            coincidencias = len(regex.findall(texto_contexto_padre))
            if coincidencias > 0:
                puntajes[tema] += coincidencias

    tema_final = puntajes.most_common(1)[0][0] if puntajes else "Otros Temas Locales / Vida Cotidiana"

    m_col = PATRON_COLONIAS.search(texto) or (PATRON_COLONIAS.search(texto_contexto_padre) if texto_contexto_padre else None)
    colonia = m_col.group(1).title() if m_col else None

    q_score = len(PALABRAS_QUEJA.findall(texto))
    p_score = len(PALABRAS_PROPUESTA.findall(texto))
    if q_score > p_score or tema_final in (
        "Agua Potable, Fugas y Tandeos (CMAS)",
        "Basura, Residuos Sólidos y Limpia Pública",
        "Calles, Baches, Obras y Vialidad",
        "Delincuencia, Inseguridad y Justicia"
    ):
        sentimiento = "Negativo/Queja"
    elif p_score > q_score:
        sentimiento = "Positivo/Propuesta"
    else:
        sentimiento = "Neutral"

    return tema_final, colonia, sentimiento


def crear_vistas_dashboard_y_exportar(conn):
    """Crea Vistas SQL permanentes para el futuro Dashboard y exporta CSVs listos para graficar."""
    cursor = conn.cursor()

    # Vista 1: Resumen maestro por Problemática y Tipo de Fuente (filtrando es_xalapa = 1)
    cursor.execute("DROP VIEW IF EXISTS vw_dashboard_problematicas;")
    cursor.execute("""
        CREATE VIEW vw_dashboard_problematicas AS
        SELECT 
            tema,
            SUM(en_portales) AS noticias_portales,
            SUM(en_fb_posts) AS publicaciones_fb,
            SUM(en_comentarios) AS comentarios_ciudadanos,
            SUM(en_portales + en_fb_posts + en_comentarios) AS volumen_total
        FROM (
            SELECT p.tema_principal_ia AS tema,
                   CASE WHEN f.tipo_origen = 'portal_web' THEN 1 ELSE 0 END AS en_portales,
                   CASE WHEN f.tipo_origen != 'portal_web' THEN 1 ELSE 0 END AS en_fb_posts,
                   0 AS en_comentarios
            FROM publicaciones p
            JOIN fuentes f ON p.id_fuente = f.id_fuente
            WHERE p.es_xalapa = 1
            UNION ALL
            SELECT c.tema_comentario_ia AS tema,
                   0 AS en_portales,
                   0 AS en_fb_posts,
                   1 AS en_comentarios
            FROM comentarios c
        )
        GROUP BY tema
        ORDER BY comentarios_ciudadanos DESC, noticias_portales DESC;
    """)

    # Vista 2: Cruce completo para Dashboard (Fuente + Tema + Género + Edad + Sentimiento)
    cursor.execute("DROP VIEW IF EXISTS vw_dashboard_demografia_temas;")
    cursor.execute("""
        CREATE VIEW vw_dashboard_demografia_temas AS
        SELECT 
            f.id_fuente,
            f.nombre AS nombre_fuente,
            f.tipo_origen,
            c.tema_comentario_ia AS problematica,
            COALESCE(c.genero_inferido, 'Pendiente') AS genero,
            COALESCE(c.rango_edad_estimado, 'Pendiente') AS rango_edad,
            c.sentimiento,
            SUBSTR(c.fecha_comentario, 1, 7) AS anio_mes,
            COUNT(*) AS total_comentarios,
            SUM(c.likes) AS total_likes
        FROM comentarios c
        JOIN fuentes f ON c.id_fuente = f.id_fuente
        GROUP BY f.id_fuente, c.tema_comentario_ia, c.genero_inferido, c.rango_edad_estimado, c.sentimiento, SUBSTR(c.fecha_comentario, 1, 7);
    """)

    # Vista 3: Ranking de Colonias con más menciones por Problemática
    cursor.execute("DROP VIEW IF EXISTS vw_dashboard_colonias;")
    cursor.execute("""
        CREATE VIEW vw_dashboard_colonias AS
        SELECT 
            colonia_detectada AS colonia,
            tema_principal_ia AS problematica,
            COUNT(*) AS total_menciones
        FROM publicaciones
        WHERE es_xalapa = 1 AND colonia_detectada IS NOT NULL
        GROUP BY colonia_detectada, tema_principal_ia
        ORDER BY total_menciones DESC;
    """)
    conn.commit()

    # Exportar la tabla resumen a CSV y JSON en data/dashboard_exports/
    filas = cursor.execute("SELECT * FROM vw_dashboard_problematicas;").fetchall()
    datos_dict = [dict(r) for r in filas]

    (EXPORT_DIR / "resumen_problematicas_xalapa.json").write_text(
        json.dumps(datos_dict, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with open(EXPORT_DIR / "resumen_problematicas_xalapa.csv", "w", newline="", encoding="utf-8-sig") as f_csv:
        writer = csv.DictWriter(f_csv, fieldnames=["tema", "noticias_portales", "publicaciones_fb", "comentarios_ciudadanos", "volumen_total"])
        writer.writeheader()
        writer.writerows(datos_dict)


def ejecutar_fase3_temas():
    with get_connection() as conn:
        cursor = conn.cursor()

        print("[1/4] Filtrando notas estatales (Poza Rica/Boca del Río/Orizaba) para dejar 100% Xalapa...")
        pubs = cursor.execute("SELECT id_publicacion, id_fuente, titulo, contenido_texto FROM publicaciones;").fetchall()
        coms = cursor.execute("""
            SELECT c.id_comentario, c.texto_comentario, p.titulo, p.contenido_texto
            FROM comentarios c
            LEFT JOIN publicaciones p ON c.id_publicacion = p.id_publicacion;
        """).fetchall()

        lote_pubs = []
        corpus_xalapa_puro = []

        for r in pubs:
            titulo = r["titulo"] or ""
            cuerpo = r["contenido_texto"] or ""
            inicio_nota = f"{titulo} {cuerpo[:450]}"

            # Si es de un portal web y el título habla de otro municipio sin mencionar Xalapa, se marca es_xalapa = 0
            es_xalapa_real = 1
            if r["id_fuente"] in (1, 2, 3, 4):
                if MUNICIPIOS_EXTERNOS.search(titulo) and not MARCADORES_XALAPA_ESTRICTO.search(titulo):
                    es_xalapa_real = 0
                elif not MARCADORES_XALAPA_ESTRICTO.search(inicio_nota):
                    es_xalapa_real = 0

            cuerpo_sin_menu = limpiar_texto_para_nmf(f"{titulo}. {cuerpo[:800]}")
            tema, colonia, _ = clasificar_texto(cuerpo_sin_menu)
            lote_pubs.append((tema, colonia, es_xalapa_real, r["id_publicacion"]))

            if es_xalapa_real == 1:
                corpus_xalapa_puro.append(cuerpo_sin_menu)

        # Incluir todos los comentarios ciudadanos de Xalapa en el descubrimiento NMF
        for c in coms:
            corpus_xalapa_puro.append(c["texto_comentario"])

        # 2. Guardar los clústeres sin sesgo en SQLite
        guardar_topicos_nmf_en_bd(conn, corpus_xalapa_puro, n_topicos=10)

        print(f"[2/4] Guardando clasificación en SQLite para {len(lote_pubs)} publicaciones...")
        cursor.executemany("""
            UPDATE publicaciones
            SET tema_principal_ia = ?, colonia_detectada = ?, es_xalapa = ?, procesado_ia = 1
            WHERE id_publicacion = ?;
        """, lote_pubs)
        conn.commit()

        print(f"[3/4] Guardando clasificación en SQLite para {len(coms)} comentarios ciudadanos...")
        lote_coms = []
        for c in coms:
            contexto_padre = limpiar_texto_para_nmf(f"{c['titulo'] or ''} {(c['contenido_texto'] or '')[:600]}")
            tema_c, _, sent_c = clasificar_texto(c["texto_comentario"], contexto_padre)
            lote_coms.append((tema_c, sent_c, c["id_comentario"]))

        cursor.executemany("""
            UPDATE comentarios
            SET tema_comentario_ia = ?, sentimiento = ?, procesado_ia = 1
            WHERE id_comentario = ?;
        """, lote_coms)
        conn.commit()

        print("[4/4] Creando Vistas SQL y exportando archivos para Dashboard en data/dashboard_exports/...")
        crear_vistas_dashboard_y_exportar(conn)

        print("\n================================================================================")
        print(" RANKING LIMPIO DE PROBLEMÁTICAS EN XALAPA (GUARDADO EN VISTAS SQL Y CSV/JSON)")
        print("================================================================================")
        filas_ranking = cursor.execute("SELECT * FROM vw_dashboard_problematicas;").fetchall()
        print(f" {'PROBLEMÁTICA DETECTADA':<48} | {'NOTICIAS':>8} | {'POSTS FB':>8} | {'COMENTARIOS':>11}")
        print("-" * 85)
        for r in filas_ranking:
            print(f" {r['tema']:<48} | {r['noticias_portales']:>8} | {r['publicaciones_fb']:>8} | {r['comentarios_ciudadanos']:>11}")
        print("================================================================================\n")


if __name__ == "__main__":
    ejecutar_fase3_temas()