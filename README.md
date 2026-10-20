# DaLogic — v1.2.0

Editor y simulador gráfico de circuitos lógicos digitales con PySide6. Incluye puertas, buses, aritmética, memoria, periféricos y una biblioteca de 30 circuitos integrados reutilizables.

[Componentes](docs/componentes-1.2.md) · [Tiempo y realimentación](docs/tiempo-y-realimentacion.md) · [Depuración y CI](docs/depuracion-y-ci.md) · [Changelog](CHANGELOG.md)

## Edición y menús

La barra de acciones se reorganiza en filas al reducir la ventana; las categorías permanecen accesibles y sus componentes se desplazan dentro de cada pestaña. El panel de componentes visuales permanece integrado en la aplicación.

Ver contiene Tema, Idioma, Acercar, Alejar, Ajustar, Mostrar rejilla, Ajustar a rejilla y Cables en ángulo recto. Simulación reúne las pausas, el avance por pasos, los puntos de parada y las sondas.

En un cable, el primer clic selecciona y el segundo crea un nodo. Su menú contextual ofrece Crear nodo, Cambiar color y Eliminar. Las puertas y periféricos ofrecen Eliminar y Editar; los módulos ofrecen Eliminar y Cambiar aspecto. El aspecto de cada módulo se conserva en el proyecto y admite deshacer. El ajuste temporal de etapas adicionales se llama Retraso de cálculo.

## Funciones

- Editor con cables, nexos, puentes, colores, rejilla, zoom, rotación, espejo, alineación y distribución.
- Texto, formas y planos con propiedades, nombres únicos y encuadre individual.
- Copiar, cortar, pegar, duplicar, deshacer/rehacer y comprobación de cambios pendientes.
- Proyectos JSON `.dalogic`, guardado atómico y recuperación automática cada minuto mientras hay cambios.
- Puertas de 2–8 entradas, fuentes, pulsadores, relojes, retardos, bombillas y displays.
- Buses de hasta 32 bits, splitters/combiners, visores, tri-state, señales X/Z y pulls.
- Sumadores, restadores, comparadores, ALU, multiplexores, decodificadores, RAM, ROM, contadores y registros de desplazamiento.
- Biblioteca de CI organizada por carpetas, búsqueda y módulos importados.
- CI secuenciales con memoria independiente por instancia. El nuevo formato 1.3 permite encapsular memoria nativa y buses, además de las puertas y módulos anteriores.
- Diagnóstico de entradas libres, redes sin fuente, anchos incompatibles, conflictos tri-state y estados X.
- Simulación por pasos, pausa completa y puntos de parada en componentes seleccionados.
- Sondas con capacidad configurable de 256 a 100.000 cambios por señal (10.000 por defecto), navegación temporal y exportación CSV/VCD.
- Tabla de verdad combinacional de hasta 16 bits de entrada; progreso cancelable desde 4.096 combinaciones.
- Exportación del circuito PNG/PDF/SVG y de tablas PNG/PDF/SVG/XLSX/CSV.
- Temas claro/oscuro, español/catalán/inglés, manual integrado traducido y consulta asíncrona de actualizaciones.

## Ejecutar desde fuentes

