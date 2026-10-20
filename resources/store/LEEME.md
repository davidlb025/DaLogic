# Envío de DaLogic a Microsoft Store

Esta carpeta contiene el paquete actual y los materiales de su ficha. No se ha enviado ni publicado nada en Partner Center. Solo el archivo `.msix` se carga en **Paquetes**; las capturas, textos y logo se añaden a sus campos correspondientes. El ZIP de entrega sirve para transportar estos archivos y no se sube como paquete.

## Paquete e identidad

El archivo `MSIX-INFO.json` contiene el nombre, versión, identidad, arquitectura y SHA-256 leídos del MSIX. `AppxManifest.xml` es una copia literal del manifiesto interno. La identidad configurada es la facilitada por el propietario:

- Package/Identity/Name: `davidlb025.DaLogic`
- Package/Identity/Publisher: `CN=EEE5E14A-E1FC-4512-A2D0-29DA37D920DF`
- Package/Properties/PublisherDisplayName: `davidlb025`

Comprueba esos tres valores en **Administración de productos → Identidad de la aplicación**. La comparación local no implica haber consultado tu cuenta. Esta entrega es para PC Windows x64; no declares compatibilidad ARM64 nativa, x86, Xbox ni móviles. La versión mínima de Windows figura en el manifiesto.

El MSIX se entrega sin firma para Partner Center. Microsoft lo firma durante la publicación. No necesitas enviar certificados ni claves. Para instalar este archivo directamente fuera de Store se necesita una firma de confianza; esta preparación no instala certificados ni cambia las opciones de seguridad de Windows.

## Pasos en Partner Center

1. Abre el producto MSIX **DaLogic** y crea un envío. Carga el `.msix` en **Paquetes** y espera su validación. No uses el flujo de una aplicación MSI/EXE para esta entrega.
2. En **Propiedades**, la categoría propuesta es **Educación**. DaLogic no solicita ni recopila datos personales para usar el editor o la simulación. Los circuitos permanecen locales. La consulta opcional de versiones contacta con GitHub, que recibe la IP y los datos técnicos de esa conexión, tal como explica la política. Revisa los requisitos detectados y los datos de soporte de `FICHAS.json`.
3. La política está disponible en `Privacidad/index.html` y `PRIVACIDAD.md`. Si añades su enlace a la ficha o Partner Center lo exige, publícala en una URL HTTPS accesible sin iniciar sesión e introduce esa URL en el campo de privacidad. `FICHAS.json` deja ese dato vacío hasta que exista una dirección comprobada. Al declarar que la aplicación no recopila información personal, Microsoft puede considerar el enlace opcional o exigirlo por las capacidades del paquete. No introduzcas una ruta de este equipo ni una URL inventada.
4. Completa precios, mercados y disponibilidad según tu decisión. Los textos describen la aplicación sin anuncios, compras integradas ni suscripciones, pero no fijan su precio en Store.
5. Completa el cuestionario de clasificación por edades (IARC). La aplicación es educativa, sin chat, apuestas, compras ni contenido de usuarios en línea. La clasificación la calcula el cuestionario; esta carpeta no atribuye una edad certificada.
6. Añade fichas para **es-ES**, **ca-ES** y **en-US**. En `Fichas/IDIOMA/` encontrarás textos listos para copiar, cuatro capturas de 1600 × 900 y sus pies en `capturas.json`. Usa `StoreLogo-300x300.png` como icono 1:1 de la ficha.
7. Como este es el primer envío, deja **Novedades de esta versión** vacío. Los módulos y carpetas conservan sus nombres propios también en las capturas de otros idiomas.
8. En **Opciones de envío**, copia `CERTIFICACION.txt`. Si se solicita la justificación del permiso restringido, utiliza `PERMISO-runFullTrust.txt`.
9. Revisa los avisos de validación, la vista previa de cada ficha y las decisiones de publicación. Después envía a certificación desde tu cuenta.

`FICHAS.json` es una referencia local, no una plantilla de importación ni una petición a la API. Si quieres usar CSV, exporta primero la plantilla correspondiente a tu producto desde Partner Center.

## Verificación y límites

`VERIFICACION.json` registra las comprobaciones realizadas sobre este archivo concreto. `SHA256SUMS-STORE.txt` permite comprobar todos los materiales de esta carpeta. El `.msix.sha256` permite comprobar solo el paquete; los cuatro hashes de la distribución completa siguen en `../SHA256SUMS.txt`.

La estructura del MSIX, sus recursos, idioma, identidad, contenido y correspondencia con `Normal/` se comprueban localmente. Las capturas proceden de la interfaz actual renderizada por Qt; no son maquetas. No se han certificado requisitos de hardware, accesibilidad completa ni ejecución en todas las versiones de Windows.

La prueba completa del Windows App Certification Kit (WACK) y la instalación bajo identidad Store no se han realizado. Para ello usa un equipo o una máquina virtual de pruebas con una copia instalada mediante un certificado de desarrollo propio o una distribución privada de Store. Puedes ejecutar WACK sobre el nombre completo del paquete instalado y guardar su informe antes del envío. No confundas este informe local con la certificación de Microsoft.

## Documentación de Microsoft consultada

- [Requisitos de paquetes y firma](https://learn.microsoft.com/en-us/windows/apps/publish/publish-your-app/msix/app-package-requirements)
- [Capturas e icono de la ficha](https://learn.microsoft.com/en-us/windows/apps/publish/publish-your-app/msix/screenshots-and-images)
- [Textos e idiomas de la ficha](https://learn.microsoft.com/en-us/windows/apps/publish/publish-your-app/msix/add-and-edit-store-listing-info)
- [Propiedades y privacidad](https://learn.microsoft.com/en-us/windows/apps/publish/publish-your-app/enter-app-properties?pivots=store-installer-msix)
- [Windows App Certification Kit](https://learn.microsoft.com/en-us/windows/uwp/debug-test-perf/windows-app-certification-kit)
