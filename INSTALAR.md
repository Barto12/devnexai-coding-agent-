# Cómo crear el instalador de DevNexAI (app de escritorio)

DevNexAI ahora tiene **dos formas de uso**:
- **CLI** (terminal): `py -m devnexai`
- **App de escritorio** (ventana gráfica): el ejecutable `DevNexAI.exe`

Esta guía es para generar el **instalador tipo setup** que crea el icono en
el escritorio y el menú inicio, como cualquier programa de Windows.

## Paso 1 — Generar el ejecutable de la app

Con el proyecto descomprimido, en la carpeta donde está `build_exe.bat`:

```cmd
build_exe.bat
```

Esto crea `dist\DevNexAI.exe` (la app en ventana, sin consola negra).
Puedes probarla ya con doble clic.

## Paso 2 — Instalar Inno Setup (una sola vez)

Descarga e instala Inno Setup (gratis):
https://jrsoftware.org/isdl.php

## Paso 3 — Compilar el instalador

1. Abre el archivo `installer.iss` con Inno Setup (doble clic).
2. Pulsa el botón **Compile** (o menú Build > Compile).
3. Se genera el instalador en: `Output\DevNexAI-Setup.exe`

## Paso 4 — Distribuir

`DevNexAI-Setup.exe` es el archivo que el usuario descarga y ejecuta.
Al instalarlo:
- Crea acceso directo en el **escritorio** (con icono).
- Lo agrega al **menú inicio**.
- Permite desinstalarlo desde "Agregar o quitar programas".

El usuario NO necesita tener Python instalado: el .exe es autónomo.

## Configurar la app

Al abrir DevNexAI, pulsa **⚙ Proveedores** para conectar una API key
(Anthropic, OpenAI, Groq, etc.) o un modelo local (Ollama / LM Studio),
todo con clics. Luego elige la carpeta del proyecto con **📁 Carpeta** y
empieza a chatear con el agente.
