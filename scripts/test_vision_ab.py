"""A/B test: compare Sonnet vs Haiku vision on the same image.

Usage:
  python scripts/test_vision_ab.py <image_path> [image_path2 ...]

Requires ANTHROPIC_API_KEY env var.
"""

import asyncio
import base64
import io
import sys
import time
import os

# Fix Windows cp1252 encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from anthropic import AsyncAnthropic

SONNET = "claude-sonnet-4-6"
HAIKU = "claude-haiku-4-5-20251001"

VISION_PROMPT = """Eres un experto en trade marketing y retail de productos de cuidado de la ropa (detergentes, suavizantes, quitamanchas, blanqueadores, etc).

Al analizar cada imagen de punto de venta, identifica y describe con precision:

1. PRODUCTOS VISIBLES: Marca, submarca, formato (polvo, liquido, pods, barra), tamano/presentacion, precio visible
2. SHARE OF SHELF: Estimacion del espacio que ocupa cada marca en la gondola (% aproximado)
3. POSICION EN GONDOLA: Nivel (ojos, manos, piso), ubicacion (punta, centro), facing
4. PROMOCIONES: Descuentos, ofertas, packs especiales, material POP, comunicacion en gondola
5. ESTADO DEL ANAQUEL: Agotados visibles (huecos), productos mal ubicados, desorden, suciedad
6. INNOVACION: Productos nuevos, formatos diferentes, tendencias (eco, concentrado, premium, refill)
7. EXHIBICIONES ESPECIALES: Cabeceras, islas, cross-merchandising (ej: detergente + suavizante juntos)
8. COMPETENCIA: Todas las marcas visibles y su posicionamiento relativo
9. COMUNICACION: Mensajes en packaging, claims (biodegradable, hipoalergenico, rinde mas), idioma

Se muy especifico con marcas y precios. Si un precio no es legible, indicalo. Si una marca no es reconocible, describela."""


def detect_media_type(data: bytes) -> str:
    if data[:2] == b"\xff\xd8":
        return "image/jpeg"
    if data[:4] == b"\x89PNG":
        return "image/png"
    if data[:4] == b"RIFF":
        return "image/webp"
    return "image/jpeg"


async def analyze(client: AsyncAnthropic, model: str, image_b64: str, media_type: str) -> dict:
    start = time.time()
    message = await client.messages.create(
        model=model,
        max_tokens=1024,
        system=VISION_PROMPT,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_b64}},
                {"type": "text", "text": "Analiza esta imagen capturada durante una visita de campo."},
            ],
        }],
    )
    elapsed = time.time() - start
    text = message.content[0].text.strip()
    return {
        "model": model,
        "text": text,
        "chars": len(text),
        "input_tokens": message.usage.input_tokens,
        "output_tokens": message.usage.output_tokens,
        "elapsed_s": round(elapsed, 1),
        "cost_usd": _estimate_cost(model, message.usage.input_tokens, message.usage.output_tokens),
    }


def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    if "sonnet" in model:
        return (input_tokens * 3 / 1_000_000) + (output_tokens * 15 / 1_000_000)
    else:  # haiku
        return (input_tokens * 0.80 / 1_000_000) + (output_tokens * 4 / 1_000_000)


async def test_image(client: AsyncAnthropic, image_path: str):
    with open(image_path, "rb") as f:
        image_bytes = f.read()

    media_type = detect_media_type(image_bytes)
    image_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
    size_kb = len(image_bytes) / 1024

    print(f"\n{'='*80}")
    print(f"IMAGE: {os.path.basename(image_path)} ({size_kb:.0f} KB, {media_type})")
    print(f"{'='*80}")

    # Run both in parallel
    sonnet_task = analyze(client, SONNET, image_b64, media_type)
    haiku_task = analyze(client, HAIKU, image_b64, media_type)
    sonnet, haiku = await asyncio.gather(sonnet_task, haiku_task)

    for result in [sonnet, haiku]:
        label = "SONNET" if "sonnet" in result["model"] else "HAIKU"
        print(f"\n--- {label} ---")
        print(f"Chars: {result['chars']} | Tokens: {result['input_tokens']}in/{result['output_tokens']}out | Time: {result['elapsed_s']}s | Cost: ${result['cost_usd']:.4f}")
        print(f"\n{result['text']}")

    # Summary comparison
    print(f"\n--- COMPARISON ---")
    print(f"Sonnet: {sonnet['chars']} chars, ${sonnet['cost_usd']:.4f}, {sonnet['elapsed_s']}s")
    print(f"Haiku:  {haiku['chars']} chars, ${haiku['cost_usd']:.4f}, {haiku['elapsed_s']}s")
    ratio = sonnet['chars'] / max(haiku['chars'], 1)
    savings = (1 - haiku['cost_usd'] / max(sonnet['cost_usd'], 0.0001)) * 100
    print(f"Sonnet es {ratio:.1f}x mas largo. Haiku ahorra {savings:.0f}% en costo.")


async def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_vision_ab.py <image_path> [image_path2 ...]")
        sys.exit(1)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        # Try loading from .env
        env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    if line.startswith("ANTHROPIC_API_KEY="):
                        api_key = line.strip().split("=", 1)[1]
                        break
    if not api_key:
        print("ERROR: Set ANTHROPIC_API_KEY environment variable")
        sys.exit(1)

    client = AsyncAnthropic(api_key=api_key, timeout=90.0)

    for path in sys.argv[1:]:
        if not os.path.exists(path):
            print(f"File not found: {path}")
            continue
        await test_image(client, path)

    print(f"\n{'='*80}")
    print("DONE. Compare the outputs above to decide if Haiku is sufficient for your use case.")


if __name__ == "__main__":
    asyncio.run(main())
