# Changelog

## Actualización de la versión 1.2.0

- Barra de acciones adaptable por filas y bibliotecas de componentes con cuadrícula y desplazamiento propios.
- Tema e Idioma en Ver; herramientas de ejecución y sondas agrupadas en Simulación.
- Panel visual integrado, sin flotación, con la misma familia de controles de la biblioteca.
- Menús contextuales explícitos para componentes, módulos y cables; primer clic de cable para seleccionar y segundo para crear nodo.
- Colores y esquinas de módulos editables, guardados en el proyecto y compatibles con deshacer. Puertas lógicas extra pasa a llamarse Retraso de cálculo.

- Opción Ayuda → Avisar de actualizaciones, persistente, para activar o desactivar la consulta y los avisos. Se comprueba también al terminar una consulta en curso.

- Inglés incorporado, junto con español y catalán, con cambio de idioma inmediato y persistente.
- Traducción de mensajes con variables, menús contextuales, tablas, diagnósticos, componentes del tablero, biblioteca predeterminada y controles estándar de Qt.
- Manual integrado disponible en los tres idiomas. Los nombres personales, identificadores de puertos y anotaciones conservan su contenido.
- Catálogos predeterminados actualizados que se combinan con los personalizados sin borrar claves ni mantener traducciones obsoletas idénticas al español.
- Cambio de nombre de módulos desde la biblioteca, actualizando el archivo y las instancias cargadas; validación de nombres y protección contra sobrescrituras y fallos de guardado.
- Nombre de instancia editable desde las propiedades del módulo y conservado al guardar el proyecto.
- Paquetes Windows y MSIX regenerados como 1.2.0 y 1.2.0.0; los manifiestos MSIX declaran español, catalán e inglés.

## [1.2.0]

Esta versión reúne todos los cambios posteriores a la v1.1.0, incluidos los que se habían descrito provisionalmente como 1.1.1–1.4.1. La numeración de los formatos de archivo es independiente de la versión de la aplicación. La publicación de una release es independiente de la compilación local del EXE y el MSI.

### Añadido respecto a v1.1

- Buses sin signo de 2–32 bits, visor transparente con ancho automático, Splitter, Combiner y buffer tri-state; valores `X`/`Z`, comprobación de anchos y avisos de varios drivers tri-state activos.
- Formato combinacional `.dmodule` 1.2 con anchos por puerto; conservación de los formatos publicados 1 y 1.1 y del proyecto `.dalogic` 1. Tabla combinacional de hasta 16 bits de entrada, columnas multi-bit, tiempos estimados y exportación PNG/PDF/SVG/XLSX/CSV.
- Bloques nativos de 1–32 bits: sumador, sumador/restador, comparador, ALU de ocho operaciones, MUX, DEMUX, decodificador y BCD a siete segmentos; canales de selección 2/4/8/16.
- RAM con escritura por flanco ascendente y lectura asíncrona, ROM editable/importable, contador up/down y registro de desplazamiento. Hasta 4096 palabras; contenido y estado persistentes en proyectos, historial y copias.
- DIP, constantes, teclado hexadecimal, pulls débiles, barra y matriz LED, display numérico, LED RGB de 8 bits por canal, semáforo e indicador sonoro opcional. Matrices configurables de hasta 32 LED y etiquetas decimal/hexadecimal/binario en cables de bus.
- Biblioteca de 30 CI en siete familias: 25 combinacionales y cinco secuenciales. Incluye 22 incorporaciones respecto a los ocho archivos de v1.1; referencias antiguas reubicadas al abrir proyectos y definiciones incorporadas en cada proyecto.
- Pestañas Aritmética, Memoria y E/S; árbol de biblioteca con búsqueda por nombre, carpetas, movimiento de CI y conservación de la expansión. Creación de CI con destino elegido, nombre libre, etiquetas y orden de puertos; conectores compactos para más de seis puertos.
- Retardos configurables en milisegundos y etapas de puertas, persistentes en proyectos y tenidos en cuenta en el tiempo estimado de las tablas.
- Sondas mediante Ctrl+clic, historial digital de varias señales y congelación al pausar relojes con F6.
- Rejilla, ajuste a rejilla y cableado ortogonal opcionales; rotación R, espejo H, selección Shift+clic, duplicado, alineación y distribución.
- Indicador de cambios pendientes, confirmación al abrir/cerrar, recuperación automática cada minuto e historial configurable de 10–1000 pasos (100 predeterminados).
- Textos, cuadrados, círculos y planos con edición propia, fuente, borde, relleno, tamaño y opacidad; redimensionado, nombres únicos de planos y encuadre por plano. Persistencia, copia y deshacer de estos elementos.
- Temas claro/oscuro y selector de idioma con aplicación de traducciones en caliente; catálogos ampliados a las interfaces y componentes nuevos.

### Corregido durante la revisión

