# Manual del DaLogic 1.2.0

El DaLogic és un editor i simulador de circuits lògics digitals per a l'escriptori. Crea un circuit, connecta'n els ports i observa els senyals. L'edició i la simulació funcionen sense connexió. Visualitza → Idioma permet triar català, espanyol o anglès i conserva la preferència per al proper inici.

## Col·locació i connexions

Tria un component a la paleta esquerra i fes clic al tauler per col·locar-lo. També pots arrossegar un botó fins al tauler. Retorn col·loca la previsualització al centre visible; Esc o clic dret cancel·la la col·locació. Un doble clic commuta un interruptor. Mantén premut un botó per activar-ne la sortida.

Fes clic en un port i després en un altre per connectar-los. Un clic en buit mentre traces crea un colze; un doble clic acaba el cable amb un extrem lliure. Esc cancel·la el traçat. Un doble clic en un nexe alterna els ponts. El primer clic en un cable el selecciona i el segon crea un node. El clic dret en un cable ofereix Crea un node, Canvia el color i Elimina. En components ofereix Elimina i Edita; en mòduls, Elimina i Canvia l’aspecte. Els colors i les cantonades del mòdul es desen al projecte.

Utilitza la roda per al zoom i el botó central per desplaçar la vista. Selecciona diversos components per moure'ls junts. R gira 90 graus i H reflecteix horitzontalment. Supr elimina la selecció. Visualitza inclou quadrícula, ajust i cables en angle recte. Edita inclou alineació, distribució i límit de l'historial.

## Projectes i historial

Fitxer → Nou comprova els canvis pendents abans de buidar el projecte. Obre carrega un projecte `.dalogic`. Desa i Anomena i desa escriuen el fitxer de manera atòmica. Desfés i Refés restauren les edicions, les connexions i els elements visuals. La recuperació automàtica desa els canvis pendents cada minut; després d'un tancament inesperat, el següent inici normal ofereix restaurar-los.

L'aplicació instal·lada desa les preferències, la recuperació, els idiomes i la biblioteca al perfil de Windows. Els projectes i les exportacions es proposen a Documents/DaLogic. La desinstal·lació conserva les dades personals. `DALOGIC_DATA_DIR` permet triar una altra carpeta. Dues instàncies no poden utilitzar la mateixa carpeta de dades alhora.

## Mòduls reutilitzables

Selecciona un grup i utilitza Widgets → Crea un CI. Escriu un nom i tria una carpeta. Els mòduls combinacionals desen una taula de veritat; els seqüencials conserven la xarxa interna i un estat independent per instància. S'admeten els formats `.dmodule` 1, 1.1, 1.2 i 1.3. El format 1.3 inclou memòria nativa i busos. La numeració del format és independent de la versió del programa.

Cerca per nom a la pestanya CI i obre les carpetes. Prem un CI per col·locar-lo. El clic dret en un mòdul de la biblioteca ofereix Canvia el nom: actualitza el nom visible i el fitxer `.dmodule`, juntament amb les instàncies carregades que hi fan referència. Un nom duplicat no substitueix un altre fitxer. Mou a una carpeta permet organitzar la biblioteca.

Per canviar només una instància del circuit, obre'n les propietats, edita Nom del mòdul i prem Desa. El projecte conserva aquest nom. Desa el CI també escriu la definició del mòdul. Els noms personals, els identificadors dels ports i les anotacions no es tradueixen en canviar d'idioma.

## Simulació i sondes

F6 pausa o reprèn els rellotges. F8 pausa tota la simulació i conserva els esdeveniments pendents. F10 aplica el lot següent; si no n'hi ha, avança els rellotges. Selecciona un component amb entrades i prem F9 per afegir una marca vermella d'aturada. Quan canvia una entrada, es calcula el lot actual i s'atura la simulació abans dels esdeveniments següents. La marca es torna taronja i la vista mostra el component. F10 aplica el lot següent; F8 continua. Selecciona els components marcats i prem F9 per treure'n les marques. Una selecció mixta es marca conjuntament. Els interruptors i rellotges no tenen entrades i no es poden marcar. Els punts d'aturada són temporals i no es desen al circuit. F7 comprova entrades lliures, fonts absents, amplades incompatibles, conflictes tri-state i senyals X. Un doble clic en una incidència localitza l'element.

Ctrl+clic en un cable o port afegeix una sonda. El panell Sondes mostra les ones, permet eliminar senyals, netejar l'historial i exportar CSV o VCD. La capacitat es configura entre 256 i 100.000 canvis per senyal, amb 10.000 per defecte. Ampliar-la no recupera mostres descartades. Exporta la captura abans de tancar.

## Taules i exportació

Ctrl+Maj+F calcula una taula de veritat combinacional. Assigna ordres únics a les columnes; el doble clic en una etiqueta localitza el component. El límit és de 16 bits d'entrada, o 65.536 combinacions. Els càlculs grans mostren un progrés cancel·lable. Els circuits amb memòria o realimentació s'observen amb simulació temporal.

El filtre de taula cerca valors de les cel·les. Exporta a PNG, PDF, SVG, XLSX o CSV. Ctrl+P exporta el circuit a PNG, PDF o SVG. PNG limita la resolució dels circuits molt grans; PDF i SVG conserven vectors. Els elements visuals afegeixen text, quadrats, cercles i plans amb nom sense modificar els senyals.

## Dreceres

| Acció | Drecera |
| --- | --- |
| Nou / Obre | Ctrl+N / Ctrl+O |
| Desa / Anomena i desa | Ctrl+S o Ctrl+G / Ctrl+Maj+S |
| Copia / Retalla / Enganxa / Duplica | Ctrl+C / Ctrl+X / Ctrl+V / Ctrl+D |
| Desfés / Refés | Ctrl+Z / Ctrl+Y |
| Ajusta / Apropa / Allunya | Ctrl+0 / Ctrl++ / Ctrl+- |
| Alinea / Distribueix | Ctrl+Maj+A / Ctrl+Maj+D |
| Tema / Manual | Ctrl+Maj+T / F1 |
| Comprova / Pausa els rellotges | F7 / F6 |
| Pausa / Punt d'aturada / Pas | F8 / F9 / F10 |

## Actualitzacions i autoria

El DaLogic pot consultar l'última versió pública de GitHub amb HTTPS. `--no-update-check` desactiva aquesta petició. La consulta no envia projectes ni registres. Els errors s'anoten a `dalogic.log` amb rotació. La finestra de crèdits conserva l'atribució a David Lopez Borrego. El projecte té llicència Apache 2.0 i les dependències mantenen els seus avisos.


A Ajuda → Avisa de les actualitzacions pots activar o desactivar la consulta i els avisos de versions noves. La preferència es desa. Activar-la consulta la versió immediatament. Desactivar-la també suprimeix el resultat d'una consulta en curs.

El menú Simulació agrupa les pauses, els passos, els punts d’aturada i les sondes. La barra d’accions es distribueix en files quan es redueix la finestra, i la paleta visual roman dins de l’aplicació.