Requisitos: Python 3.10 o posterior y PySide6 `>=6.10,<7`, con un entorno gráfico compatible. El flujo de distribución se ejecuta en Windows x64.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py
```

También puedes pasar la ruta de un proyecto:

```powershell
python main.py "Proyectos/mi circuito.dalogic" --no-update-check
```

`--no-update-check` evita consultar actualizaciones. `--smoke-test` comprueba el arranque y el proyecto opcional, y cierra: devuelve 0 si funciona, 1 si falla o 2 si otra instancia utiliza la misma carpeta de datos. No restaura ni elimina una recuperación pendiente.

Abre `pyproject.toml` en Qt Creator y selecciona el Python con PySide6. Las fuentes de Designer están en `resources/ui/`; las interfaces se regeneran con `pyside6-uic --from-imports` y las imágenes de `resources/img.qrc` con `pyside6-rcc`. En el entorno local de distribución también puedes usar `python crear_instaladores.py --resources-only`. `resources/compiled/` se conserva en Git para poder ejecutar un checkout sin regenerarlo primero.

## Organización del código

Los módulos escritos a mano se agrupan por responsabilidad:

- `main.py`: ventana principal, diálogos y coordinación de las acciones del editor.
- `app_runtime.py`: rutas, datos del usuario, actualizaciones, arranque y registro de errores.
- `board_view.py`: tablero, cableado, propagación, cálculos cancelables y diagnóstico eléctrico.
- `project_io.py`: proyectos y módulos JSON, guardado atómico y exportación de sondas CSV/VCD.
- `widgets/`: lógica de componentes, componentes nativos y sus representaciones gráficas; las anotaciones visuales permanecen en `visual.py`.
- `crear_instaladores.py` (solo local, excluido de Git): única fuente de creación de recursos Qt, ejecutables, ZIP, MSI y MSIX.
- `widgets/visual.py`: layouts adaptables, menús, anotaciones y paletas visuales.

Las interfaces generadas permanecen en `resources/compiled/`, separadas del código editable.

## Crear los medios de instalación

El sistema de distribución se conserva solo en el entorno local y se excluye de Git. Toda su autoría está en `crear_instaladores.py`:

```powershell
py -3 crear_instaladores.py --preparar-entorno
```

Prepara `.venv-build`, ejecuta las pruebas, regenera los recursos Qt y compila ambas variantes con PyInstaller. Reutiliza cargadores oficiales reconstruidos con CFG, DEP y ASLR. Crea `dist/Normal`, `dist/console`, los dos ZIP con nombres formales, el MSI, `Store` con el MSIX y `SHA256SUMS.txt` con los cuatro paquetes. Conserva la entrega anterior en `build/previous-distributions/`.

Usa `--solo-instaladores` para reutilizar los EXE, `--solo-msix` para generar únicamente Store, o `--salida CARPETA_NUEVA` para guardar otra entrega. Consulta [las instrucciones completas](docs/CREAR_INSTALADORES.md).

El MSI conserva el asistente de `delivery-v12`: bienvenida, privacidad, personalización, resumen y progreso. Permite elegir destino y accesos directos. Los datos personales permanecen fuera de la carpeta de instalación. Consulta [la guía del MSI](docs/instalador-msi.md).

El MSIX conserva solo `runFullTrust` para mantener la compatibilidad de escritorio. Windows puede mostrar «Uses all system resources»; no se añaden capacidades innecesarias ni se oculta el aviso. Incluye logo circular y recursos visuales y textos localizados. La interfaz de instalación pertenece a Windows.

## Uso rápido y atajos

1. Añade componentes desde las pestañas de la izquierda y arrástralos al tablero.
2. Haz clic en un puerto y luego en otro para conectarlos; los clics en vacío crean codos. Esc cancela el trazado.
3. Un doble clic cambia un interruptor. Un pulsador se activa mientras se mantiene presionado. El menú contextual configura cada componente.
4. Guarda el proyecto con Ctrl+S. Selecciona un circuito con sus fuentes y salidas y usa Widgets → Crear CI para reutilizarlo.
5. Usa F7 para comprobar el circuito, F1 para el manual y Ctrl+clic para colocar una sonda.

| Acción | Atajo |
| --- | --- |
| Nuevo / abrir | Ctrl+N / Ctrl+O |
| Guardar / guardar como | Ctrl+S o Ctrl+G / Ctrl+Mayús+S |
| Copiar / cortar / pegar / duplicar | Ctrl+C / Ctrl+X / Ctrl+V / Ctrl+D |
| Deshacer / rehacer | Ctrl+Z / Ctrl+Y |
| Eliminar / girar / espejar | Supr / R / H |
| Tabla de verdad | Ctrl+Mayús+F |
| Exportar circuito | Ctrl+P |
| Ajustar / acercar / alejar | Ctrl+0 / Ctrl++ / Ctrl+- |
| Alinear / distribuir | Ctrl+Mayús+A / Ctrl+Mayús+D |
| Tema claro/oscuro | Ctrl+Mayús+T |
| Manual / comprobar circuito | F1 / F7 |
| Pausar relojes | F6 |
| Pausar toda la simulación | F8 |
| Alternar punto de parada en selección | F9 |
| Avanzar un lote de eventos | F10 |
| Añadir sonda | Ctrl+clic en cable o puerto |

Rueda para zoom y botón central con arrastre para desplazar el tablero. Los avisos de puertos libres pueden ser intencionados y no cambian la lógica del circuito.

### Puntos de parada: inspeccionar una señal

Selecciona una puerta, un módulo o una salida con entradas y pulsa **F9**, o usa **Simulación → Añadir punto de parada**. La marca roja indica que se observarán sus entradas. Los interruptores y relojes no reciben entradas y no admiten esta parada.

Cuando cambia una entrada marcada, se calcula ese lote y se pausa la simulación antes de aplicar los eventos siguientes. La marca se vuelve naranja y la vista muestra el componente. **F10** aplica el siguiente lote; **F8 / Reanudar simulación** continúa normalmente.

Ejemplo: conecta **Interruptor → NOT → Bombilla** y marca NOT. Al cambiar el interruptor, NOT se actualiza y la simulación se pausa. La bombilla mantiene su estado hasta que pulses F10 o F8. Esto permite seguir la propagación de la señal.

F9 quita las marcas de los componentes seleccionados si todos están marcados; en una selección mixta, los marca todos. Son ayudas temporales: no se guardan en el circuito y se limpian al abrir, crear o reconstruir un proyecto. Los módulos se observan por sus entradas externas.

## Archivos, formatos y datos personales

- `.dalogic` conserva componentes, cables, propiedades, formas y estados internos.
- `.dmodule` 1 almacena tablas escalares; 1.1 conserva redes secuenciales escalares; 1.2 almacena tablas con buses/X/Z; 1.3 conserva redes secuenciales con memoria nativa y buses. La aplicación lee los cuatro formatos y elige automáticamente el menor que admite el circuito. El formato de archivo 1.3 se admite desde DaLogic 1.2.0; la numeración del formato es independiente de la versión de la aplicación.
- Las tablas combinacionales excluyen circuitos con memoria o realimentación. Sus salidas dependen también del estado previo.
- Las sondas conservan un historial acotado en memoria; exporta la captura antes de cerrar. Cambiar la capacidad puede eliminar las muestras más antiguas.
- Desde fuentes se usa `user/` cuando es escribible. El ejecutable usa los datos por usuario del sistema, normalmente `%LOCALAPPDATA%/DaLogic` en Windows.
- `DALOGIC_DATA_DIR` permite elegir una carpeta explícita. También sitúa Proyectos y Exports dentro de ella; sin esa variable el ejecutable propone Documentos/DaLogic para esos archivos.
- La biblioteca y los idiomas predeterminados están en `resources/defaults/`. Se copian al perfil sin reemplazar archivos existentes. Los datos de una instalación anterior se conservan.
- Una segunda instancia con la misma carpeta de datos se rechaza. Los errores se registran en `dalogic.log`, con rotación a 1 MB y dos archivos anteriores.

Los catálogos de español, catalán e inglés se distribuyen en resources/defaults/Idiomas. Para añadir un idioma, crea un JSON en user/Idiomas con code, name y translations. Las claves son frases originales en español; los mensajes dinámicos usan marcadores como {v0} o {name}, que deben conservarse. Los catálogos personalizados se combinan con los predeterminados sin borrarlos ni eliminar claves. Los campos que faltan usan el catálogo distribuido o el texto original. Los controles estándar de Qt se traducen con sus catálogos oficiales.

Para cambiar el nombre de un .dmodule, abre la pestaña CI, haz clic derecho en el módulo de la biblioteca y elige Cambiar nombre. Se actualizan el nombre interno, el archivo y sus instancias cargadas sin reemplazar otro módulo. Para cambiar solo una instancia, edita Nombre del módulo en sus propiedades y guarda el proyecto.

## Qué se incluye en Git

Se conservan código de la aplicación, recursos, UI compilada, iconos, biblioteca e idiomas predeterminados, documentación y manifiesto Qt Creator. Todo `user/` es local y se excluye de Git, incluidas `user/Biblioteca/`, `user/Idiomas/`, preferencias y copias de seguridad. La biblioteca y los idiomas compartidos se distribuyen desde `resources/defaults/`. Se excluyen el sistema local de creación de instaladores (`crear_instaladores.py`, `DaLogic.spec`, `requirements-build.txt`, `resources/windows-version.txt` y `.github/workflows/tests.yml`), `tests/`, todo `user/`, `Proyectos/`, `Exports/`, entornos, herramientas descargadas, compilaciones, paquetes, temporales y certificados privados.

El `.gitignore` no borra archivos locales. Los archivos personales que estaban ya versionados se retiran únicamente del índice. No se realizan commits ni se publica el repositorio automáticamente.

## Pruebas y límites de verificación

```powershell
python -m unittest discover -s tests -v
```

Los tests se conservan solo localmente y no se suben a GitHub. Si están presentes, las pruebas usan Qt offscreen y datos temporales. Cubren lógica, aritmética, buses/X/Z, memoria, CI nativos, estado independiente, persistencia, guardado fallido, recuperación, historial, edición, sondas, pasos, puntos de parada y exportaciones. Los proyectos personales de ejemplo se comprueban cuando existen y se omiten en un checkout limpio.

La validación local se realiza en Windows con Python 3.12 y PySide6 6.12. El flujo de creación de instaladores de GitHub Actions se conserva solo localmente y se excluye de Git junto con sus herramientas. La prueba offscreen no sustituye pruebas físicas de ratón, DPI o audio, ni certifica macOS/Linux. PNG limita la resolución en circuitos muy extensos para acotar memoria; PDF/SVG conservan salida vectorial.

## Licencia

Creado por David Lopez Borrego. Licencia Apache 2.0; conserva [LICENSE](LICENSE) y [NOTICE](NOTICE) al redistribuir. La ventana de créditos mantiene la atribución del proyecto.


En Ayuda → Avisar de actualizaciones puedes activar o desactivar la consulta y el aviso de nuevas versiones. La preferencia se conserva al reiniciar. Al activarla se comprueba la última versión; al desactivarla tampoco se muestran resultados de consultas que ya estuvieran en curso.

## Editar módulos .dmodule

Los nombres de módulos y sus etiquetas no se traducen al cambiar el idioma. Haz doble clic sobre un módulo o usa Cambiar aspecto para abrir las pestañas Etiquetas, Aspecto y Simulación. En Etiquetas puedes cambiar el nombre y ordenar entradas y salidas con Subir/Bajar, conservando sus cables. **Aceptar** aplica al circuito; **Guardar** también actualiza el .dmodule; **Cancelar** descarta la edición pendiente. Consulta [la guía de módulos](docs/modulos.md).

## Biblioteca CI y menús

La selección de CI se muestra como una sola fila, con el logo de DaLogic en los módulos. Las carpetas y los módulos conservan sus nombres originales en todos los idiomas. Los menús superiores ajustan su ancho al texto y muestran los atajos con el formato `Ctrl + …`, dejando sitio para las flechas de los submenús.

Los módulos ajustan el cuerpo y el área del título a su nombre y reservan espacio independiente para las etiquetas de cada lado. En oscuro, las previsualizaciones, cabeceras y flechas siguen el tema. Las flechas de las pestañas tienen su propia zona de interacción.

Los botones de la barra superior conservan sus nombres al abrir menús; los atajos aparecen dentro de los desplegables. Su ancho se actualiza al cambiar de tema o fuente. Al pasar de una pestaña a una flecha de desplazamiento se retira el hover de la pestaña; el control derecho termina con una línea divisoria.

Los puertos se muestran en una columna vertical por cada lado. Las puertas con muchas entradas y los divisores/combinadores aumentan su altura para mantener espacio entre puertos; el display ordena sus entradas a–g de arriba abajo. Todos los tipos de componentes, módulos y cables usan azul para indicar la selección.
