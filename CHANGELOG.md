# Changelog

Todos los cambios descritos en esta sección están previstos para la futura versión **1.1.0**. Esta versión todavía no ha sido publicada y se encuentra en fase de planificación. Por tanto, este documento debe considerarse una **guía orientativa y no definitiva** de las funcionalidades previstas para la próxima versión.

## [1.1.0] — Próxima versión (sin publicar)

### Relojes y circuitos con memoria

* Se añadirá el componente **Reloj**, capaz de generar una señal periódica con un intervalo configurable en milisegundos.

* El ciclo de los relojes se sincronizará al abrir o reconstruir un proyecto.

* Se admitirán la **realimentación** y las **conexiones recursivas** en circuitos secuenciales, permitiendo conservar durante la simulación el estado de los elementos y la memoria de estados anteriores.

* Los circuitos que contengan realimentación podrán convertirse en **CI secuenciales**. El archivo `.dmodule` conservará la red interna del circuito, sus conexiones y su estado inicial, en lugar de representarlo mediante una tabla combinacional.

* Cada CI secuencial conservará su propio estado durante la simulación. Los proyectos también podrán guardar y restaurar dicho estado al volver a abrirse.

* La tabla de verdad indicará cuándo un circuito contiene realimentación o depende de estados anteriores. En estos casos, no se generará una tabla de verdad combinacional.

### Formatos de CI

* Se eliminará la compatibilidad con el formato `.dmodule` heredado y con su lector de pruebas correspondiente a versiones anteriores a la primera versión publicada del repositorio (**legacy**). Estos archivos `.dmodule` indicaban `"version": 1`, pero almacenaban `truth_table` como una lista plana de enteros (por ejemplo, `[0, 1, 1, 2, 1, 2, 2, 3]`). Aunque declarasen la versión `1`, dicha estructura no correspondía al **formato publicado 1** y dejará de ser compatible.

* Se mantendrá la compatibilidad con el **formato publicado 1**, introducido en **v1.0.0**, que utiliza filas estructuradas con información de entradas, salidas y tiempo.

* Los CI secuenciales que almacenen el circuito completo pasarán a utilizar el **formato 1.1**. La versión v1.0.0 no podrá leer estos CI secuenciales, mientras que DaLogic 1.1 podrá cargarlos y conservar su estado.

### Idiomas y documentación

* Se limitará la extracción de cadenas de traducción al texto visible de la interfaz. Los identificadores, nombres de campos, selectores CSS y otros literales internos dejarán de incorporarse a los archivos JSON de idioma.

* Se actualizarán los catálogos `user/Idiomas/*.json` para que contengan únicamente cadenas de texto reconocidas como contenido traducible de la interfaz.

* Se actualizará el README con la documentación correspondiente a los relojes, los circuitos con memoria y los CI secuenciales.

### Estado del lanzamiento

La versión **1.1.0** es una versión futura y permanecerá sin publicar hasta que finalice su implementación. Las funcionalidades y cambios descritos en este documento representan el **alcance previsto** para dicha versión y están sujetos a modificaciones durante su desarrollo.

Por tanto, este changelog **no debe interpretarse como una lista de funcionalidades ya disponibles ni como una especificación definitiva** de la versión 1.1.0.
