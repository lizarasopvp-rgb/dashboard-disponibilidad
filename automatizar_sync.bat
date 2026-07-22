@echo off
REM =========================================================================
REM Script de Sincronizacion Automatica - Dashboard Disponibilidad
REM =========================================================================

REM 1. Ir a la carpeta del proyecto
cd /d "C:\Users\ADECCOBPO\Desktop\Dashboard_disponibilidad"

REM 2. Configurar la conexion a la base de datos de Supabase (Produccion)
REM Esta URL fue recuperada automaticamente del archivo migrate_db.py
set DATABASE_URL=postgresql://postgres.shoudgqfklpqhwngseoa:Juanlizarasor1245@aws-0-ca-central-1.pooler.supabase.com:5432/postgres

REM 3. Ejecutar el script de sincronizacion en Python
echo Iniciando sincronizacion con la API de Tigo...
python sync_disponibilidad.py

REM 4. (Opcional) Pausar para ver el resultado si se ejecuta manualmente. 
REM En tareas programadas, puedes borrar la linea "pause".
pause
