# DaLogic — Release v1.0.0

DaLogic es un editor gráfico de circuitos lógicos digitales. Permite diseñar y simular circuitos, calcular tablas de verdad y guardar circuitos integrados (CI) reutilizables. La interfaz está en español y los proyectos se guardan en formatos JSON propios.


## Funciones

### Editor y cableado

- Coloca y mueve componentes en el tablero y conecta sus puertos con cables.
- Los cables se ajustan a puertos, nexos y extremos. Un doble clic sobre el tablero o un cable crea un nexo, que también permite ramificar conexiones.
- Cambia la apariencia de cada nexo entre Nexo, Puente, Puente hacia el otro lado y el modo inicial. Los puentes ilustran cruces sin modificar la conectividad lógica.
- Edita el color de cada cable desde su menú contextual.
- Selecciona, copia, corta, pega y elimina componentes. Las copias aparecen ligeramente desplazadas.
- Zoom con la rueda del ratón; desplaza el tablero con el botón central y arrastre. Ajustar a circuito encuadra el diseño. Puedes alternar entre tema claro y oscuro desde Ver.
- Con más de seis entradas o salidas, los conectores se distribuyen en columnas para facilitar su selección.

### Componentes

| Elemento | Funcionamiento |
| --- | --- |
| AND | Salida activa si todas las entradas lo están; admite 2–8 entradas. |
| OR | Salida activa si alguna entrada lo está; admite 2–8 entradas. |
| XOR | Salida activa si hay un número impar de entradas activas; admite 2–8 entradas. |
| NOT | Invierte su única entrada. |
| NAND / NOR | Resultado invertido de AND / OR; admiten 2–8 entradas. |
| Interruptor | Fuente persistente; doble clic alterna su estado. |
| Botón momentáneo | Activo mientras se mantiene pulsado. |
| Retardo | Retrasa la propagación durante el tiempo configurado, en milisegundos. |
| Bombilla | Se enciende con señal activa; permite editar retardo y color encendido. |
| Display de 7 segmentos | Muestra los segmentos a–g conectados; permite editar retardo y color de cada segmento. |
| CI | Módulo reutilizable con entradas, salidas y tiempo de respuesta configurados por combinación. |

Las puertas lógicas admiten como mínimo dos entradas, excepto NOT, que tiene una. Los controles de edición muestran las cantidades de puertos permitidas por cada tipo. Al hacer doble clic en una etiqueta de componente, el tablero lo centra y selecciona para que puedas localizarlo.

### Simulación y tabla de verdad

Los cambios se propagan por los cables y pueden atravesar componentes con retardo. Los interruptores mantienen el estado; los botones momentáneos vuelven a apagarse al soltarlos.

La tabla de verdad del circuito completo utiliza interruptores y botones conectados como entradas, y bombillas y displays conectados como salidas. Permite asignar manualmente un número único a cada columna. Las combinaciones avanzan en orden binario; por ejemplo, con tres entradas: 000, 001, 010, 011, 100, 101, 110, 111.

- Las bombillas producen 0 o 1.
- Los displays producen los índices de segmentos encendidos (por ejemplo, 012 o 031); un guion indica que no hay segmentos activos.
- Cada combinación incluye el tiempo de respuesta estimado en ms. El diálogo también informa cuánto tardó el cálculo completo.
- Se avisa de entradas, segmentos o salidas sin conexión antes de continuar; se excluyen o se consideran apagados según indique el aviso.
- No hay un límite fijo de entradas. Si hay más de 12, se muestra la cantidad de combinaciones (2ⁿ) y se avisa de que el cálculo puede tardar y consumir memoria; al aceptar, se genera la tabla.
- La tabla permite buscar filas, cambiar el ancho de las columnas y exportar.

El comando está en Widgets → Calcular tabla de verdad (Ctrl+Mayús+F).

### CI y biblioteca

Selecciona componentes y usa Crear CI para generar un módulo reutilizable. El archivo registra explícitamente cada combinación de entradas, sus salidas y el tiempo de respuesta; no guarda las salidas como un entero empaquetado. El retardo añadido al CI se suma al de cada respuesta.

La pestaña CI agrupa los módulos en:

- **Biblioteca**: archivos en user/Biblioteca, ubicación sugerida al guardar.
- **Subido**: módulos importados explícitamente.
- **Cargado**: módulos presentes en el proyecto abierto que no están en las otras secciones.

Los números de puerto empiezan en cero, no se repiten en entradas o salidas y ordenan los conectores de menor a mayor. Al editar un CI guardado, Guardar CI actualiza el archivo .dmodule.

### Proyectos y exportación

- Guarda y abre proyectos .dalogic (JSON); también se admiten archivos JSON compatibles.
- Se conservan componentes, posiciones, estados, propiedades, cables, colores, nexos, puentes, extremos y rótulos de sección.
- Los módulos .dmodule se guardan como JSON. Se admiten las versiones 1 y 2; los módulos antiguos se normalizan al cargarlos.
- Exporta el circuito como PNG con fondo transparente, PDF o SVG.
- Exporta tablas como PNG, PDF, SVG, XLSX o CSV separado por punto y coma.
- Los proyectos recientes se guardan en user/recent.json y preferencias como el tema y el idioma en user/config.json.

## Instalación y ejecución

### Requisitos

- Python 3.10 o posterior.
- PySide6 6.5 o posterior de la serie 6.
- Windows, macOS o Linux con entorno gráfico compatible con Qt.

No se necesita otra biblioteca para Excel: la exportación XLSX se genera desde el programa.

En la raíz del proyecto, crea un entorno virtual e instala requirements.txt.

**Windows PowerShell**

~~~powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
~~~

**macOS o Linux**

