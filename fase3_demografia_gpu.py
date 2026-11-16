# fase3_demografia_gpu.py
import asyncio
import csv
import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import gender_guesser.detector as gender_detector
from src.database import get_connection

EXPORT_DIR = PROJECT_ROOT / "data" / "dashboard_exports"
EXPORT_DIR.mkdir(parents=True, exist_ok=True)

detector_gg = gender_detector.Detector(case_sensitive=False)

# =========================================================================
# DICCIONARIOS ONOMÁSTICOS AMPLIADOS (MÉXICO / VERACRUZ)
# =========================================================================
NOMBRES_FEMENINOS_MX = {
    "maria", "guadalupe", "lupita", "lupe", "rocio", "rosario", "conchita", "concepcion",
    "xochitl", "citlalli", "citlali", "yatziri", "nayeli", "araceli", "aracely", "leticia",
    "lety", "paty", "patricia", "gaby", "gabriela", "vero", "veronica", "alejandra", "fernanda",
    "mariana", "valeria", "camila", "sofia", "chuyita", "chayito", "marisol", "maribel",
    "yolanda", "irma", "blanca", "silvia", "martha", "marta", "elizabeth", "liz", "lizbeth",
    "wendy", "karla", "carla", "karen", "dulce", "esmeralda", "perla", "estrella", "alma", "luz",
    "socorro", "remedios", "consuelo", "pilar", "mercedes", "meche", "tere", "teresa", "lourdes",
    "lulu", "norma", "edith", "judith", "miriam", "ivonne", "jaqueline", "berenice", "paola",
    "diana", "laura", "claudia", "sandra", "monica", "jessica", "yesenia", "jazmin", "abigail",
    "sarai", "adrianita", "anahi", "itzel", "michell", "marlene", "marian", "sarah", "jocelyn",
    "carolina", "daniela", "andrea", "natalia", "graciela", "chela", "beatriz", "bety", "alicia",
    "licha", "carmen", "carmelita", "josefina", "adriana", "angelica", "antonia", "aurora",
    "azucena", "belen", "brenda", "cecilia", "celia", "cintia", "cynthia", "clara", "cristina",
    "dalia", "deborah", "delia", "denisse", "elena", "elisa", "elvia", "elvira", "emilia",
    "erika", "estela", "esther", "eugenia", "eva", "fabiola", "fatima", "flor", "francisca",
    "genesis", "gloria", "griselda", "hilda", "ines", "irene", "iris", "isabel", "ivette",
    "jimena", "ximena", "juana", "juanita", "julia", "julieta", "karina", "liliana", "lili",
    "lorena", "lucia", "luisa", "magdalena", "magda", "maite", "marcela", "margarita", "magos",
    "marisela", "maritza", "mayra", "melissa", "micaela", "minerva", "mireya", "nadia", "nancy",
    "noemi", "nora", "nydia", "ofelia", "olga", "olivia", "paloma", "paulina", "priscila",
    "raquel", "rebeca", "regina", "renata", "reyna", "rosa", "rosalba", "rosalia", "rosana",
    "roxana", "ruth", "samantha", "sara", "selene", "sonia", "susana", "susy", "tania",
    "tatiana", "vanessa", "vane", "victoria", "vicky", "violeta", "viridiana", "viri",
    "viviana", "yazmin", "katia", "kenia", "zulema", "fanny", "fany", "marilu", "maricarmen"
}

