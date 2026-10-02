# Brújula Bibliográfica · Termografía mamaria

Aplicación en Python para explorar una revisión bibliográfica en desarrollo sobre inteligencia artificial aplicada a la clasificación del cáncer de mama mediante termografía infrarroja. La interfaz muestra la procedencia de los registros, permite descargar los conjuntos de datos y ofrece filtros, puntajes de afinidad y gráficos por objetivo de investigación.

## Preguntas de la revisión

1. ¿Qué bases de datos se mencionan, con qué frecuencia y bajo qué condiciones de acceso?
2. ¿Qué técnicas de preparación y aumento de imágenes se mencionan y con qué propósito?
3. ¿Qué modelos de aprendizaje automático o profundo, tipos de clasificación y herramientas se mencionan?
4. ¿Qué métricas, resultados y limitaciones metodológicas se reportan?

Los temas multimodalidad, explicabilidad (XAI) y software figuran como líneas futuras en la interfaz.

## Datos y proceso

| Etapa | Registros | Archivo principal |
| --- | ---: | --- |
| Scopus | 629 | `data/SC1.csv` |
| Web of Science | 264 | `data/WS1.xls` |
| Unificación de columnas | 893 | `outputs/dataset_scopus_wos/dataset_unificado.xlsx` |
| Tras fusionar 227 pares duplicados | 666 | `outputs/dataset_scopus_wos/dataset_final_deduplicado.xlsx` |
| Tras apartar 65 registros con el filtro textual de termografía mamaria | 601 | `outputs/dataset_scopus_wos/dataset_final.xlsx` |
| Con puntajes y motivos de recomendación | 601 | `outputs/dataset_scopus_wos/dataset_analizado.csv` |

La aplicación calcula las cifras de la portada leyendo los archivos incluidos. El filtro temático revisa título, resumen y palabras clave; se conserva un artículo que menciona específicamente termografía mamaria aunque también trate otras tecnologías. Los registros apartados y su motivo están en `descartados_filtro_termografia.csv`.

## Cómo se generan los resultados

`analisis_local.py` calcula afinidad textual con los cuatro objetivos mediante TF-IDF y reglas explícitas; el CSV analizado incluye el nivel de recomendación, puntajes y motivos. `analytics.py` detecta menciones de bases de datos, estrategias, modelos, métricas y limitaciones en los campos bibliográficos. Los valores son una **prioridad de lectura**, no probabilidades calibradas ni decisiones definitivas de inclusión. Una mención de una métrica o modelo tampoco confirma su uso en el estudio: eso requiere revisar el texto completo.

Esta versión no se conecta a ChatGPT ni usa una clave de API. Los resultados mostrados proceden del CSV analizado y de cálculos locales reproducibles.

## Ejecutar localmente

Se recomienda Python 3.12.

```bash
python -m venv .venv
python -m pip install -r requirements.txt
python -m streamlit run brujula_bibliografica/app.py
```

En Windows, activa el entorno virtual antes de instalar las dependencias, o usa directamente `.venv/Scripts/python.exe`. La página se abre normalmente en `http://localhost:8501`.

## Publicar en Railway

1. Conecta este repositorio privado de GitHub a un nuevo servicio de Railway.
2. En **Settings → Deploy**, establece el comando de inicio `sh start.sh`.
3. En **Settings → Networking**, usa **Generate Domain** para obtener el enlace público.
4. Abre el enlace y comprueba que cargan la portada, las descargas y el análisis.

`start.sh` hace que Streamlit escuche en el puerto que asigna el alojamiento. Railway tiene un plan Free con crédito mensual limitado; consulta el consumo del servicio en su panel.

## Archivos principales

- `brujula_bibliografica/app.py`: interfaz.
- `brujula_bibliografica/project_report.py`: cifras y rutas de los datos.
- `brujula_bibliografica/analytics.py`: conteos de menciones.
- `brujula_bibliografica/analisis_local.py`: puntajes locales.
- `brujula_bibliografica/filtrar_termografia.py`: filtro temático.
- `brujula_bibliografica/test_core.py`: pruebas del procesamiento.
- `data/` y `outputs/dataset_scopus_wos/`: fuentes y resultados que utiliza la aplicación.

El repositorio es privado porque contiene las exportaciones bibliográficas originales y permite descargarlas desde la aplicación.