~~~sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
~~~

Inicia desde la raíz con el entorno activado:

~~~sh
python main.py
~~~

En Windows también puedes usar py main.py.

## Uso rápido

1. Añade componentes desde Básico; usa la pestaña CI para insertar módulos reutilizables.
2. Arrástralos al tablero y conecta salidas con entradas. Inicia el cable en un puerto y termínalo en un puerto, nexo o extremo válido.
3. Haz doble clic en interruptores y mantén pulsados los botones momentáneos.
4. Usa los editores contextuales para configurar retardos, colores, cantidad de puertos o numeración, según el componente.
5. Guarda el proyecto en .dalogic. Para reutilizar una selección entre proyectos, créala como CI.
6. Calcula la tabla desde Widgets → Calcular tabla de verdad. Exporta el circuito desde Archivo → Exportar y la tabla desde su ventana.

## Deshacer y rehacer

Ctrl+Z deshace el último cambio del circuito y Ctrl+Y lo rehace. El historial incluye los componentes, conexiones, posiciones, nexos, propiedades y estados guardados por el proyecto, y conserva hasta 100 pasos. Abrir o crear un proyecto inicia un historial nuevo. Deshacer no escribe el archivo del proyecto; guarda los cambios cuando vuelvas a usar Guardar.

## Carpetas predeterminadas

- Los proyectos nuevos se abren y guardan inicialmente en Proyectos.
- Las exportaciones de circuitos y tablas proponen la carpeta Exports.
- Los circuitos integrados se guardan en user/Biblioteca. Si había una biblioteca anterior llamada user/Biblioteca de CI, sus módulos se trasladan a la carpeta nueva; si un nombre ya existe, se conserva el archivo anterior con un sufijo.

## Idiomas

La aplicación ofrece un selector de idioma en la barra superior. Los catálogos están en user/Idiomas y se cargan desde archivos JSON. En el primer inicio se amplía es.json con las claves de texto de la interfaz.

Para añadir un idioma, copia user/Idiomas/es.json a un archivo nuevo, por ejemplo en.json. Cambia el nombre mostrado y el código, y sustituye los valores de translations por las traducciones correspondientes. Las claves son las frases originales en español; cualquier frase que no traduzcas seguirá apareciendo en español. Guarda el archivo y reinicia DaLogic para que aparezca en el selector.

El formato usa los campos code, name y translations. Por ejemplo, una entrada del catálogo puede ser:

~~~json
{
  "code": "en",
  "name": "English",
  "translations": {
    "Archivo": "File"
  }
}
~~~

## Atajos

| Acción | Atajo |
| --- | --- |
| Nuevo / abrir | Ctrl+N / Ctrl+O |
| Guardar / guardar como | Ctrl+G / Ctrl+Mayús+S |
| Exportar circuito | Ctrl+P |
| Copiar / cortar / pegar | Ctrl+C / Ctrl+X / Ctrl+V |
| Eliminar selección | Supr |
| Calcular tabla de verdad | Ctrl+Mayús+F |
| Deshacer / rehacer | Ctrl+Z / Ctrl+Y |
| Tema claro/oscuro | Ctrl+Mayús+T |
| Ajustar vista al circuito | Ctrl+0 |
| Cancelar trazado de cable | Esc |
| Zoom / desplazar tablero | Rueda / botón central y arrastre |

## Archivos principales

| Ruta | Función |
| --- | --- |
| main.py | Arranque, ventana, proyectos, CI, tabla de verdad y exportación. |
| board_view.py | Tablero, conexiones, nexos, interacción y propagación de señales. |
| project_io.py | Lectura y escritura de .dalogic y .dmodule. |
| Proyectos/ | Carpeta predeterminada de apertura y guardado de proyectos. |
| Exports/ | Carpeta inicial para exportar circuitos y tablas. |
| widgets/widgets.py | Lógica de puertas, fuentes, retardos, salidas y CI. |
| widgets/graphics.py | Gráficos, conectores, cables y editores. |
| resources/ui/ | Fuentes de las interfaces Qt. |
| resources/compiled/ | Interfaces compiladas que usa el programa. |
| resources/styles/ | Temas claro y oscuro. |
| user/Idiomas/ | Catálogos de idioma en formato JSON (incluye es.json). |
| resources/app_icon.py | Icono de aplicación integrado en código. |
| user/ | Preferencias, recientes y Biblioteca. |

Para regenerar interfaces o recursos Qt durante el desarrollo, scripts/build.py contiene la rutina de conversión y espera pyside6-uic y pyside6-rcc en la ruta configurada por el script.

## Solución de problemas

- **Error de Qt al iniciar**: instala requirements.txt en el mismo Python con el que ejecutas main.py y utiliza un escritorio compatible con Qt.
- **CI ausente**: verifica que sea un JSON válido .dmodule; archivos no reconocidos o dañados se omiten.
- **Tabla no calculable**: comprueba que haya una bombilla o display conectado y revisa el aviso de entradas sin conexión. Con muchas entradas, confirma el aviso para iniciar el cálculo; la cantidad de filas crece exponencialmente.
- **No se puede guardar en la biblioteca**: comprueba permisos de escritura en user/Biblioteca.

## Licencia y créditos

DaLogic se distribuye bajo Apache License 2.0. Consulta [LICENSE](LICENSE) para conocer los términos completos. El proyecto fue creado por David Lopez Borrego; [NOTICE](NOTICE) contiene la atribución y el enlace al repositorio. Si redistribuyes el programa, especialmente como aplicación gráfica o binario, se recomienda conservar una atribución visible en Acerca de o Créditos e incluir el contenido de NOTICE. Es una recomendación del proyecto, no una condición adicional de la licencia.
