#!/usr/bin/env python3
"""
Genera datos.js OPTIMIZADO (claves cortas) desde Data.xlsx + CMDB.xlsx

Mapeo de columnas (Data.xlsx):
  - Mes: columna "Mes"
  - Ciudad: city_name_x (si vacío, city_name_y)
  - Departamento: department_name_x (si vacío, department_name_y)
  - Regional: siteregion
  - Causa suspensión: slapausereason
  - Ticket: servicenow_id (si vacío, orderid)
  - Causa raíz: causa_final
  - Causa global: "Causa global"
  - Solución: procsolutiondes
  - Detalle falla: diagnosedescription + closeacceptdes + procsolutiondes
"""
import pandas as pd
import json

print("Leyendo DataV2.xlsx...")
xls = pd.ExcelFile('DataV2.xlsx')
sheet_to_parse = 'Data' if 'Data' in xls.sheet_names else xls.sheet_names[0]
df = xls.parse(sheet_to_parse)
print(f"  {len(df)} filas, {len(df.columns)} columnas leídas")
if 'etiqueta_padre' not in df.columns:
    df['etiqueta_padre'] = 'Sin dato'

print("Leyendo PLAN 500_UNIRED.xlsx...")
try:
    plan500_file = pd.ExcelFile('PLAN 500_UNIRED.xlsx')
    plan500_df = None
    for sheet in plan500_file.sheet_names:
        df_temp = pd.read_excel(plan500_file, sheet_name=sheet)
        if any('Estado de plan' in c for c in df_temp.columns) and any('FECHA DE EJECUCI' in c for c in df_temp.columns):
            plan500_df = df_temp
            break
    if plan500_df is None:
        plan500_df = pd.read_excel(plan500_file) # fallback
    
    estado_col = [c for c in plan500_df.columns if 'Estado de plan' in c]
    date_col = [c for c in plan500_df.columns if 'FECHA DE EJECUCI' in c]
    
    plan500_sites = {}
    plan500_counts = {}
    if estado_col and date_col:
        estado_col = estado_col[0]
        date_col = date_col[0]
        finalizados = plan500_df[plan500_df[estado_col].astype(str).str.strip().str.upper() == 'FINALIZADO']
        for _, row in finalizados.iterrows():
            d = pd.to_datetime(row[date_col], errors='coerce', dayfirst=True)
            if pd.isna(d):
                d = pd.to_datetime(row[date_col], errors='coerce')
            
            if pd.notna(d):
                mes = int(d.strftime('%Y%m'))
                plan500_counts[mes] = plan500_counts.get(mes, 0) + 1
                c = str(row['CODIGO']).strip() if pd.notna(row['CODIGO']) else None
                n = str(row['Netco']).strip() if pd.notna(row['Netco']) else None
                if c and c != 'nan': plan500_sites[c] = mes
                if n and n != 'nan': plan500_sites[n] = mes
except Exception as e:
    print(f"Error leyendo PLAN 500: {e}")
    plan500_sites = {}
    plan500_counts = {}
print(f"  Sitios Plan 500 Finalizados (con fecha): {len(plan500_sites)}")

print("Leyendo CMDB.xlsx...")
cmdb = pd.read_excel('CMDB.xlsx')

# CMDB: inventario operativo
cmdb_op = cmdb[cmdb['Site_state'].fillna('').str.upper() == 'OPERATIVO'].copy()
# Normalizar nombre de Cartagena y Cali para que coincida con Data.xlsx
cmdb_op['Ciudad'] = cmdb_op['Ciudad'].replace({
    'CARTAGENA DE INDIAS': 'CARTAGENA', 'Cartagena de Indias': 'Cartagena',
    'SANTIAGO DE CALI': 'CALI', 'Santiago de Cali': 'Cali'
})
sitios_por_ciudad = cmdb_op.groupby('Ciudad')['NodeB_Name'].nunique().to_dict()
sitios_por_depto = cmdb_op.groupby('Departamento')['NodeB_Name'].nunique().to_dict()
total_sitios_red = int(cmdb_op['NodeB_Name'].nunique())

# Mapeo de nombres de sitio desde CMDB
site_name_map = {}
for _, row in cmdb.dropna(subset=['Nombre_Site']).iterrows():
    name = str(row['Nombre_Site']).strip()
    codigo = row.get('CODIGO_EMPLAZAMIENTO')
    nodeb = row.get('NodeB_Name')
    if pd.notna(codigo) and str(codigo).strip():
        site_name_map[str(codigo).strip()] = name
    if pd.notna(nodeb) and str(nodeb).strip():
        site_name_map[str(nodeb).strip()] = name