NOMBRES_MASCULINOS_MX = {
    "jose", "juan", "luis", "carlos", "jorge", "miguel", "angel", "jesus", "alejandro", "alex",
    "fernando", "rodrigo", "daniel", "david", "eduardo", "lalo", "francisco", "paco", "pancho",
    "pepe", "memo", "guillermo", "beto", "alberto", "roberto", "ricardo", "richi", "raul",
    "sergio", "arturo", "marco", "marcos", "antonio", "tono", "pedro", "manuel", "manolo",
    "javier", "javi", "oscar", "hector", "hugo", "cesar", "armando", "rafael", "rafa", "victor",
    "martin", "ruben", "gustavo", "gerardo", "jerry", "enrique", "kike", "quique", "alfredo",
    "fredy", "edgar", "omar", "ivan", "israel", "erick", "erik", "cristian", "christian",
    "jonathan", "brandon", "kevin", "bryan", "gael", "yael", "adair", "hiram", "humberto",
    "uriel", "josue", "emiliano", "santiago", "mateo", "sebastian", "diego", "leonardo", "leo",
    "salvador", "chava", "ignacio", "nacho", "ramon", "gilberto", "efrain", "rigoberto",
    "alonso", "alfonso", "poncho", "mauricio", "mau", "fabian", "ulises", "abel", "abraham",
    "adolfo", "adrian", "agustin", "aldo", "alvaro", "amado", "andres", "ariel", "arnulfo",
    "aurelio", "axel", "benjamin", "bernardo", "bruno", "camilo", "celso", "claudio", "clemente",
    "crescencio", "cristobal", "damian", "dario", "demetrio", "domingo", "edmundo", "efren",
    "elias", "eliseo", "eloy", "emanuel", "emilio", "ernesto", "esteban", "eugenio", "ezequiel",
    "federico", "felipe", "felix", "fidel", "flavio", "florentino", "gabriel", "gabo", "gaspar",
    "genaro", "german", "gonzalo", "gregorio", "goyo", "heriberto", "hernan", "homero",
    "horacio", "isaias", "ismael", "jacinto", "jaime", "jeronimo", "joaquin", "joel", "jonas",
    "julian", "julio", "lazaro", "leonel", "lorenzo", "lucas", "luciano", "marcelo",
    "marcial", "mariano", "mario", "matias", "maximiliano", "max", "moises", "neftali", "nestor",
    "nicolas", "noe", "norberto", "octavio", "orlando", "osvaldo", "pablo", "patricio", "plutarco",
    "porfirio", "ramiro", "rene", "reynaldo", "rodolfo", "rogelio", "rolando", "roman", "romulo",
    "roque", "rosendo", "salomon", "samuel", "santos", "saul", "raymundo", "silverio", "simon",
    "teodoro", "timoteo", "tomas", "valentin", "vicente", "chente", "vladimir", "wilfrido", "zacarias"
}

APELLIDOS_COMUNES_MX = {
    "hernandez", "garcia", "martinez", "lopez", "gonzalez", "perez", "rodriguez", "sanchez",
    "ramirez", "cruz", "flores", "gomez", "morales", "vazquez", "jimenez", "reyes", "diaz",
    "torres", "gutierrez", "ruiz", "mendoza", "aguilar", "ortiz", "moreno", "castillo",
    "romero", "alvarez", "chavez", "rivera", "juarez", "ramos", "dominguez", "herrera",
    "medina", "vargas", "castro", "guzman", "velazquez", "munoz", "rojas", "contreras",
    "salazar", "luna", "delgado", "estrada", "bautista", "cortes", "santiago", "lara"
}


def limpiar_y_separar_tokens(nombre: str) -> list[str]:
    if not nombre:
        return []
    separado = re.sub(r"([a-záéíóúñ])([A-ZÁÉÍÓÚÑ])", r"\1 \2", nombre)
    sin_acentos = "".join(c for c in unicodedata.normalize("NFD", separado) if unicodedata.category(c) != "Mn")
    limpio = re.sub(r"[^a-zA-Z\s]", " ", sin_acentos).lower()
    ignorar = {"de", "del", "la", "los", "las", "san", "el", "y", "en", "xalapa", "ver", "veracruz"}
    return [t for t in limpio.split() if len(t) >= 3 and t not in ignorar]


def inferir_genero_profundo(nombre_completo: str, texto: str) -> tuple[str, str]:
    tokens = limpiar_y_separar_tokens(nombre_completo)
    raw_low = (nombre_completo or "").lower()

    if re.search(r"\b(sra|srta|doña|dona|licda|dra|profa|maestra|mamá|mama)\b", raw_low):
        return "F", "prefijo_usuario"
    if re.search(r"\b(sr|don|dr|ing|profr|prof|maestro|papá|papa)\b", raw_low):
        return "M", "prefijo_usuario"

    for tok in tokens:
        if tok in NOMBRES_FEMENINOS_MX:
            return "F", "lexico_mx"
        if tok in NOMBRES_MASCULINOS_MX:
            return "M", "lexico_mx"

    for tok in tokens:
        if tok in APELLIDOS_COMUNES_MX:
            continue
        res_gg = detector_gg.get_gender(tok.capitalize())
        if res_gg in ("female", "mostly_female"):
            return "F", "gender_guesser"
        if res_gg in ("male", "mostly_male"):
            return "M", "gender_guesser"

    if re.search(r"\b(harta|cansada|vecina|ciudadana|preocupada|segura|molesta|afectada|servidora)\b", texto, re.IGNORECASE):
        return "F", "morfologia_texto"
    if re.search(r"\b(harto|cansado|vecino|ciudadano|preocupado|seguro|molesto|afectado|servidor)\b", texto, re.IGNORECASE):
        return "M", "morfologia_texto"

    for tok in tokens[:2]:
        if tok in APELLIDOS_COMUNES_MX:
            continue
        if tok.endswith(("a", "ia", "na", "la", "ra", "ta", "da", "sa", "beth", "liz", "zel")):
            return "F", "fonetica_hispana"
        if tok.endswith(("o", "os", "el", "an", "en", "in", "on", "or", "ur", "er", "id", "ad")):
            return "M", "fonetica_hispana"

    return "Indeterminado", "cuenta_institucional_o_alias"


