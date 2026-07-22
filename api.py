import os
from flask import Flask, request, jsonify, send_file, make_response
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

DB_URL = os.environ.get('DATABASE_URL')
DB_CONFIG = {
    'dbname': 'dashboard_notas',
    'user': 'postgres',
    'password': 'admin123',
    'host': 'localhost',
    'port': '5432'
}

def get_db():
    if DB_URL:
        return psycopg2.connect(DB_URL)
    return psycopg2.connect(**DB_CONFIG)

@app.route('/')
def index():
    return send_file('dashboard_disponibilidad_tigo_v5.html')

@app.route('/datos.js')
def serve_datos_js():
    # En producción servir el comprimido para ahorrar 90% de peso
    if os.path.exists('datos.js.gz') and not os.environ.get('FLASK_ENV') == 'development':
        response = make_response(send_file('datos.js.gz'))
        response.headers['Content-Encoding'] = 'gzip'
        response.headers['Content-Type'] = 'application/javascript'
        return response
    return send_file('datos.js')

# ============================================================
#  NOTAS DE SITIOS
# ============================================================
@app.route('/nota_sitio', methods=['POST'])
def guardar_nota_sitio():
    d = request.json
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO notas_sitios (departamento, municipio, codigo_sitio, nota)
            VALUES (%s, %s, %s, %s)
            RETURNING id, fecha_registro
        """, (d['departamento'], d['municipio'], d['codigo_sitio'], d['nota']))
        row = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"ok": True, "id": row[0], "fecha": str(row[1])}), 200
    except Exception as e:
        print(f"Error nota_sitio: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route('/notas_sitio/<codigo>', methods=['GET'])
def obtener_notas_sitio(codigo):
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM notas_sitios WHERE codigo_sitio = %s ORDER BY fecha_registro DESC", (codigo,))
        notas = cur.fetchall()
        cur.close()
        conn.close()
        for n in notas:
            n['fecha_registro'] = str(n['fecha_registro'])
        return jsonify(notas), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/nota_sitio/<int:nota_id>', methods=['DELETE'])
def borrar_nota_sitio(nota_id):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("DELETE FROM notas_sitios WHERE id = %s", (nota_id,))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"ok": True}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============================================================
#  NOTAS DE FALLAS
# ============================================================
@app.route('/nota_falla', methods=['POST'])
def guardar_nota_falla():
    d = request.json
    try:
        conn = get_db()
        cur = conn.cursor()
        # hora_inicio y hora_fin pueden venir como texto formateado o null
        # Los guardamos como texto en la BD si no se pueden parsear
        hora_ini = d.get('hora_inicio')
        hora_fin = d.get('hora_fin')
        # Si vienen como 'N/A' o 'null', ponerlos en None
        if hora_ini in (None, 'null', 'N/A', ''): hora_ini = None
        if hora_fin in (None, 'null', 'N/A', ''): hora_fin = None
        
        cur.execute("""
            INSERT INTO notas_fallas (ticket, hora_inicio, hora_fin, duracion_minutos,
                                      causa_especifica, solucion, codigo_sitio, nota)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, fecha_registro
        """, (
            d['ticket'],
            hora_ini,
            hora_fin,
            d.get('duracion_minutos'),
            d.get('causa_especifica'),
            d.get('solucion'),
            d['codigo_sitio'],
            d['nota']
        ))
        row = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"ok": True, "id": row[0], "fecha": str(row[1])}), 200
    except Exception as e:
        print(f"Error nota_falla: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route('/notas_falla/<ticket>', methods=['GET'])
def obtener_notas_falla(ticket):
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM notas_fallas WHERE ticket = %s ORDER BY fecha_registro DESC", (ticket,))
        notas = cur.fetchall()
        cur.close()
        conn.close()
        for n in notas:
            n['fecha_registro'] = str(n['fecha_registro'])
            if n['hora_inicio']: n['hora_inicio'] = str(n['hora_inicio'])
            if n['hora_fin']: n['hora_fin'] = str(n['hora_fin'])
        return jsonify(notas), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/nota_falla/<int:nota_id>', methods=['DELETE'])
def borrar_nota_falla(nota_id):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("DELETE FROM notas_fallas WHERE id = %s", (nota_id,))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"ok": True}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============================================================
#  NOTAS DE ANÁLISIS (causa+mes en gráfica apilada)
# ============================================================
@app.route('/nota_analisis', methods=['POST'])
def guardar_nota_analisis():
    d = request.json
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO notas_analisis (seccion, causa, mes, nota, imagen)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id, fecha_registro
        """, (d.get('seccion','causa_raiz'), d['causa'], d['mes'], d['nota'], d.get('imagen')))
        row = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"ok": True, "id": row[0], "fecha": str(row[1])}), 200
    except Exception as e:
        print(f"Error nota_analisis: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route('/notas_analisis/<seccion>/<causa>/<mes>', methods=['GET'])
def obtener_notas_analisis(seccion, causa, mes):
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT * FROM notas_analisis
            WHERE seccion = %s AND causa = %s AND mes = %s
            ORDER BY fecha_registro DESC
        """, (seccion, causa, mes))
        notas = cur.fetchall()
        cur.close()
        conn.close()
        for n in notas:
            n['fecha_registro'] = str(n['fecha_registro'])
        return jsonify(notas), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/nota_analisis/<int:nota_id>', methods=['DELETE'])
def borrar_nota_analisis(nota_id):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("DELETE FROM notas_analisis WHERE id = %s", (nota_id,))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"ok": True}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============================================================
#  RESUMEN DE NOTAS (Para pintar botones)
# ============================================================
@app.route('/resumen_notas', methods=['GET'])
def resumen_notas():
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT codigo_sitio FROM notas_sitios")
        sitios = [r[0] for r in cur.fetchall()]
        cur.execute("SELECT DISTINCT ticket FROM notas_fallas")
        fallas = [r[0] for r in cur.fetchall()]
        cur.execute("SELECT DISTINCT seccion || '|' || causa || '|' || mes FROM notas_analisis")
        analisis = [r[0] for r in cur.fetchall()]
        cur.close()
        conn.close()
        return jsonify({"sitios": sitios, "fallas": fallas, "analisis": analisis}), 200
    except Exception as e:
        return jsonify({"sitios": [], "fallas": [], "analisis": [], "error": str(e)}), 500

# ============================================================
#  DISPONIBILIDAD 4G - Historico NAR
# ============================================================
@app.route('/api/disponibilidad/<fuente>', methods=['GET'])
def obtener_disponibilidad(fuente):
    """Retorna historico NAR 4G filtrado por fuente (Huawei o UNIRED)."""
    if fuente not in ('Huawei', 'UNIRED'):
        return jsonify({"error": "Fuente debe ser 'Huawei' o 'UNIRED'"}), 400
    try:
        desde = request.args.get('desde')  # formato: 2025-10
        hasta = request.args.get('hasta')  # formato: 2026-06
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        sql = "SELECT mes, region, nar_pct, cantidad_eventos, minutos_falla, fecha_consulta FROM disponibilidad_4g_historico WHERE fuente = %s"
        params = [fuente]

        if desde:
            sql += " AND mes >= %s"
            params.append(desde + '-01')
        if hasta:
            sql += " AND mes <= %s"
            params.append(hasta + '-01')

        sql += " ORDER BY mes, region"
        cur.execute(sql, params)
        rows = cur.fetchall()
        cur.close()
        conn.close()

        for r in rows:
            r['mes'] = str(r['mes'])
            r['nar_pct'] = float(r['nar_pct']) if r['nar_pct'] else None
            if r['fecha_consulta']:
                r['fecha_consulta'] = str(r['fecha_consulta'])

        return jsonify(rows), 200
    except Exception as e:
        print(f"Error disponibilidad GET: {e}")
        return jsonify({"error": str(e)}), 500


# ============================================================
#  TEST DE CONEXION
# ============================================================
@app.route('/ping', methods=['GET'])
def ping():
    try:
        conn = get_db()
        conn.close()
        return jsonify({"ok": True, "msg": "Conectado a PostgreSQL"}), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


if __name__ == '__main__':
    print("== Servidor API Dashboard Notas ==")
    try:
        c = get_db()
        c.close()
        print("Conexion exitosa a PostgreSQL!")
    except Exception as e:
        print(f"ERROR de conexion: {e}")
    port = int(os.environ.get('PORT', 5000))
    print(f"Servidor en http://0.0.0.0:{port}")
    app.run(host='0.0.0.0', port=port)