- Guardado JSON atómico para proyectos, CI, preferencias, recientes, idiomas y recuperación: un fallo de escritura conserva el archivo anterior. Rechazo de NaN y limpieza de temporales fallidos.
- Guardar como conserva el historial y solo marca el documento como guardado cuando la escritura termina; restaura ruta y nombre si falla. Fallos en recientes o eliminación de recuperación no invalidan un proyecto ya guardado. Ctrl+S funciona junto con Ctrl+G.
- Validación previa de proyectos antes de vaciar el tablero: estructura, versión, IDs duplicados, posiciones finitas, orientación, puertos, referencias de cables, colores, puntos medios y elementos visuales. Los archivos inválidos habituales conservan el circuito abierto.
- Validación de CI publicados: tablas completas sin filas repetidas, anchos y valores válidos, tiempos no negativos y referencias internas válidas en módulos secuenciales. Se siguen rechazando las tablas planas experimentales anteriores al repositorio.
- Las señales `X` y `Z` se conservan al cargar, simular y calcular tablas; los buses no se convierten en booleanos. Las tablas de selecciones parciales enumeran todos los valores del ancho de cada puerto.
- Resolución compartida de drivers: los pulls ceden ante fuentes fuertes y `Z` libera su driver. Módulos secuenciales conservan estados indeterminados y muestran `X` si agotan el presupuesto de eventos.
- D Latch de biblioteca: primera entrada D, segunda EN, primera salida Q y segunda Q̅; corregidas las vinculaciones invertidas. Las definiciones ya incorporadas dentro de proyectos anteriores permanecen intactas.
- Copiar/pegar conserva anchos, valores, etiquetas, memoria y estado. Reconstruir conexiones no provoca flancos artificiales en memorias nativas. Las sondas se limpian antes de eliminar sus objetos Qt.
- Dividir un cable conserva sus puntos intermedios, puentes y color. El ajuste al cable sigue el trazado ortogonal visible.
- Preferencias dañadas y rutas de UI antiguas recuperan valores válidos; errores al actualizar catálogos de idioma no impiden disponer de la interfaz. Importar el programa deja de cambiar el directorio de trabajo.
- Comprobación de actualizaciones asíncrona con QtNetwork, timeout de tres segundos, validación de respuesta y comparación numérica de versiones; no ofrece versiones iguales o anteriores y evita bloquear el arranque.
- PNG de circuitos y tablas limitado a 50 millones de píxeles y 32767 píxeles por lado; errores de memoria o escritura se comunican al usuario.

### Optimizado y reorganizado

- Evaluación combinacional en orden de dependencias, con plan reutilizado por cada fila de tabla; se evitan firmas globales repetidas en redes sin realimentación. Se conserva la detección acotada de oscilaciones y el funcionamiento de circuitos independientes.
- Reconstrucción de conexiones y coloreado por redes conductoras, con caché de conectividad; búsqueda de cables en el área local del cursor y borrado en lote al cortar.
- Caché de definiciones de biblioteca por fecha de modificación y tamaño; filtrar no vuelve a leer módulos sin cambios y las modificaciones se detectan.
- `settle_topology` integrado en `widgets/widgets.py`; eliminado `simulation.py`. Validación `.dmodule` centralizada en `project_io.py`, junto con escritura atómica y preparación de proyectos.
- Icono y versión compartidos desde `resources/__init__.py`; eliminado `resources/app_icon.py` y su copia base64. Icono integrado en el recurso Qt canónico.
- Eliminadas las copias generadas `resources/rc_img.py` y `resources/ui/ui_*.py`; interfaces y recursos generados únicamente en `resources/compiled/`.
- `crear_instaladores.py --resources-only` usa las herramientas del Python activo, funciona desde cualquier carpeta y comprueba errores, sin ejecutables Qt Creator fijados a una máquina.
- Reparada la entrada de versión Windows inexistente que referenciaba `DaLogic.spec`: metadatos 1.2.0 en `resources/windows-version.txt`. El spec local incluye la documentación en la distribución; el binario requiere su reconstrucción aparte.
- Dependencia PySide6 alineada con los recursos regenerados: `>=6.10,<7`. Manifiesto de proyecto actualizado y `.gitignore` deja de excluir `pyproject.toml` y `ROADMAP.md`.
- README, guía de componentes y roadmap unificados bajo 1.2; retiradas afirmaciones sobre minimapa, filtros/orden y CI de registro/contador que no existen en la biblioteca final.

### Validación

- 60 pruebas automatizadas en tres archivos: puertas, buses, X/Z, pulls, aritmética exhaustiva de cuatro bits y ocho operaciones ALU, selección, BCD, memoria y flancos, matriz LED, los 30 CI, latch/flip-flops con resultados esperados independientes, persistencia, validación, fallos de escritura, historial, copia, sondas, cables, retardos, actualizaciones y renderizado/exportación Qt. Suite superada en Windows con Python 3.12 y 3.14 / PySide6 6.10.3.
- Exportaciones de circuito PNG/PDF/SVG y tabla PNG/PDF/SVG/XLSX verificadas; carga del proyecto Calculadora comprobada.
- Comparación local de reconstrucción de cadenas de 300/1000 NOT: mediana de tres ejecuciones, sin dibujo ni temporizadores, frente al código previo a esta revisión. Para 1000 NOT: 267,585 → 3,948 ms; 2000 → 1000 evaluaciones de puertas. Es una medición de este escenario, no de todos los circuitos.