# Las coordenadas ahora vienen nativas en DataV2.xlsx (Latitud, Longitud)

# ============================================================
# DERIVAR COLUMNAS SEGÚN INSTRUCCIONES DEL USUARIO
# ============================================================

# Ciudad y Departamento (nuevas columnas DataV2)
df['CITY_DS'] = df['Ciudad'].fillna('Sin dato')

# Departamento
df['DEPARTMENT_DS'] = df['Departamento'].fillna('Sin dato')

# Regional: siteregion
df['REGION_OP'] = df['siteregion'].fillna('Sin dato')

# Causa suspensión: slapausereason
df['CAUSA_SUSPENSION_ESPECIFICA'] = df['slapausereason'].fillna('Sin dato')

# Nueva columna Causa suspension global
if 'Causa suspensión global' in df.columns:
    df['CAUSA_SUSPENSION_MACRO'] = df['Causa suspensión global'].fillna('Sin dato')
elif 'Causa suspension global' in df.columns:
    df['CAUSA_SUSPENSION_MACRO'] = df['Causa suspension global'].fillna('Sin dato')
else:
    df['CAUSA_SUSPENSION_MACRO'] = df['CAUSA_SUSPENSION_ESPECIFICA']

# Ticket: Mostrar unicamente orderid (CM) segun requerimiento
df['TICKET'] = df['orderid'].fillna('Sin dato')

# Causa raíz (específica): causa_final
df['CAUSA_RAIZ'] = df['causa_final'].fillna('Sin dato')

# Causa global
df['CAUSA_GLOBAL'] = df['causa_global'].fillna('Sin dato')

# Solución: procsolutiondes
df['SOLUCION_TICKET'] = df['procsolutiondes'].fillna('Sin dato')

# Detalle de falla: combinación de diagnosedescription + closeacceptdes + procsolutiondes
def build_detalle(row):
    parts = []
    for col in ['diagnosedescription', 'closeacceptdes', 'procsolutiondes']:
        val = row.get(col)
        if pd.notna(val) and str(val).strip():
            parts.append(str(val).strip())
    return ' | '.join(parts) if parts else 'Sin detalle'

df['DETALLE_FALLA'] = df.apply(build_detalle, axis=1)

# Lógica IA
import re
def normalize_text(text):
    if not isinstance(text, str) or not text.strip():
        return ""
    text = text.lower().replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u').replace('ñ', 'n')
    return re.sub(r'\s+', ' ', text).strip()

def get_causa_ia(row):
    norm = normalize_text(row['DETALLE_FALLA'])
    if not norm:
        return 'Otra'
    vm_negative = r'(no\s+se\s+encuentra|no\s+registra|no\s+presenta|no\s+hay|sin)\s+(con\s+)?(mantenimiento\s+programado|mto\s+programado)'
    vm_positive = r'mantenimiento\s+programado|mto\.?\s+programado|trabajo\s+programado'
    is_vm = bool(re.search(vm_positive, norm)) and not bool(re.search(vm_negative, norm))
    
    red_mt_pattern = r'red\s+(de\s+)?media\s+tension|linea\s+(de\s+)?media\s+tension|transformador|trafo|canuela'
    is_red_mt = bool(re.search(red_mt_pattern, norm))
    
    tx_pattern = r'corte\s+(de\s+)?fibra|fibra\s+corte|falla\s+(el\s+|de\s+|del\s+)?atn|atn\s+caid|equipo\s+carrier|falla\s+(de\s+|del\s+)?equipo\s+carrier|falla\s+carrier'
    is_tx = bool(re.search(tx_pattern, norm))
    
    tormenta_pattern = r'tormenta|vendaval|lluvia|lluvias|inundac|deslizamiento|derrumb'
    is_tormenta = bool(re.search(tormenta_pattern, norm))
    
    if is_vm:
        return 'VM electrificadora'
    elif is_red_mt:
        return 'Línea Media tensión'
    elif is_tx:
        return 'TX'
    elif is_tormenta:
        return 'Tormenta eléctrica / Vendaval'
    else:
        return 'Otra'

df['CAUSA_IA'] = df.apply(get_causa_ia, axis=1)

# Site ID y Name
df['SITE_CD'] = df['sitio_homologado'].fillna('Sin dato')
df['SITE_NAME'] = df['SITE_CD'].apply(lambda x: site_name_map.get(str(x).strip(), str(x).strip()) if pd.notna(x) else 'Sin dato')

# Estado
df['ESTADO_RAD'] = df['faultresolvingtime'].isna().apply(lambda x: 'Activo' if x else 'Restaurado')

