import os
from dotenv import load_dotenv
from google import genai


load_dotenv()


def create_agent():
    api_key = os.getenv("ANTIGRAVITY_API_KEY")

    if not api_key:
        raise RuntimeError(
            "ANTIGRAVITY_API_KEY no está configurada en el archivo .env"
        )

    client = genai.Client(api_key=api_key)

    return client


def run_agent(prompt: str):
    client = create_agent()

    interaction = client.interactions.create(
        agent="antigravity-preview-05-2026",
        input=prompt,
        environment="remote",
        agent_config={
            "type": "antigravity",
            "model": "gemini-3.6-flash",
            "max_total_tokens": 50000,
        },
    )

    return interaction


if __name__ == "__main__":

    prompt = """
    Eres el agente principal del proyecto CargoManifest-Extractor.

    Tu objetivo es ayudar a construir un sistema robusto para analizar
    manifiestos de carga portuaria en PDF.

    El proyecto maneja actualmente dos formatos:

    1. PDF cuyo nombre contiene "todo":
       corresponde a República Dominicana.

    2. PDF cuyo nombre contiene "all":
       corresponde a Puerto Rico.

    IMPORTANTE:
    - No debes confiar únicamente en el nombre del archivo.
    - Debes analizar la estructura interna del PDF.
    - No debes asumir que ambos formatos tienen las mismas columnas.
    - No debes modificar información original.
    - Si una estructura no puede identificarse con suficiente confianza,
      debes reportarla como desconocida.
    - El objetivo final es extraer todos los registros del manifiesto
      de manera estructurada.

    Por ahora realiza solamente una prueba de conexión.

    Responde indicando:
    - que eres el agente Antigravity;
    - que la conexión fue exitosa;
    - qué capacidades tienes disponibles;
    - y que estás listo para analizar el proyecto.
    """

    result = run_agent(prompt)

    print("=" * 80)
    print("ANTIGRAVITY AGENT")
    print("=" * 80)
    print()
    print("Status:", result.status)
    print()
    print(result.output_text)
