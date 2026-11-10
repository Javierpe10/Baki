"""Consola local para gestionar secretos. Los valores se piden con entrada oculta.

Uso, desde la carpeta backend:
    ..\\.venv\\Scripts\\python.exe -m app.secrets_cli guardar baki:google:oauth_client
    ..\\.venv\\Scripts\\python.exe -m app.secrets_cli listar
    ..\\.venv\\Scripts\\python.exe -m app.secrets_cli borrar baki:google:oauth_client
    ..\\.venv\\Scripts\\python.exe -m app.secrets_cli autorizar-google C:\\ruta\\client_secret.json
    ..\\.venv\\Scripts\\python.exe -m app.secrets_cli conectar-ghl
    ..\\.venv\\Scripts\\python.exe -m app.secrets_cli conectar-elevenlabs
"""

import argparse
import getpass
import sys

from app.secrets_store import SecretStoreUnavailable, tienda_por_defecto


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="secrets_cli")
    subordenes = parser.add_subparsers(dest="orden", required=True)

    guardar = subordenes.add_parser("guardar")
    guardar.add_argument("nombre")

    borrar = subordenes.add_parser("borrar")
    borrar.add_argument("nombre")

    subordenes.add_parser("listar")

    google = subordenes.add_parser("autorizar-google")
    google.add_argument("json_cliente", help="Ruta del client_secret_XXX.json descargado de Google Cloud")

    subordenes.add_parser("conectar-ghl")
    subordenes.add_parser("conectar-elevenlabs")
    subordenes.add_parser("conectar-n8n")

    args = parser.parse_args(argv)

    try:
        tienda = tienda_por_defecto()

        if args.orden == "guardar":
            valor = getpass.getpass("Valor (no se muestra): ")
            tienda.guardar(args.nombre, valor)
            print(f"Guardado: {args.nombre}")

        elif args.orden == "borrar":
            tienda.borrar(args.nombre)
            print(f"Borrado: {args.nombre}")

        elif args.orden == "autorizar-google":
            from app.integraciones.google_auth import autorizar_desde_json

            autorizar_desde_json(args.json_cliente)
            print("Google conectado. Ya puedes borrar el archivo JSON descargado.")

        elif args.orden == "conectar-ghl":
            from app.agente import config as cfg

            token = getpass.getpass("Private Integration Token de GoHighLevel (no se muestra): ").strip()
            location = input("Location ID (Sub-cuenta > Settings > Business Profile): ").strip()
            if not token or not location:
                raise ValueError("Faltan datos.")
            tienda.guardar("baki:ghl:token", token)
            cfg.guardar({"ghl_location_id": location})
            print("GoHighLevel conectado.")

        elif args.orden == "conectar-elevenlabs":
            from app.agente import config as cfg

            clave = getpass.getpass("API key de ElevenLabs (no se muestra): ").strip()
            if not clave:
                raise ValueError("Clave vacía.")
            tienda.guardar("baki:elevenlabs:api_key", clave)
            voz = input("Voice ID (Enter para la voz por defecto): ").strip()
            if voz:
                cfg.guardar({"elevenlabs_voz_id": voz})
            print("ElevenLabs conectado.")

        elif args.orden == "conectar-n8n":
            from app.agente import config as cfg

            url = input("URL de tu n8n (ej. https://tuempresa.app.n8n.cloud o http://localhost:5678): ").strip().rstrip("/")
            if not url.startswith(("http://", "https://")):
                raise ValueError("La URL debe empezar por http:// o https://")
            clave = getpass.getpass("API key de n8n (no se muestra): ").strip()
            if not clave:
                raise ValueError("Clave vacía.")
            tienda.guardar("baki:n8n:api_key", clave)
            cfg.guardar({"n8n_url": url})
            print("n8n conectado.")

        else:
            for nombre in tienda.listar():
                print(nombre)

    except (ValueError, KeyError, SecretStoreUnavailable, RuntimeError, FileNotFoundError) as error:
        mensaje = error.args[0] if error.args else str(error)
        print(f"Error: {mensaje}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