## [1.1.0]

### Añadido

- Componente **Reloj** con intervalo de cambio configurable entre 10 y 60.000 ms (500 ms por defecto).
- Control para pausar o reanudar todos los relojes del circuito desde la barra de herramientas o con **F6**.
- Circuitos secuenciales y realimentación: los CI secuenciales guardan el circuito interno y cada instancia mantiene su propio estado.
- Detección de oscilaciones y bucles de señal, con detención de la simulación y pausa de los relojes.
- Persistencia del estado lógico de los componentes y de los CI secuenciales en los proyectos.
- Documentación sobre relojes, retardos, tablas combinacionales y circuitos con memoria.

### Cambiado

- Los relojes conectados se incluyen como entradas binarias al calcular una tabla de verdad; durante el cálculo permanecen estáticos.
- Los circuitos con realimentación y los CI secuenciales no generan tablas de verdad combinacionales.
- Los archivos `.dmodule` usan el formato publicado **1** para CI combinacionales y el formato **1.1** para CI secuenciales.
- Se conserva la compatibilidad con el formato combinacional publicado 1; se rechazan los archivos de prueba antiguos que empaquetaban sus filas como una lista plana de enteros.
- Los catálogos de idioma se limitan a cadenas visibles de la interfaz.

### Corregido

- Al eliminar componentes o cables, cortar, deshacer o rehacer se reconstruyen las conexiones y se recalculan las señales para quitar activaciones obsoletas.
- Al abrir o reconstruir un proyecto se restauran las conexiones, los estados guardados y la sincronización de los relojes.

### Mantenimiento de empaquetado

- Un único `crear_instaladores.py` crea Normal, console, ZIP, MSI, MSIX y los cuatro hashes.
- Layouts y menús compartidos integrados en `widgets/visual.py`; cálculos y diagnósticos integrados en `board_view.py`.
- MSIX con textos es/ca/en y recursos gráficos de alta densidad; conserva solo `runFullTrust` por compatibilidad.

### Edición de módulos · 20 de octubre de 2026

- Los nombres de .dmodule y sus etiquetas conservan el texto original en todos los idiomas.
- Editor común con Etiquetas, Aspecto y Simulación; nombre y orden de entradas/salidas editables sin desconectar cables.
- Aceptar aplica al circuito, Guardar actualiza el archivo original y Cancelar descarta cambios. Guardado atómico y edición reversible.

### Biblioteca CI y menús · 20 de octubre de 2026

- Selección continua en CI, sin doble fondo ni marco negro de foco; navegación por teclado conservada.
- Iconos de módulos con el logo de DaLogic y carpetas sin traducción.
- Menús más compactos: los modificadores visibles y su medida coinciden, con menor margen derecho y flechas de submenú separadas de los atajos.

### Controles oscuros, módulos y texto · 20 de octubre de 2026

- Paleta oscura completa para cabeceras, esquina de tablas y controles nativos; flechas vectoriales legibles en los selectores numéricos.
- Previsualizaciones de componentes con el tema activo, incluso al alternar el tema durante la colocación.
- Módulos con dimensiones calculadas a partir de su nombre y sus etiquetas, en zonas independientes. Los puertos mantienen el orden vertical y siguen correctamente el giro y el espejo.
- Pestañas con flechas de desplazamiento opacas y áreas de hover independientes, sin indicadores de corte dentados.
- Menús contextuales separados del evento de pulsación para evitar que el arrastre posterior active también una selección rectangular.
- Medición nativa de todos los atajos visibles, incluidos alias, sin acumulación de ancho al reabrir los menús o cambiar el idioma.

### Menús y desplazamiento de pestañas · 20 de octubre de 2026

- Los atajos se dibujan y miden solo dentro de los menús, sin alterar el texto de las acciones compartidas con la barra superior.
- El tamaño de los menús se recalcula tras cambios de tema, fuente y acciones, incluso si siguen abiertos.
- Línea de cierre después de la flecha derecha de las pestañas y finalización explícita del hover al entrar en las flechas, incluidas las desactivadas.

### Puertos verticales y selección azul · 20 de octubre de 2026

- Las puertas con más de seis puertos y los divisores/combinadores de bus crecen en altura y muestran una sola columna de puertos a cada lado, en lugar de dos columnas.
- Display con entradas a–g en una sola columna, mayor altura y etiquetas visibles. El giro y el espejo conservan las conexiones de cada segmento.
- Color azul común para selección de componentes, módulos, elementos visuales, cables y nodos, en claro y oscuro; también se muestra en el teclado hexadecimal.
