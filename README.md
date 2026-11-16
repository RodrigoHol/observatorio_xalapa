# Observatorio Ciudadano de Xalapa: Sistema Automatizado de Ingesta, Análisis Demográfico y Descubrimiento de Problemáticas

Documentación técnica y metodológica del pipeline de recolección, procesamiento y estructuración de datos sobre la opinión y problemáticas de la población de Xalapa, Veracruz (Periodo: Enero 2025 – Noviembre 2026).

---

## 1. Resumen Ejecutivo y Estadísticas Totales del Banco de Datos

El observatorio recopila, filtra y analiza de forma automatizada información proveniente de medios de comunicación institucionales (para evitar sesgos) y redes sociales (para capturar la interacción ciudadana directa).

* **Total de Registros Recolectados:** >28,900 elementos únicos analizados.
* **Base de Datos Persistente:** SQLite (`data/observatorio_xalapa.db`) con modo `WAL` activado para acceso concurrente de alto rendimiento.
* **Desglose General del Volumen:**
  * **Portales Web (Banco General):** **24,693 notas periodísticas** filtradas estrictamente para el municipio de Xalapa.
  * **Facebook (Páginas y Grupos):** **575 publicaciones** y **3,690 comentarios ciudadanos** con vinculación relacional a su post madre, nombre de autor anonimizado/hash y URL de avatar.

---

## 2. Arquitectura de Fuentes de Información

La ingesta se dividió en dos capas complementarias para garantizar representatividad y cero sesgo ideológico:

| ID Fuente | Nombre de la Fuente | Tipo de Origen | Registros Obtenidos | Rango Temporal |
| :---: | :--- | :--- | :---: | :---: |
| **1** | Diario de Xalapa (OEM) | Portal Web | 901 notas | Ene 2025 – Nov 2026 |
| **2** | Al Calor Político (Portal) | Portal Web | 324 notas | Ene 2025 – Nov 2026 |
| **3** | El Heraldo de Xalapa | Portal Web | 1,876 notas | Feb 2025 – Nov 2026 |
| **4** | AVC Noticias (Portal) | Portal Web | 21,592 notas | Ene 2025 – Nov 2026 |
| **5** | Página FB (ID 100064946853452) | Página Facebook | 116 posts / 1,663 coms | Ene 2025 – Nov 2026 |
| **6** | Xalapa Noticias Digitales | Página Facebook | 234 posts / 1,250 coms | Ene 2025 – Nov 2026 |
| **7** | AVC Noticias (FB) | Página Facebook | 0 posts / 0 coms* | - |
| **8** | Grupo FB (266246240411326) | Grupo Facebook | 58 posts / 291 coms | Ene 2025 – Nov 2026 |
| **9** | Grupo Al Calor Político | Grupo Facebook | 167 posts / 486 coms | Ene 2025 – Nov 2026 |

*\*Nota: La fuente 7 quedó cubierta ampliamente por las 21,592 notas directas del portal web de AVC Noticias.*

---

## 3. Metodología de Procesamiento e Inteligencia Artificial Local

Todo el procesamiento analítico se ejecutó de manera local optimizando el hardware disponible (CPU i5, 16 GB RAM, RTX 3050):

1. **Filtro Geográfico Estricto:** Validación mediante expresiones regulares y marcadores espaciales para descartar notas estatales ajenas a Xalapa (eliminando ruido de Poza Rica, Boca del Río u Orizaba).
2. **Descubrimiento de Tópicos sin Sesgo (NMF + TF-IDF):** Aplicación de factorización de matrices no negativas sobre un corpus masivo para extraer matemáticamente los clústeres emergentes de la agenda pública sin imponer categorías previas.
3. **Clasificación Demográfica Híbrida (Género y Edad):** 
   * Asignación de género (`M`, `F`, `Indeterminado`) mediante onomástica mexicana, diccionarios del INEGI, `gender-guesser` y morfología textual.
   * Estimación de rangos de edad (`18-29`, `30-49`, `50+`) combinando cohorte de nombres, estilometría digital (uso de mayúsculas, puntuación y modismos) y marcadores lingüísticos explícitos, logrando reducir los perfiles indeterminados a menos del 10%.

---

## 4. Hallazgos Principales: Ranking de Problemáticas

El contraste entre la agenda mediática y la conversación ciudadana muestra que, mientras los portales informan sobre política y eventos institucionales, el debate ciudadano se concentra fuertemente en servicios y seguridad:

1. **Calles, Baches, Obras y Vialidad:** Principal motor de queja ciudadana directa en redes sociales y foco constante de reportes vecinales.
2. **Delincuencia, Inseguridad y Justicia:** Alta recurrencia tanto en notas periodísticas como en preocupación manifestada por la población.
3. **Salud Pública, Dengue y Hospitales:** Problemática estacional y estructural reflejada en la prensa y debates locales.
4. **Medio Ambiente, Áreas Verdes y Maltrato Animal / Agua Potable (CMAS):** Temas con alta participación ciudadana y movilización digital.

---

## 5. Estructura del Proyecto y Archivos del Pipeline

### Credenciales de Apify

Instala las dependencias con `python -m pip install -r requirements.txt`. Copia
`.env.example` a `.env` y sustituye los valores de `APIFY_TOKENS` por tus tokens
de Apify separados por comas. El archivo `.env` está excluido de Git; no agregues
tokens directamente al código ni al repositorio.

El código fuente modular se encuentra organizado en la raíz del proyecto:

```text
observatorio_xalapa/
├── data/
│   ├── observatorio_xalapa.db          # Base de datos SQLite principal (WAL mode)
│   ├── apify_backups/                  # Caché local de seguridad de las extracciones API
│   └── dashboard_exports/              # Archivos CSV y JSON listos para consumo externo
├── src/
│   ├── database.py                     # Capa de persistencia, esquemas e índices
│   └── scrapers/                       # Scripts de ingesta asíncrona (Portales y FB)
├── main_fase1.py                       # Orquestador del banco de noticias (Fase 1)
├── fase2_apify.py                      # Orquestador de recolección de Facebook (Fase 2)
├── fase3_temas_ia.py                   # Motor de clasificación temática y clustering NMF
└── fase3_demografia_gpu.py             # Motor de inferencia demográfica (Género y Edad)