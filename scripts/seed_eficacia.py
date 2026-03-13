"""Seed Eficacia implementation with visit type schemas.

Usage: SUPABASE_SERVICE_ROLE_KEY=<key> python scripts/seed_eficacia.py
"""
import json
import os
import sys
import urllib.request

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://sglvhzmwfzetyrhwouiw.supabase.co")
KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
if not KEY:
    print("ERROR: Set SUPABASE_SERVICE_ROLE_KEY env var before running this script.")
    sys.exit(1)


def sb_post(table, data):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{table}",
        data=json.dumps(data).encode(),
        method="POST",
        headers={
            "apikey": KEY,
            "Authorization": f"Bearer {KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        },
    )
    try:
        resp = urllib.request.urlopen(req)
        return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"Error {e.code}: {e.read().decode()[:300]}")
        return None


# Schema 1: Supermarket Visit
supermarket_schema = {
    "implementation": "eficacia",
    "visit_type": "supermarket_visit",
    "display_name": "Visita a Supermercado",
    "description": "Auditoria de punto de venta en cadena de supermercados",
    "primary_media": ["image", "voice"],
    "categories": [
        {
            "id": "share_of_shelf",
            "label": "Share of Shelf",
            "description": "Participacion visual en gondola por marca",
            "fields": [
                {"id": "categoria_producto", "type": "string", "label": "Categoria (cereales, bebidas, snacks)"},
                {"id": "marca", "type": "string", "label": "Marca"},
                {"id": "facings", "type": "number", "label": "Numero de facings"},
                {"id": "share_porcentaje", "type": "number", "label": "Share estimado (%)"},
                {"id": "ubicacion_gondola", "type": "string", "label": "Ubicacion (ojos/arriba/abajo)"},
                {"id": "estado_surtido", "type": "string", "label": "Estado (lleno/vacios/desordenado)"},
            ],
            "is_array": True,
            "applies_to": ["image"],
        },
        {
            "id": "precios",
            "label": "Precios capturados",
            "description": "Precios visibles en etiquetas o material POP",
            "fields": [
                {"id": "producto", "type": "string", "label": "Producto"},
                {"id": "marca", "type": "string", "label": "Marca"},
                {"id": "precio", "type": "number", "label": "Precio COP"},
                {"id": "presentacion", "type": "string", "label": "Presentacion (500ml, 1kg)"},
                {"id": "tipo_precio", "type": "string", "label": "Tipo (regular/promocion/descuento)"},
            ],
            "is_array": True,
            "applies_to": ["image", "voice"],
        },
        {
            "id": "exhibiciones_especiales",
            "label": "Exhibiciones especiales",
            "description": "Puntas de gondola, islas, displays fuera de lineal",
            "fields": [
                {"id": "tipo_exhibicion", "type": "string", "label": "Tipo (punta de gondola/isla/display/cabecera)"},
                {"id": "marca", "type": "string", "label": "Marca"},
                {"id": "productos", "type": "string", "label": "Productos exhibidos"},
                {"id": "material_pop", "type": "string", "label": "Material POP presente"},
                {"id": "estado", "type": "string", "label": "Estado (bueno/regular/malo)"},
            ],
            "is_array": True,
            "applies_to": ["image"],
        },
        {
            "id": "actividad_competencia",
            "label": "Actividad de competencia",
            "description": "Promociones, activaciones o exhibiciones de marcas competidoras",
            "fields": [
                {"id": "marca", "type": "string", "label": "Marca competidora"},
                {"id": "actividad", "type": "string", "label": "Actividad (promo, degustacion, exhibicion)"},
                {"id": "impacto", "type": "string", "label": "Impacto estimado (alto/medio/bajo)"},
                {"id": "alerta", "type": "boolean", "label": "Requiere atencion urgente"},
            ],
            "is_array": True,
            "applies_to": ["image", "voice", "text"],
        },
        {
            "id": "perfil_punto",
            "label": "Perfil del punto de venta",
            "description": "Informacion general del supermercado visitado",
            "fields": [
                {"id": "cadena", "type": "string", "label": "Cadena (Exito, Jumbo, D1, Ara, Olimpica)"},
                {"id": "formato", "type": "string", "label": "Formato (hipermercado/supermercado/express/descuento)"},
                {"id": "nivel_trafico", "type": "string", "label": "Trafico estimado (alto/medio/bajo)"},
                {"id": "observaciones", "type": "string", "label": "Observaciones generales"},
            ],
            "applies_to": ["image", "voice", "text"],
        },
    ],
    "confidence_threshold": 0.7,
    "sheets_tab": "Supermercados",
}

