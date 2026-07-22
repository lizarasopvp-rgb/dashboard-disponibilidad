"""
sync_disponibilidad.py
Consulta la API de disponibilidad, extrae datos NAR 4G por region y mes,
y los almacena/actualiza en PostgreSQL (tabla disponibilidad_4g_historico).

Uso:
  python sync_disponibilidad.py          # Sync completa
  python sync_disponibilidad.py --fuente Huawei   # Solo una fuente
"""
import os
import sys
import json
import logging
from datetime import datetime

import requests
import psycopg2

# ---------- Config ----------
API_URL = os.environ.get(
    'DISPONIBILIDAD_API_URL',
    'http://10.100.64.87:4002/api/disponibilidad'
)

DB_CONFIG = {
    'dbname': os.environ.get('DB_NAME', 'dashboard_notas'),
    'user':   os.environ.get('DB_USER', 'postgres'),
    'password': os.environ.get('DB_PASS', 'admin123'),
    'host':   os.environ.get('DB_HOST', 'localhost'),
    'port':   os.environ.get('DB_PORT', '5432'),
}

FUENTES = {
    'Huawei': 'Excluye parada reloj',
    'UNIRED': 'Sin exclusiones',
}

PAYLOAD_BASE = {
    'site': '',
    'month': '',
    'tech': ['RAN-3G', 'RAN-4G'],
    'region': ['ANDINA', 'CARIBE', 'CENTRO', 'SUR'],
    'event': [
        'PARADA_RELOJ', 'TRANSMISION_MNO', 'EVENTO SIN CERRAR',
        'MINUTOS_HUAWEI_CONTRATO', 'DEMORA', 'MINUTOS_HUAWEI_EXLUSION',
        'MAL CONTEO DE CELDAS', 'NAR',
    ],
}

REGIONES = ['ANDINA', 'CARIBE', 'CENTRO', 'SUR']

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
log = logging.getLogger('sync_disp')


# ---------- Helpers ----------
def get_db():
    db_url = os.environ.get('DATABASE_URL')
    if db_url:
        return psycopg2.connect(db_url)
    return psycopg2.connect(**DB_CONFIG)


