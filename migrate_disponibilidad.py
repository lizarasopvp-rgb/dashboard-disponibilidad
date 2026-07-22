"""
migrate_disponibilidad.py
Crea la tabla disponibilidad_4g_historico en PostgreSQL.
Ejecutar una única vez: python migrate_disponibilidad.py
"""
import psycopg2
import os

DB_CONFIG = {
    'dbname': 'dashboard_notas',
    'user': 'postgres',
    'password': 'admin123',
    'host': 'localhost',
    'port': '5432'
}

SQL = """
CREATE TABLE IF NOT EXISTS disponibilidad_4g_historico (
    id               BIGSERIAL PRIMARY KEY,
    fuente           VARCHAR(20)   NOT NULL,
    mes              DATE          NOT NULL,
    region           VARCHAR(20)   NOT NULL,
    nar_pct          NUMERIC(5,2),
    cantidad_eventos INTEGER,
    minutos_falla    BIGINT,
    fecha_consulta   TIMESTAMP     DEFAULT NOW(),
    created_at       TIMESTAMP     DEFAULT NOW(),
    updated_at       TIMESTAMP     DEFAULT NOW(),
    CONSTRAINT uq_disp_fuente_mes_region UNIQUE (fuente, mes, region)
);

CREATE INDEX IF NOT EXISTS idx_disp_fuente ON disponibilidad_4g_historico (fuente);
CREATE INDEX IF NOT EXISTS idx_disp_mes    ON disponibilidad_4g_historico (mes);
"""

def migrate():
    db_url = os.environ.get('DATABASE_URL')
    if db_url:
        conn = psycopg2.connect(db_url)
    else:
        conn = psycopg2.connect(**DB_CONFIG)

    cur = conn.cursor()
    cur.execute(SQL)
    conn.commit()
    cur.close()
    conn.close()
    print("[OK] Tabla disponibilidad_4g_historico creada exitosamente.")

if __name__ == "__main__":
    migrate()