# Tecnología
df['TECNOLOGIA'] = df['domain'].replace({'RAN-3G': '3G', 'RAN-4G': '4G', 'RAN-2G': '2G', 'RAN-5G': '5G'}).fillna('4G')

# Minutos
df['MIN_IND_DIA'] = pd.to_numeric(df['minutos_falla'], errors='coerce').fillna(0)

# Rangos de duración
def get_rango(minutos):
    if minutos > 720: return '> 12 horas'
    if minutos > 480: return '8 a 12 Horas'
    if minutos > 240: return '4 a 8 horas'
    if minutos > 30: return '30 Min a 4 horas'
    if minutos > 10: return 'Flapping'
    return '< 10 Minutos'
df['Rangos'] = df['MIN_IND_DIA'].apply(get_rango)

# Fecha
df['FECHA_DIA'] = pd.to_datetime(df['fecha_inicio_sintetica'], errors='coerce')

# Mapear la columna `mes` al formato requerido MES_ANO
df['MES_ANO'] = df['mes'].astype(str).str.replace('-', '').fillna('0').astype(int)

# Fechas para agrupamiento masivas
df['fi'] = pd.to_datetime(df['faultfirstoccurtime'] if 'faultfirstoccurtime' in df.columns else df['fecha_inicio_sintetica'], errors='coerce')
df['ff'] = pd.to_datetime(df['fecha_fin_sintetica'], errors='coerce')

# Falla Activa (Si faultresolvingtime está vacio, sigue activa)
df['is_active'] = df['faultresolvingtime'].isna()

# Eventos con falla real
eventos = df[df['MIN_IND_DIA'] > 0].copy()
print(f"  Eventos con falla > 0 min: {len(eventos)}")

print("Calculando fallas masivas...")
eventos['SITE_PREFIX'] = eventos['SITE_CD'].astype(str).str[:3].str.upper()
eventos['fi_date'] = eventos['fi'].dt.date
eventos['ff_date'] = eventos['ff'].dt.date

grouped = eventos.dropna(subset=['fi', 'ff', 'SITE_PREFIX']).groupby(['fi_date', 'ff_date', 'SITE_PREFIX'])
masiva_clusters = []
for name, group in grouped:
    if len(group) < 3: 
        continue
    group = group.sort_values('fi')
    
    current_cluster = []
    base_fi = None
    base_ff = None
    
    for idx, row in group.iterrows():
        if not current_cluster:
            current_cluster.append(idx)
            base_fi = row['fi']
            base_ff = row['ff']
        else:
            diff_fi = abs((row['fi'] - base_fi).total_seconds()) / 60
            diff_ff = abs((row['ff'] - base_ff).total_seconds()) / 60
            if diff_fi <= 60 and diff_ff <= 60:
                current_cluster.append(idx)
            else:
                if len(current_cluster) >= 3:
                    masiva_clusters.append(current_cluster)
                current_cluster = [idx]
                base_fi = row['fi']
                base_ff = row['ff']
                
    if len(current_cluster) >= 3:
        masiva_clusters.append(current_cluster)

eventos['MASIVA_ID'] = 'No'
for i, cluster_indices in enumerate(masiva_clusters):
    eventos.loc[cluster_indices, 'MASIVA_ID'] = f"MASIVA-{i+1}"
print(f"  Total fallas masivas detectadas: {len(masiva_clusters)}")

for col in ['CAUSA_GLOBAL','CAUSA_RAIZ','TICKET','SOLUCION_TICKET','DETALLE_FALLA',
            'SITE_CD','SITE_NAME','CITY_DS','DEPARTMENT_DS','TECNOLOGIA','REGION_OP',
            'Rangos','ESTADO_RAD','CAUSA_SUSPENSION_MACRO', 'CAUSA_SUSPENSION_ESPECIFICA','etiqueta_padre', 'CAUSA_IA']:
    if col in eventos.columns:
        eventos[col] = eventos[col].fillna('Sin dato')

eventos['Latitud'] = pd.to_numeric(eventos['Latitud'], errors='coerce').fillna(4.6)
eventos['Longitud'] = pd.to_numeric(eventos['Longitud'], errors='coerce').fillna(-74.1)

# String interning: index repetitive strings to save space
str_pool = {}
str_list = []
def intern(s):
    s = str(s)
    if s not in str_pool:
        str_pool[s] = len(str_list)
        str_list.append(s)
    return str_pool[s]

# Build events with short keys and interned strings
# Truncate long text fields to save space
def truncate(s, max_len=1500):
    s = str(s)
    return s[:max_len] + '...' if len(s) > max_len else s

