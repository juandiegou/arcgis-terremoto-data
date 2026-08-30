"""
Script de sincronizacion: Descarga reportes ciudadanos del FeatureServer de ArcGIS
y los guarda como archivo JSON para que Databricks los pueda leer via raw.githubusercontent.com

AUTENTICACION:
- Si el FeatureServer es publico (como ReportesCiudadanos_Terremoto_20260810), NO necesita credenciales.
- Si requiere autenticacion, configura estos GitHub Secrets en el repo:
    ARCGIS_USERNAME  -> tu usuario de ArcGIS Online
    ARCGIS_PASSWORD  -> tu contrasena de ArcGIS Online
  El script generara un token automaticamente y lo usara para autenticarse.
"""
import requests
import json
import os
from datetime import datetime

# URL del FeatureServer de ArcGIS
FEATURESERVER_URL = "https://services.arcgis.com/vC1CdlKWEAtuT38d/arcgis/rest/services/ReportesCiudadanos_Terremoto_20260810/FeatureServer"
OUTPUT_FILE = "data/reportes_terremoto.json"

def get_arcgis_token():
    """Obtiene un token de ArcGIS Online si hay credenciales configuradas.
    Retorna None si no hay credenciales (servicio publico).
    """
    username = os.environ.get("ARCGIS_USERNAME")
    password = os.environ.get("ARCGIS_PASSWORD")
    
    if not username or not password:
        print("No hay credenciales de ArcGIS configuradas (servicio publico)")
        return None
    
    print(f"Autenticando con ArcGIS Online como: {username}")
    
    token_url = "https://www.arcgis.com/sharing/rest/generateToken"
    token_params = {
        'username': username,
        'password': password,
        'grant_type': 'password',
        'f': 'json'
    }
    
    r = requests.post(token_url, data=token_params, timeout=15)
    r.raise_for_status()
    result = r.json()
    
    if 'token' not in result:
        raise Exception(f"Error de autenticacion: {result.get('error', {}).get('message', 'N/A')}")
    
    print("Token obtenido exitosamente")
    return result['token']

def download_features():
    """Descarga todos los features del FeatureServer de ArcGIS."""
    print(f"Conectando a: {FEATURESERVER_URL}")
    
    # Obtener token si hay credenciales
    token = get_arcgis_token()
    
    # Obtener info del servicio
    params = {'f': 'json'}
    if token:
        params['token'] = token
    
    r = requests.get(f"{FEATURESERVER_URL}?f=json", params=params, timeout=15)
    r.raise_for_status()
    service_info = r.json()
    
    if 'error' in service_info:
        raise Exception(f"Error del servicio: {service_info['error'].get('message', 'N/A')}")
    
    layers = service_info.get('layers', [])
    print(f"Servicio: {service_info.get('name', 'N/A')}")
    print(f"Capas: {len(layers)}")
    
    if not layers:
        print("No hay capas disponibles")
        return None
    
    layer_id = layers[0].get('id', 0)
    print(f"Usando capa {layer_id}: {layers[0].get('name', 'N/A')}")
    
    # Descargar todos los features con geometria
    query_url = f"{FEATURESERVER_URL}/{layer_id}/query"
    query_params = {
        'where': '1=1',
        'outFields': '*',
        'f': 'json',
        'returnGeometry': 'true',
        'resultRecordCount': 2000
    }
    if token:
        query_params['token'] = token
    
    print("Descargando features...")
    r = requests.get(query_url, params=query_params, timeout=60)
    r.raise_for_status()
    result = r.json()
    
    if 'error' in result:
        raise Exception(f"Error en query: {result['error'].get('message', 'N/A')}")
    
    features = result.get('features', [])
    print(f"Descargados {len(features)} features")
    
    return result

def save_json(data, filepath):
    """Guarda los datos como archivo JSON con metadata."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    output = {
        "metadata": {
            "source": FEATURESERVER_URL,
            "downloaded_at": datetime.utcnow().isoformat() + "Z",
            "total_features": len(data.get('features', [])),
            "authenticated": bool(os.environ.get("ARCGIS_USERNAME"))
        },
        "data": data
    }
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"Guardado en: {filepath}")
    print(f"Tamano: {os.path.getsize(filepath) / 1024:.1f} KB")

def main():
    print("="*60)
    print("SINCRONIZACION: Reportes ArcGIS -> GitHub")
    print("="*60)
    
    data = download_features()
    if data is None:
        print("No se pudieron descargar los datos")
        exit(1)
    
    save_json(data, OUTPUT_FILE)
    
    print("Sincronizacion completada!")
    print("Los datos estaran disponibles en raw.githubusercontent.com")

if __name__ == "__main__":
    main()