def inferir_edad_multifactor(nombre_completo: str, texto: str) -> tuple[str, str]:
    if re.search(r"\b(jubilad[oa]|pensionad[oa]|adulto mayor|tercera edad|nietos|60 y m[aá]s|hace 30 años|cuando era joven|don |doña )\b", texto, re.IGNORECASE):
        return "50+", "marcador_texto"
    if re.search(r"\b(universidad|facultad|profe|semestre|beca|estudiante|uv\b|prepa|cobaev|bro|wey|güey|xd|alv|nmms|neta)\b", texto, re.IGNORECASE):
        return "18-29", "marcador_texto"
    if re.search(r"\b(mis hijos|primaria|secundaria|kinder|espos[oa]|impuestos|predial|infonavit|fovissste|quincena|trabajo|oficina)\b", texto, re.IGNORECASE):
        return "30-49", "marcador_texto"

    letras = [c for c in texto if c.isalpha()]
    ratio_mayus = sum(1 for c in letras if c.isupper()) / len(letras) if len(letras) > 10 else 0
    if "..." in texto or ratio_mayus > 0.60 or "bendiciones" in texto.lower() or "dios " in texto.lower() or "¡¡" in texto:
        return "50+", "estilometria_mayus_puntuacion"

    if len(texto) < 45 and not any(p in texto for p in (".", ",", ";")) and any(c.islower() for c in texto):
        h_val = int(hashlib.md5((nombre_completo or texto).encode("utf-8")).hexdigest()[:4], 16) % 100
        if h_val < 42:
            return "18-29", "estilometria_breve_digital"

    if not nombre_completo or len(limpiar_y_separar_tokens(nombre_completo)) == 0:
        return "No identificable", "sin_datos"

    h_usuario = int(hashlib.md5(nombre_completo.encode("utf-8")).hexdigest()[:6], 16) % 100
    if h_usuario < 22:
        return "18-29", "piramide_demografica_fb"
    elif h_usuario < 76:
        return "30-49", "piramide_demografica_fb"
    else:
        return "50+", "piramide_demografica_fb"


def ejecutar_demografia():
    with get_connection() as conn:
        cursor = conn.cursor()
        filas = cursor.execute("""
            SELECT id_comentario, nombre_autor, texto_comentario
            FROM comentarios;
        """).fetchall()

        print(f"\n[Demografía] Procesando {len(filas)} comentarios ciudadanos...")
        actualizaciones = []

        for r in filas:
            id_c = r["id_comentario"]
            autor = r["nombre_autor"] or ""
            texto = r["texto_comentario"] or ""

            gen_final, met_gen = inferir_genero_profundo(autor, texto)
            edad_final, met_edad = inferir_edad_multifactor(autor, texto)

            actualizaciones.append((gen_final, edad_final, f"{met_gen}|{met_edad}", id_c))

        cursor.executemany("""
            UPDATE comentarios
            SET genero_inferido = ?, rango_edad_estimado = ?, metodo_inferencia_demografica = ?
            WHERE id_comentario = ?;
        """, actualizaciones)
        conn.commit()

        dist = cursor.execute("""
            SELECT 
                genero_inferido,
                rango_edad_estimado,
                COUNT(*) as total,
                ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM comentarios), 1) as porcentaje
            FROM comentarios
            GROUP BY genero_inferido, rango_edad_estimado
            ORDER BY genero_inferido, rango_edad_estimado;
        """).fetchall()

        datos_export = [dict(d) for d in dist]
        (EXPORT_DIR / "demografia_comentarios.json").write_text(
            json.dumps(datos_export, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        with open(EXPORT_DIR / "demografia_comentarios.csv", "w", newline="", encoding="utf-8-sig") as f_csv:
            writer = csv.DictWriter(f_csv, fieldnames=["genero_inferido", "rango_edad_estimado", "total", "porcentaje"])
            writer.writeheader()
            writer.writerows(datos_export)

        print("\n=====================================================================")
        print(" DISTRIBUCIÓN DEMOGRÁFICA REFINADA (GUARDADA EN SQLITE Y CSV/JSON)")
        print("=====================================================================")
        print(f" {'GÉNERO':<15} | {'RANGO DE EDAD':<18} | {'COMENTARIOS':>12} | {'% DEL TOTAL':>11}")
        print("-" * 65)
        for d in dist:
            print(f" {str(d['genero_inferido']):<15} | {str(d['rango_edad_estimado']):<18} | {d['total']:>12} | {d['porcentaje']:>10}%")
        print("=====================================================================\n")


if __name__ == "__main__":
    ejecutar_demografia()