data = []
for _, r in eventos.iterrows():
    ts = r['FECHA_DIA']
    if pd.isna(ts):
        continue
    lat = r['Latitud']
    lng = r['Longitud']

    data.append([
        intern(r['SITE_CD']),              # 0: sitio_id
        intern(r['SITE_NAME']),            # 1: nombre
        intern(r['DEPARTMENT_DS']),         # 2: depto
        intern(r['CITY_DS']),              # 3: ciudad
        intern(r['REGION_OP']),            # 4: region
        intern(r['TECNOLOGIA']),           # 5: tech
        round(float(r['MIN_IND_DIA']),1),  # 6: min
        intern(r['CAUSA_GLOBAL']),         # 7: causa macro (causa global)
        intern(r['CAUSA_RAIZ']),           # 8: causa esp (causa_final)
        intern(r['ESTADO_RAD']),           # 9: estado
        intern(r['TICKET']),              # 10: ticket
        intern(truncate(r['SOLUCION_TICKET'])),  # 11: solucion
        ts.strftime('%Y-%m-%d %H:%M:%S'),  # 12: fecha
        round(float(lat),4),               # 13: lat
        round(float(lng),4),               # 14: lng
        intern(r['Rangos']),               # 15: rango
        int(r['MES_ANO']),                 # 16: mes_ano
        intern(r['CAUSA_SUSPENSION_MACRO']),       # 17: causa suspensión macro
        intern(r['CAUSA_SUSPENSION_ESPECIFICA']),  # 18: causa suspensión especifica
        intern(truncate(r['DETALLE_FALLA'])), # 19: detalle falla
        intern(r['etiqueta_padre']),               # 20: etiqueta_padre
        intern(r['MASIVA_ID']),                    # 21: masiva_id
        intern(r['CAUSA_IA']),                     # 22: causa_ia
        1 if r['is_active'] else 0,                # 23: is_active (1 o 0)
    ])

print(f"Eventos: {len(data)}, Strings pool: {len(str_list)}")

# Causa raíz por macro
causas_macro = sorted(eventos['CAUSA_GLOBAL'].unique().tolist())
cr_map = {}
for m in causas_macro:
    esp = [e for e in eventos[eventos['CAUSA_GLOBAL']==m]['CAUSA_RAIZ'].unique() if e != 'Sin dato']
    cr_map[m] = sorted(esp) if esp else ['Sin especificar']

# Causa suspensión por macro (agrupar automáticamente)
causas_susp = sorted(eventos['CAUSA_SUSPENSION_MACRO'].unique().tolist())
cs_map = {}
for m in causas_susp:
    esp = [e for e in eventos[eventos['CAUSA_SUSPENSION_MACRO']==m]['CAUSA_SUSPENSION_ESPECIFICA'].unique() if e != 'Sin dato']
    cs_map[m] = sorted(esp) if esp else ['Sin especificar']

inv_c = {str(k).strip(): int(v) for k,v in sitios_por_ciudad.items()}
inv_d = {str(k).strip(): int(v) for k,v in sitios_por_depto.items()}

# Meses disponibles
meses_disponibles = sorted(eventos['MES_ANO'].unique().tolist())
print(f"  Meses disponibles: {meses_disponibles}")

js = "// Data real generada desde Data.xlsx + CMDB.xlsx\n"
js += f"const _S={json.dumps(str_list, ensure_ascii=False)};\n"
js += f"const _E={json.dumps(data, ensure_ascii=False)};\n"
js += f"const _IC={json.dumps(inv_c, ensure_ascii=False)};\n"
js += f"const _ID={json.dumps(inv_d, ensure_ascii=False)};\n"
js += f"const _TSR={total_sitios_red};\n"
js += f"const _CR={json.dumps(cr_map, ensure_ascii=False)};\n"
js += f"const _CS={json.dumps(cs_map, ensure_ascii=False)};\n"
js += f"const _MA={json.dumps(meses_disponibles)};\n"
js += f"const _PLAN500={json.dumps(plan500_sites)};\n"
js += f"const _PLAN500_COUNTS={json.dumps(plan500_counts)};\n"
import gzip
with gzip.open('datos.js.gz', 'wt', encoding='utf-8') as f:
    f.write(js)

with open('datos.js', 'w', encoding='utf-8') as f:
    f.write(js)

with gzip.open('datos.js.gz', 'wt', encoding='utf-8') as f:
    f.write(js)

print(f"datos.js: {len(js):,} bytes")
print("¡LISTO!")