r1 = sb_post(
    "visit_types",
    {
        "implementation_id": "eficacia",
        "slug": "supermarket_visit",
        "display_name": "Visita a Supermercado",
        "schema_json": supermarket_schema,
        "sheets_tab": "Supermercados",
        "confidence_threshold": 0.7,
        "sort_order": 0,
        "is_active": True,
    },
)
if r1:
    print(f"supermarket_visit created: {r1[0]['id']}")

# Schema 2: Wholesale Visit
wholesale_schema = {
    "implementation": "eficacia",
    "visit_type": "wholesale_visit",
    "display_name": "Visita a Mayorista",
    "description": "Auditoria de punto de venta mayorista o distribuidor",
    "primary_media": ["image", "voice"],
    "categories": [
        {
            "id": "inventario_visible",
            "label": "Inventario visible",
            "description": "Productos en estanteria y bodega",
            "fields": [
                {"id": "producto", "type": "string", "label": "Producto"},
                {"id": "marca", "type": "string", "label": "Marca"},
                {"id": "cantidad_estimada", "type": "string", "label": "Cantidad estimada (cajas/unidades)"},
                {"id": "estado", "type": "string", "label": "Estado (fresco/proximo a vencer/danado)"},
            ],
            "is_array": True,
            "applies_to": ["image", "voice"],
        },
        {
            "id": "precios_mayorista",
            "label": "Precios mayorista",
            "description": "Precios por volumen y condiciones comerciales",
            "fields": [
                {"id": "producto", "type": "string", "label": "Producto"},
                {"id": "marca", "type": "string", "label": "Marca"},
                {"id": "precio_unitario", "type": "number", "label": "Precio unitario COP"},
                {"id": "precio_caja", "type": "number", "label": "Precio por caja COP"},
                {"id": "descuento_volumen", "type": "string", "label": "Descuento por volumen"},
            ],
            "is_array": True,
            "applies_to": ["image", "voice"],
        },
        {
            "id": "actividad_competencia",
            "label": "Actividad de competencia",
            "description": "Actividad de marcas competidoras",
            "fields": [
                {"id": "marca", "type": "string", "label": "Marca competidora"},
                {"id": "actividad", "type": "string", "label": "Actividad"},
                {"id": "alerta", "type": "boolean", "label": "Requiere atencion urgente"},
            ],
            "is_array": True,
            "applies_to": ["image", "voice", "text"],
        },
        {
            "id": "relacion_comercial",
            "label": "Relacion con el mayorista",
            "description": "Contacto y oportunidades comerciales",
            "fields": [
                {"id": "nombre_contacto", "type": "string", "label": "Nombre del contacto"},
                {"id": "pedido_sugerido", "type": "string", "label": "Pedido sugerido"},
                {"id": "condiciones", "type": "string", "label": "Condiciones comerciales mencionadas"},
                {"id": "seguimiento", "type": "string", "label": "Accion de seguimiento"},
            ],
            "applies_to": ["voice", "text"],
        },
    ],
    "confidence_threshold": 0.65,
    "sheets_tab": "Mayoristas",
}

r2 = sb_post(
    "visit_types",
    {
        "implementation_id": "eficacia",
        "slug": "wholesale_visit",
        "display_name": "Visita a Mayorista",
        "schema_json": wholesale_schema,
        "sheets_tab": "Mayoristas",
        "confidence_threshold": 0.65,
        "sort_order": 1,
        "is_active": True,
    },
)
if r2:
    print(f"wholesale_visit created: {r2[0]['id']}")

print("\nDone! Eficacia has 2 visit types ready.")
