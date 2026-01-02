"""
Módulo para procesar line_items desde orders_final
Extrae productos del campo JSON y los agrega al dashboard
"""

import pandas as pd
import json

def extract_line_items_from_orders(df):
    """
    Extrae line items del campo JSON en orders_final
    
    Args:
        df: DataFrame con la columna 'line_items' (JSON string o dict)
        
    Returns:
        DataFrame con productos desglosados
    """
    
    if df.empty or 'line_items' not in df.columns:
        return pd.DataFrame()
    
    all_items = []
    
    for idx, row in df.iterrows():
        try:
            # Parsear JSON si es string
            if isinstance(row['line_items'], str):
                items = json.loads(row['line_items'])
            elif isinstance(row['line_items'], list):
                items = row['line_items']
            else:
                continue
            
            # Procesar cada item
            for item in items:
                product_data = {
                    'order_id': row['id'],
                    'order_date': row['date'],
                    'channel': row['channel'],
                    'line_item_id': item.get('id'),
                    'product_id': item.get('product_id'),
                    'variant_id': item.get('variant_id'),
                    'sku': item.get('sku', 'N/A'),
                    'name': item.get('name', 'Sin nombre'),
                    'title': item.get('title', item.get('name', 'Sin título')),
                    'quantity': item.get('quantity', 0),
                    'price': float(item.get('price', 0)),
                    'total_discount': float(item.get('total_discount', 0)),
                    'line_total': float(item.get('price', 0)) * item.get('quantity', 0)
                }
                all_items.append(product_data)
        
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            # Skip problematic rows
            continue
    
    if not all_items:
        return pd.DataFrame()
    
    items_df = pd.DataFrame(all_items)
    return items_df

def get_top_products(items_df, top_n=20):
    """
    Obtiene los top productos por ventas
    
    Args:
        items_df: DataFrame con line items
        top_n: Número de productos a retornar
        
    Returns:
        DataFrame con ranking de productos
    """
    
    if items_df.empty:
        return pd.DataFrame()
    
    # Agrupar por SKU
    product_summary = items_df.groupby(['sku', 'name']).agg({
        'quantity': 'sum',
        'line_total': 'sum'
    }).reset_index()
    
    # Ordenar por ventas totales
    product_summary = product_summary.sort_values('line_total', ascending=False)
    
    # Calcular % del total
    total_sales = product_summary['line_total'].sum()
    product_summary['pct_total'] = (product_summary['line_total'] / total_sales * 100).round(2)
    
    # Top N
    top_products = product_summary.head(top_n).reset_index(drop=True)
    top_products.index = top_products.index + 1  # Ranking empieza en 1
    
    # Renombrar columnas
    top_products.columns = ['SKU', 'Producto', 'Unidades', 'Ventas (MXN)', '% del Total']
    
    return top_products

def format_product_table(df):
    """
    Formatea la tabla de productos para display
    
    Args:
        df: DataFrame con productos
        
    Returns:
        DataFrame formateado
    """
    
    if df.empty:
        return df
    
    # Formatear columnas numéricas
    df['Ventas (MXN)'] = df['Ventas (MXN)'].apply(lambda x: f"${x:,.2f}")
    df['% del Total'] = df['% del Total'].apply(lambda x: f"{x:.1f}%")
    df['Unidades'] = df['Unidades'].apply(lambda x: f"{int(x):,}")
    
    return df