def fetch_api(fuente_file, retries=3):
    """Consulta la API con reintentos."""
    payload = {**PAYLOAD_BASE, 'file': fuente_file}
    for attempt in range(1, retries + 1):
        try:
            resp = requests.post(API_URL, json=payload, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            log.warning(f'  Intento {attempt}/{retries} fallo: {e}')
            if attempt == retries:
                raise
    return None


def parse_response(api_data):
    """
    Extrae de la respuesta de la API los datos NAR 4G por mes y region.
    Retorna lista de dicts listos para insertar.
    """
    rows = []
    data_section = api_data.get('data', {})

    for mes_str, month_obj in data_section.items():
        # mes_str es '2026-06', convertir a date del 1er dia del mes
        try:
            mes_date = datetime.strptime(mes_str, '%Y-%m').replace(day=1).date()
        except ValueError:
            log.warning(f'  Mes invalido: {mes_str}, saltando')
            continue

        nar_data = month_obj.get('narData', [])
        if not nar_data:
            continue

        # Datos por region
        total_min_fallas = 0
        total_eventos = 0
        total_sitios = 0
        region_rows = []

        for item in nar_data:
            region = item.get('region', '').upper()
            if region not in REGIONES:
                continue

            fg = item.get('4g', {})
            nar_pct = fg.get('narPct')
            cantidad_eventos = fg.get('totalEventos', 0)
            min_fallas = fg.get('minFallasTotal', 0)

            if nar_pct is None:
                continue

            region_rows.append({
                'mes': mes_date,
                'region': region,
                'nar_pct': round(nar_pct, 2),
                'cantidad_eventos': cantidad_eventos,
                'minutos_falla': int(min_fallas),
            })

            total_min_fallas += min_fallas
            total_eventos += cantidad_eventos
            total_sitios += fg.get('totalSitios', 0)

        rows.extend(region_rows)

        # Calcular GLOBAL como promedio ponderado por sitios, o buscar
        # en 'bars' el Total bruto de minutos de falla
        # Mejor: calcular desde narData sumando min y sitios
        if region_rows:
            # Calculamos el NAR global desde las bars (Total bruto)
            bars = month_obj.get('chartData', {}).get('bars', [])
            global_nar = None
            global_min = 0
            global_ev = 0

            for bar in bars:
                if bar.get('label') == 'Total bruto de minutos de falla':
                    fg_bar = bar.get('4g', {})
                    global_min += fg_bar.get('minFallas', 0)

            # NAR global = promedio ponderado de las regiones
            # Usamos: NAR = 1 - (sum_min_fallas_regiones / (sum_minMes_regiones * totalSitios_regiones))
            # Mas simple: promedio ponderado por sitios de los NAR regionales
            # O simplemente: usar el calculo: (total_sitios*minMes - total_min_fallas) / (total_sitios*minMes)
            # Pero es mas facil calcular desde los datos reales
            # Calculamos como promedio simple de las 4 regiones (lo que muestra el dashboard)
            sum_nar = sum(r['nar_pct'] for r in region_rows)
            global_nar_pct = round(sum_nar / len(region_rows), 2)

            rows.append({
                'mes': mes_date,
                'region': 'GLOBAL',
                'nar_pct': global_nar_pct,
                'cantidad_eventos': total_eventos,
                'minutos_falla': int(total_min_fallas),
            })

    return rows


def upsert_rows(conn, fuente, rows):
    """Inserta o actualiza registros en la BD."""
    cur = conn.cursor()
    sql = """
        INSERT INTO disponibilidad_4g_historico
            (fuente, mes, region, nar_pct, cantidad_eventos, minutos_falla, fecha_consulta, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
        ON CONFLICT (fuente, mes, region)
        DO UPDATE SET
            nar_pct = EXCLUDED.nar_pct,
            cantidad_eventos = EXCLUDED.cantidad_eventos,
            minutos_falla = EXCLUDED.minutos_falla,
            fecha_consulta = NOW(),
            updated_at = NOW()
    """
    for r in rows:
        cur.execute(sql, (
            fuente,
            r['mes'],
            r['region'],
            r['nar_pct'],
            r['cantidad_eventos'],
            r['minutos_falla'],
        ))
    conn.commit()
    cur.close()
    return len(rows)


# ---------- Main ----------
def sync(fuente_filter=None):
    """Ejecuta la sincronizacion completa."""
    log.info('=== Inicio sincronizacion disponibilidad 4G ===')
    conn = get_db()
    total = 0

    fuentes = FUENTES
    if fuente_filter:
        if fuente_filter in FUENTES:
            fuentes = {fuente_filter: FUENTES[fuente_filter]}
        else:
            log.error(f'Fuente invalida: {fuente_filter}. Opciones: {list(FUENTES.keys())}')
            return 0

    for fuente_name, fuente_file in fuentes.items():
        log.info(f'Consultando API para {fuente_name} (file={fuente_file})...')
        try:
            api_data = fetch_api(fuente_file)
        except Exception as e:
            log.error(f'  Error fatal al consultar API para {fuente_name}: {e}')
            continue

        log.info(f'  Parseando respuesta...')
        rows = parse_response(api_data)
        log.info(f'  {len(rows)} registros extraidos')

        if rows:
            count = upsert_rows(conn, fuente_name, rows)
            log.info(f'  {count} registros insertados/actualizados en BD')
            total += count

    conn.close()
    log.info(f'=== Sincronizacion completada: {total} registros totales ===')
    return total


if __name__ == '__main__':
    fuente_arg = None
    if len(sys.argv) > 2 and sys.argv[1] == '--fuente':
        fuente_arg = sys.argv[2]
    sync(fuente_arg)
