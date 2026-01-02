"""
Script de prueba para verificar conexión a Supabase
y estructura de datos antes del deployment
"""

import sys
from datetime import datetime, timedelta
import pytz

try:
    from supabase import create_client
    import pandas as pd
    print("✅ Librerías importadas correctamente")
except ImportError as e:
    print(f"❌ Error al importar librerías: {e}")
    print("\n👉 Ejecuta: pip install -r requirements.txt")
    sys.exit(1)

def test_connection():
    """Probar conexión a Supabase"""
    print("\n" + "="*60)
    print("🔍 PROBANDO CONEXIÓN A SUPABASE")
    print("="*60)
    
    try:
        # Intentar leer secrets
        import streamlit as st
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        print("✅ Secrets cargados correctamente")
    except Exception as e:
        print(f"❌ Error al cargar secrets: {e}")
        print("\n👉 Asegúrate de tener .streamlit/secrets.toml configurado")
        return False
    
    try:
        supabase = create_client(url, key)
        print("✅ Cliente de Supabase creado")
    except Exception as e:
        print(f"❌ Error al crear cliente: {e}")
        return False
    
    return supabase

def test_orders_table(supabase):
    """Probar tabla orders_final"""
    print("\n" + "="*60)
    print("📊 PROBANDO TABLA orders_final")
    print("="*60)
    
    try:
        # Obtener últimas 5 órdenes
        response = supabase.table('orders_final')\
            .select('*')\
            .order('created_at', desc=True)\
            .limit(5)\
            .execute()
        
        if not response.data:
            print("⚠️  La tabla está vacía")
            return False
        
        df = pd.DataFrame(response.data)
        print(f"✅ Tabla encontrada con {len(df)} órdenes (muestra)")
        print(f"📅 Rango de fechas: {df['created_at'].min()} a {df['created_at'].max()}")
        
        # Verificar columnas importantes
        required_cols = [
            'id', 'order_number', 'created_at', 'processed_at',
            'total_price', 'channel_tags', 'line_items'
        ]
        
        missing_cols = [col for col in required_cols if col not in df.columns]
        
        if missing_cols:
            print(f"⚠️  Columnas faltantes: {', '.join(missing_cols)}")
        else:
            print("✅ Todas las columnas necesarias presentes")
        
        return df
        
    except Exception as e:
        print(f"❌ Error al acceder a orders_final: {e}")
        return False

def test_line_items(df):
    """Probar extracción de line_items"""
    print("\n" + "="*60)
    print("📦 PROBANDO LINE_ITEMS")
    print("="*60)
    
    if 'line_items' not in df.columns:
        print("❌ Columna line_items no existe")
        return False
    
    # Contar órdenes con line_items
    has_items = df['line_items'].notna().sum()
    total = len(df)
    pct = (has_items / total * 100) if total > 0 else 0
    
    print(f"📊 {has_items}/{total} órdenes tienen line_items ({pct:.1f}%)")
    
    if has_items == 0:
        print("❌ Ninguna orden tiene line_items")
        print("\n👉 Asegúrate de que tu API está guardando line_items en formato JSON")
        return False
    
    # Probar parsear un line_item
    import json
    for idx, row in df.iterrows():
        if pd.notna(row['line_items']):
            try:
                if isinstance(row['line_items'], str):
                    items = json.loads(row['line_items'])
                elif isinstance(row['line_items'], list):
                    items = row['line_items']
                else:
                    continue
                
                if items:
                    print(f"✅ Line items parseados correctamente")
                    print(f"   Ejemplo de producto:")
                    print(f"   - SKU: {items[0].get('sku', 'N/A')}")
                    print(f"   - Nombre: {items[0].get('name', 'N/A')}")
                    print(f"   - Cantidad: {items[0].get('quantity', 0)}")
                    print(f"   - Precio: {items[0].get('price', 0)}")
                    return True
            except json.JSONDecodeError:
                print("⚠️  Line items no es JSON válido")
                continue
    
    print("⚠️  No se pudieron parsear line_items")
    return False

def test_channels(df):
    """Probar distribución de canales"""
    print("\n" + "="*60)
    print("🏪 PROBANDO CANALES")
    print("="*60)
    
    if 'channel_tags' not in df.columns:
        print("❌ Columna channel_tags no existe")
        return False
    
    channel_counts = df['channel_tags'].value_counts()
    print("📊 Distribución de canales:")
    for channel, count in channel_counts.items():
        print(f"   - {channel}: {count} órdenes")
    
    return True

def test_dates(df):
    """Probar manejo de fechas"""
    print("\n" + "="*60)
    print("📅 PROBANDO FECHAS")
    print("="*60)
    
    try:
        df['processed_at'] = pd.to_datetime(df['processed_at'])
        df['created_at'] = pd.to_datetime(df['created_at'])
        
        print(f"✅ Fechas parseadas correctamente")
        print(f"   - Primera orden: {df['created_at'].min()}")
        print(f"   - Última orden: {df['created_at'].max()}")
        
        # Verificar timezone
        if df['processed_at'].dt.tz is None:
            print("⚠️  Las fechas no tienen timezone (se asumirá UTC)")
        else:
            print(f"✅ Timezone: {df['processed_at'].dt.tz}")
        
        return True
    except Exception as e:
        print(f"❌ Error al parsear fechas: {e}")
        return False

def main():
    """Función principal de prueba"""
    print("\n🚀 INICIANDO PRUEBAS DEL DASHBOARD")
    print("="*60)
    
    # Test 1: Conexión
    supabase = test_connection()
    if not supabase:
        print("\n❌ PRUEBAS FALLIDAS - No se pudo conectar a Supabase")
        return
    
    # Test 2: Tabla orders_final
    df = test_orders_table(supabase)
    if df is False or df.empty:
        print("\n❌ PRUEBAS FALLIDAS - Problema con tabla orders_final")
        return
    
    # Test 3: Line items
    test_line_items(df)
    
    # Test 4: Canales
    test_channels(df)
    
    # Test 5: Fechas
    test_dates(df)
    
    print("\n" + "="*60)
    print("✅ TODAS LAS PRUEBAS COMPLETADAS")
    print("="*60)
    print("\n👉 Siguiente paso: Ejecuta 'streamlit run app.py'")
    print("   O haz deployment en Streamlit Cloud")

if __name__ == "__main__":
    main()