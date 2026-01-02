import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import pytz
from supabase import create_client, Client
import os
from product_processor import extract_line_items_from_orders, get_top_products, format_product_table

# Configuración de la página
st.set_page_config(
    page_title="Dashboard de Ventas",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Timezone de México
MEXICO_TZ = pytz.timezone('America/Mexico_City')

# Colores por canal
CHANNEL_COLORS = {
    'Amazon': '#FF9900',
    'Mercado Libre': '#FFE600',
    'Shopify': '#96BF48',
    'TikTok': '#000000',
    'Otro': '#CCCCCC'
}

@st.cache_resource
def init_supabase():
    """Inicializar cliente de Supabase"""
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

def get_mexico_now():
    """Obtener hora actual en timezone de México"""
    return datetime.now(MEXICO_TZ)

def get_date_range_filters(start_date, end_date):
    """Convertir fechas a timestamps para filtros"""
    start_datetime = datetime.combine(start_date, datetime.min.time())
    end_datetime = datetime.combine(end_date, datetime.max.time())
    
    start_datetime = MEXICO_TZ.localize(start_datetime)
    end_datetime = MEXICO_TZ.localize(end_datetime)
    
    return start_datetime.isoformat(), end_datetime.isoformat()

@st.cache_data(ttl=300)
def load_orders_data(start_date_iso, end_date_iso):
    """Cargar datos de órdenes desde Supabase"""
    supabase = init_supabase()
    
    response = supabase.table('orders_final')\
        .select('*')\
        .gte('processed_at', start_date_iso)\
        .lte('processed_at', end_date_iso)\
        .execute()
    
    df = pd.DataFrame(response.data)
    
    if not df.empty:
        # Convertir fechas a timezone de México
        # Primero localizar a UTC (timezone de Supabase) y luego convertir a México
        df['processed_at'] = pd.to_datetime(df['processed_at']).dt.tz_localize('UTC').dt.tz_convert(MEXICO_TZ)
        df['created_at'] = pd.to_datetime(df['created_at']).dt.tz_localize('UTC').dt.tz_convert(MEXICO_TZ)
        
        # Crear columna de fecha (sin hora)
        df['date'] = df['processed_at'].dt.date
        
        # Limpiar nombres de canal
        df['channel'] = df['channel_tags'].fillna('Otro').str.strip()
        
        # Asegurar que total_price es numérico
        df['total_price'] = pd.to_numeric(df['total_price'], errors='coerce').fillna(0)
    
    return df

@st.cache_data(ttl=300)
def load_line_items_data(start_date_iso, end_date_iso):
    """Cargar datos de líneas de productos (si existe tabla separada)"""
    # Por ahora, extraeremos productos del JSON en orders_final
    # Si tienes una tabla line_items separada, cambiar esta función
    return pd.DataFrame()

def calculate_kpis(df, period_start, period_end):
    """Calcular KPIs principales"""
    if df.empty:
        return {
            'ventas_total': 0,
            'num_ordenes': 0,
            'ticket_promedio': 0
        }
    
    # Filtrar por período
    mask = (df['date'] >= period_start) & (df['date'] <= period_end)
    period_df = df[mask]
    
    ventas_total = period_df['total_price'].sum()
    num_ordenes = len(period_df)
    ticket_promedio = ventas_total / num_ordenes if num_ordenes > 0 else 0
    
    return {
        'ventas_total': ventas_total,
        'num_ordenes': num_ordenes,
        'ticket_promedio': ticket_promedio
    }

def format_currency(amount):
    """Formatear cantidad como moneda MXN"""
    return f"${amount:,.2f} MXN"

def create_channel_bar_chart(df, title):
    """Crear gráfica de barras por canal"""
    if df.empty:
        return go.Figure()
    
    channel_sales = df.groupby('channel')['total_price'].sum().sort_values(ascending=False)
    
    colors = [CHANNEL_COLORS.get(ch, CHANNEL_COLORS['Otro']) for ch in channel_sales.index]
    
    fig = go.Figure(data=[
        go.Bar(
            y=channel_sales.index,
            x=channel_sales.values,
            orientation='h',
            marker_color=colors,
            text=[format_currency(v) for v in channel_sales.values],
            textposition='auto',
        )
    ])
    
    fig.update_layout(
        title=title,
        xaxis_title="Ventas (MXN)",
        yaxis_title="Canal",
        height=300,
        showlegend=False
    )
    
    return fig

def create_daily_trend_chart(df, title, channel=None):
    """Crear gráfica de tendencia diaria"""
    if df.empty:
        return go.Figure()
    
    if channel:
        df = df[df['channel'] == channel]
    
    daily_sales = df.groupby('date')['total_price'].sum().reset_index()
    daily_sales = daily_sales.sort_values('date')
    
    color = CHANNEL_COLORS.get(channel, '#1f77b4') if channel else '#1f77b4'
    
    fig = go.Figure(data=[
        go.Scatter(
            x=daily_sales['date'],
            y=daily_sales['total_price'],
            mode='lines+markers',
            line=dict(color=color, width=3),
            marker=dict(size=8),
            fill='tozeroy',
            fillcolor=f'rgba{tuple(list(int(color.lstrip("#")[i:i+2], 16) for i in (0, 2, 4)) + [0.2])}'
        )
    ])
    
    fig.update_layout(
        title=title,
        xaxis_title="Fecha",
        yaxis_title="Ventas (MXN)",
        height=400 if not channel else 250,
        showlegend=False
    )
    
    return fig

def show_overview_tab(df, selected_start, selected_end):
    """Mostrar pestaña de overview con métricas"""
    st.header("📊 Overview de Ventas")
    
    # Obtener fechas de hoy y del mes actual
    now = get_mexico_now()
    today = now.date()
    first_day_month = today.replace(day=1)
    
    # Calcular KPIs
    kpis_today = calculate_kpis(df, today, today)
    kpis_month = calculate_kpis(df, first_day_month, today)
    
    # Sección 1: KPIs Cards
    st.subheader("Métricas Principales")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            label="💰 Ventas Hoy",
            value=format_currency(kpis_today['ventas_total'])
        )
    
    with col2:
        st.metric(
            label="💰 Ventas del Mes",
            value=format_currency(kpis_month['ventas_total'])
        )
    
    with col3:
        st.metric(
            label="🎯 Ticket Promedio Mes",
            value=format_currency(kpis_month['ticket_promedio'])
        )
    
    col4, col5, col6 = st.columns(3)
    
    with col4:
        st.metric(
            label="📦 Órdenes Hoy",
            value=f"{kpis_today['num_ordenes']:,}"
        )
    
    with col5:
        st.metric(
            label="📦 Órdenes del Mes",
            value=f"{kpis_month['num_ordenes']:,}"
        )
    
    with col6:
        st.metric(
            label="🎯 Ticket Promedio Hoy",
            value=format_currency(kpis_today['ticket_promedio'])
        )
    
    st.divider()
    
    # Sección 2: Gráficas por Canal
    st.subheader("Ventas por Canal")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Filtrar datos de hoy
        today_df = df[df['date'] == today]
        fig_today = create_channel_bar_chart(today_df, "Ventas de Hoy por Canal")
        st.plotly_chart(fig_today, use_container_width=True, key="chart_today_channel")
    
    with col2:
        # Filtrar datos del mes
        month_df = df[(df['date'] >= first_day_month) & (df['date'] <= today)]
        fig_month = create_channel_bar_chart(month_df, "Ventas del Mes por Canal")
        st.plotly_chart(fig_month, use_container_width=True, key="chart_month_channel")
    
    st.divider()
    
    # Sección 3: Tendencias Temporales
    st.subheader("Tendencias de Ventas")
    
    # Gráfica grande: Total del mes
    month_df = df[(df['date'] >= first_day_month) & (df['date'] <= today)]
    fig_total = create_daily_trend_chart(month_df, "Ventas Diarias del Mes - Total")
    st.plotly_chart(fig_total, use_container_width=True, key="chart_total_trend")
    
    # Gráficas pequeñas por canal
    st.subheader("Tendencias por Canal")
    
    channels = ['Amazon', 'Mercado Libre', 'Shopify', 'TikTok']
    
    col1, col2 = st.columns(2)
    
    for idx, channel in enumerate(channels):
        with col1 if idx % 2 == 0 else col2:
            fig_channel = create_daily_trend_chart(month_df, f"{channel}", channel)
            st.plotly_chart(fig_channel, use_container_width=True, key=f"chart_trend_{channel.lower().replace(' ', '_')}")

def show_top_products_tab(df):
    """Mostrar pestaña de top productos"""
    st.header("🏆 Top Productos")
    
    # Selector de período
    col1, col2 = st.columns([3, 1])
    
    with col1:
        period = st.radio(
            "Seleccionar período:",
            ["Mes Actual", "Año Actual"],
            horizontal=True
        )
    
    with col2:
        top_n = st.number_input(
            "Top N productos:",
            min_value=5,
            max_value=100,
            value=20,
            step=5
        )
    
    # Calcular fechas según período
    now = get_mexico_now()
    today = now.date()
    
    if period == "Mes Actual":
        start_date = today.replace(day=1)
        end_date = today
    else:  # Año Actual
        start_date = today.replace(month=1, day=1)
        end_date = today
    
    # Filtrar datos por período
    period_df = df[(df['date'] >= start_date) & (df['date'] <= end_date)].copy()
    
    if period_df.empty:
        st.warning("No hay datos para el período seleccionado")
        return
    
    # Mostrar resumen del período
    st.caption(f"📅 Período: {start_date.strftime('%d/%m/%Y')} - {end_date.strftime('%d/%m/%Y')}")
    st.caption(f"📦 Total de órdenes: {len(period_df):,}")
    
    # Procesar line items
    with st.spinner("Procesando productos..."):
        try:
            # Extraer line items
            items_df = extract_line_items_from_orders(period_df)
            
            if items_df.empty:
                st.warning("⚠️ No se pudieron extraer productos de las órdenes. Verifica que la columna 'line_items' contenga datos válidos.")
                st.info("**Nota**: La columna 'line_items' debe contener JSON con la información de productos de cada orden.")
                return
            
            # Obtener top productos
            top_products = get_top_products(items_df, top_n=top_n)
            
            if top_products.empty:
                st.warning("No se encontraron productos en el período seleccionado")
                return
            
            # Mostrar métricas resumidas
            col1, col2, col3 = st.columns(3)
            
            with col1:
                total_units = items_df['quantity'].sum()
                st.metric("🔢 Total Unidades Vendidas", f"{int(total_units):,}")
            
            with col2:
                total_revenue = items_df['line_total'].sum()
                st.metric("💰 Ventas Totales", format_currency(total_revenue))
            
            with col3:
                unique_products = items_df['sku'].nunique()
                st.metric("📦 SKUs Únicos", f"{unique_products:,}")
            
            st.divider()
            
            # Mostrar tabla de top productos
            st.subheader(f"Top {top_n} Productos - {period}")
            
            # Formatear para display
            display_df = format_product_table(top_products.copy())
            
            # Agregar columna de ranking
            display_df.insert(0, '#', range(1, len(display_df) + 1))
            
            # Mostrar tabla
            st.dataframe(
                display_df,
                width='stretch',
                hide_index=True,
                column_config={
                    "#": st.column_config.NumberColumn(
                        "Ranking",
                        help="Posición en el ranking",
                        width="small"
                    ),
                    "SKU": st.column_config.TextColumn(
                        "SKU",
                        help="Código del producto",
                        width="medium"
                    ),
                    "Producto": st.column_config.TextColumn(
                        "Nombre del Producto",
                        help="Nombre o descripción del producto",
                        width="large"
                    ),
                    "Unidades": st.column_config.TextColumn(
                        "Unidades",
                        help="Total de unidades vendidas",
                        width="small"
                    ),
                    "Ventas (MXN)": st.column_config.TextColumn(
                        "Ventas Totales",
                        help="Ingresos totales generados",
                        width="medium"
                    ),
                    "% del Total": st.column_config.TextColumn(
                        "% Total",
                        help="Porcentaje del total de ventas",
                        width="small"
                    )
                }
            )
            
            # Gráfica de top 10
            st.subheader("Top 10 Productos - Visualización")
            
            top_10 = top_products.head(10).copy()
            # Revertir orden para que el #1 esté arriba en horizontal bar
            top_10 = top_10.iloc[::-1]
            
            # Convertir ventas a numérico si está como string
            if top_10['Ventas (MXN)'].dtype == 'object':
                top_10['Ventas (MXN)'] = top_10['Ventas (MXN)'].str.replace('$', '').str.replace(',', '').astype(float)
            
            fig = go.Figure(data=[
                go.Bar(
                    y=top_10['Producto'],
                    x=top_10['Ventas (MXN)'],
                    orientation='h',
                    text=[format_currency(v) for v in top_10['Ventas (MXN)']],
                    textposition='auto',
                    marker_color='#FF6B6B'
                )
            ])
            
            fig.update_layout(
                title=f"Top 10 Productos por Ventas - {period}",
                xaxis_title="Ventas (MXN)",
                yaxis_title="Producto",
                height=500,
                showlegend=False
            )
            
            st.plotly_chart(fig, use_container_width=True, key="chart_top_products")
            
        except Exception as e:
            st.error(f"Error al procesar productos: {str(e)}")
            st.info("**Sugerencia**: Verifica que tus órdenes en Supabase tengan la columna 'line_items' con datos en formato JSON válido.")

def main():
    """Función principal de la aplicación"""
    
    # Sidebar con filtros
    with st.sidebar:
        st.title("🎛️ Filtros")
        
        # Selector de rango de fechas
        now = get_mexico_now()
        today = now.date()
        first_day_month = today.replace(day=1)
        
        st.subheader("Rango de Fechas")
        
        date_range = st.date_input(
            "Seleccionar período:",
            value=(first_day_month, today),
            max_value=today,
            key="date_range"
        )
        
        if isinstance(date_range, tuple) and len(date_range) == 2:
            selected_start, selected_end = date_range
        else:
            selected_start = selected_end = today
        
        st.divider()
        
        # Información adicional
        st.subheader("ℹ️ Información")
        st.caption(f"Última actualización: {now.strftime('%Y-%m-%d %H:%M:%S')}")
        st.caption(f"Timezone: America/Mexico_City")
        
        # Botón para refrescar datos
        if st.button("🔄 Refrescar Datos", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
    
    # Título principal
    st.title("📊 Dashboard de Ventas - Shopify")
    
    # Cargar datos
    with st.spinner("Cargando datos..."):
        start_iso, end_iso = get_date_range_filters(selected_start, selected_end)
        df = load_orders_data(start_iso, end_iso)
    
    if df.empty:
        st.error("No se encontraron datos para el período seleccionado")
        return
    
    # Tabs principales
    tab1, tab2 = st.tabs(["📈 Overview", "🏆 Top Productos"])
    
    with tab1:
        show_overview_tab(df, selected_start, selected_end)
    
    with tab2:
        show_top_products_tab(df)

if __name__ == "__main__":
    main()










# import streamlit as st
# import pandas as pd
# import plotly.express as px
# import plotly.graph_objects as go
# from datetime import datetime, timedelta
# import pytz
# from supabase import create_client, Client
# import os
# from product_processor import extract_line_items_from_orders, get_top_products, format_product_table

# # Configuración de la página
# st.set_page_config(
#     page_title="Dashboard de Ventas",
#     page_icon="📊",
#     layout="wide",
#     initial_sidebar_state="expanded"
# )

# # Timezone de México
# MEXICO_TZ = pytz.timezone('America/Mexico_City')

# # Colores por canal
# CHANNEL_COLORS = {
#     'Amazon': '#FF9900',
#     'Mercado Libre': '#FFE600',
#     'Shopify': '#96BF48',
#     'TikTok': '#000000',
#     'Otro': '#CCCCCC'
# }

# @st.cache_resource
# def init_supabase():
#     """Inicializar cliente de Supabase"""
#     url = st.secrets["SUPABASE_URL"]
#     key = st.secrets["SUPABASE_KEY"]
#     return create_client(url, key)

# def get_mexico_now():
#     """Obtener hora actual en timezone de México"""
#     return datetime.now(MEXICO_TZ)

# def get_date_range_filters(start_date, end_date):
#     """Convertir fechas a timestamps para filtros"""
#     start_datetime = datetime.combine(start_date, datetime.min.time())
#     end_datetime = datetime.combine(end_date, datetime.max.time())
    
#     start_datetime = MEXICO_TZ.localize(start_datetime)
#     end_datetime = MEXICO_TZ.localize(end_datetime)
    
#     return start_datetime.isoformat(), end_datetime.isoformat()

# @st.cache_data(ttl=300)
# def load_orders_data(start_date_iso, end_date_iso):
#     """Cargar datos de órdenes desde Supabase"""
#     supabase = init_supabase()
    
#     response = supabase.table('orders_final')\
#         .select('*')\
#         .gte('processed_at', start_date_iso)\
#         .lte('processed_at', end_date_iso)\
#         .execute()
    
#     df = pd.DataFrame(response.data)
    
#     if not df.empty:
#         # Convertir fechas a timezone de México
#         df['processed_at'] = pd.to_datetime(df['processed_at']).dt.tz_convert(MEXICO_TZ)
#         df['created_at'] = pd.to_datetime(df['created_at']).dt.tz_convert(MEXICO_TZ)
        
#         # Crear columna de fecha (sin hora)
#         df['date'] = df['processed_at'].dt.date
        
#         # Limpiar nombres de canal
#         df['channel'] = df['channel_tags'].fillna('Otro').str.strip()
        
#         # Asegurar que total_price es numérico
#         df['total_price'] = pd.to_numeric(df['total_price'], errors='coerce').fillna(0)
    
#     return df

# @st.cache_data(ttl=300)
# def load_line_items_data(start_date_iso, end_date_iso):
#     """Cargar datos de líneas de productos (si existe tabla separada)"""
#     # Por ahora, extraeremos productos del JSON en orders_final
#     # Si tienes una tabla line_items separada, cambiar esta función
#     return pd.DataFrame()

# def calculate_kpis(df, period_start, period_end):
#     """Calcular KPIs principales"""
#     if df.empty:
#         return {
#             'ventas_total': 0,
#             'num_ordenes': 0,
#             'ticket_promedio': 0
#         }
    
#     # Filtrar por período
#     mask = (df['date'] >= period_start) & (df['date'] <= period_end)
#     period_df = df[mask]
    
#     ventas_total = period_df['total_price'].sum()
#     num_ordenes = len(period_df)
#     ticket_promedio = ventas_total / num_ordenes if num_ordenes > 0 else 0
    
#     return {
#         'ventas_total': ventas_total,
#         'num_ordenes': num_ordenes,
#         'ticket_promedio': ticket_promedio
#     }

# def format_currency(amount):
#     """Formatear cantidad como moneda MXN"""
#     return f"${amount:,.2f} MXN"

# def create_channel_bar_chart(df, title):
#     """Crear gráfica de barras por canal"""
#     if df.empty:
#         return go.Figure()
    
#     channel_sales = df.groupby('channel')['total_price'].sum().sort_values(ascending=False)
    
#     colors = [CHANNEL_COLORS.get(ch, CHANNEL_COLORS['Otro']) for ch in channel_sales.index]
    
#     fig = go.Figure(data=[
#         go.Bar(
#             y=channel_sales.index,
#             x=channel_sales.values,
#             orientation='h',
#             marker_color=colors,
#             text=[format_currency(v) for v in channel_sales.values],
#             textposition='auto',
#         )
#     ])
    
#     fig.update_layout(
#         title=title,
#         xaxis_title="Ventas (MXN)",
#         yaxis_title="Canal",
#         height=300,
#         showlegend=False
#     )
    
#     return fig

# def create_daily_trend_chart(df, title, channel=None):
#     """Crear gráfica de tendencia diaria"""
#     if df.empty:
#         return go.Figure()
    
#     if channel:
#         df = df[df['channel'] == channel]
    
#     daily_sales = df.groupby('date')['total_price'].sum().reset_index()
#     daily_sales = daily_sales.sort_values('date')
    
#     color = CHANNEL_COLORS.get(channel, '#1f77b4') if channel else '#1f77b4'
    
#     fig = go.Figure(data=[
#         go.Scatter(
#             x=daily_sales['date'],
#             y=daily_sales['total_price'],
#             mode='lines+markers',
#             line=dict(color=color, width=3),
#             marker=dict(size=8),
#             fill='tozeroy',
#             fillcolor=f'rgba{tuple(list(int(color.lstrip("#")[i:i+2], 16) for i in (0, 2, 4)) + [0.2])}'
#         )
#     ])
    
#     fig.update_layout(
#         title=title,
#         xaxis_title="Fecha",
#         yaxis_title="Ventas (MXN)",
#         height=400 if not channel else 250,
#         showlegend=False
#     )
    
#     return fig

# def show_overview_tab(df, selected_start, selected_end):
#     """Mostrar pestaña de overview con métricas"""
#     st.header("📊 Overview de Ventas")
    
#     # Obtener fechas de hoy y del mes actual
#     now = get_mexico_now()
#     today = now.date()
#     first_day_month = today.replace(day=1)
    
#     # Calcular KPIs
#     kpis_today = calculate_kpis(df, today, today)
#     kpis_month = calculate_kpis(df, first_day_month, today)
    
#     # Sección 1: KPIs Cards
#     st.subheader("Métricas Principales")
    
#     col1, col2, col3 = st.columns(3)
    
#     with col1:
#         st.metric(
#             label="💰 Ventas Hoy",
#             value=format_currency(kpis_today['ventas_total'])
#         )
    
#     with col2:
#         st.metric(
#             label="💰 Ventas del Mes",
#             value=format_currency(kpis_month['ventas_total'])
#         )
    
#     with col3:
#         st.metric(
#             label="🎯 Ticket Promedio Mes",
#             value=format_currency(kpis_month['ticket_promedio'])
#         )
    
#     col4, col5, col6 = st.columns(3)
    
#     with col4:
#         st.metric(
#             label="📦 Órdenes Hoy",
#             value=f"{kpis_today['num_ordenes']:,}"
#         )
    
#     with col5:
#         st.metric(
#             label="📦 Órdenes del Mes",
#             value=f"{kpis_month['num_ordenes']:,}"
#         )
    
#     with col6:
#         st.metric(
#             label="🎯 Ticket Promedio Hoy",
#             value=format_currency(kpis_today['ticket_promedio'])
#         )
    
#     st.divider()
    
#     # Sección 2: Gráficas por Canal
#     st.subheader("Ventas por Canal")
    
#     col1, col2 = st.columns(2)
    
#     with col1:
#         # Filtrar datos de hoy
#         today_df = df[df['date'] == today]
#         fig_today = create_channel_bar_chart(today_df, "Ventas de Hoy por Canal")
#         st.plotly_chart(fig_today, use_container_width=True)
    
#     with col2:
#         # Filtrar datos del mes
#         month_df = df[(df['date'] >= first_day_month) & (df['date'] <= today)]
#         fig_month = create_channel_bar_chart(month_df, "Ventas del Mes por Canal")
#         st.plotly_chart(fig_month, use_container_width=True)
    
#     st.divider()
    
#     # Sección 3: Tendencias Temporales
#     st.subheader("Tendencias de Ventas")
    
#     # Gráfica grande: Total del mes
#     month_df = df[(df['date'] >= first_day_month) & (df['date'] <= today)]
#     fig_total = create_daily_trend_chart(month_df, "Ventas Diarias del Mes - Total")
#     st.plotly_chart(fig_total, use_container_width=True)
    
#     # Gráficas pequeñas por canal
#     st.subheader("Tendencias por Canal")
    
#     channels = ['Amazon', 'Mercado Libre', 'Shopify', 'TikTok']
    
#     col1, col2 = st.columns(2)
    
#     for idx, channel in enumerate(channels):
#         with col1 if idx % 2 == 0 else col2:
#             fig_channel = create_daily_trend_chart(month_df, f"{channel}", channel)
#             st.plotly_chart(fig_channel, use_container_width=True)

# def show_top_products_tab(df):
#     """Mostrar pestaña de top productos"""
#     st.header("🏆 Top Productos")
    
#     # Selector de período
#     col1, col2 = st.columns([3, 1])
    
#     with col1:
#         period = st.radio(
#             "Seleccionar período:",
#             ["Mes Actual", "Año Actual"],
#             horizontal=True
#         )
    
#     with col2:
#         top_n = st.number_input(
#             "Top N productos:",
#             min_value=5,
#             max_value=100,
#             value=20,
#             step=5
#         )
    
#     # Calcular fechas según período
#     now = get_mexico_now()
#     today = now.date()
    
#     if period == "Mes Actual":
#         start_date = today.replace(day=1)
#         end_date = today
#     else:  # Año Actual
#         start_date = today.replace(month=1, day=1)
#         end_date = today
    
#     # Filtrar datos por período
#     period_df = df[(df['date'] >= start_date) & (df['date'] <= end_date)].copy()
    
#     if period_df.empty:
#         st.warning("No hay datos para el período seleccionado")
#         return
    
#     # Mostrar resumen del período
#     st.caption(f"📅 Período: {start_date.strftime('%d/%m/%Y')} - {end_date.strftime('%d/%m/%Y')}")
#     st.caption(f"📦 Total de órdenes: {len(period_df):,}")
    
#     # Procesar line items
#     with st.spinner("Procesando productos..."):
#         try:
#             # Extraer line items
#             items_df = extract_line_items_from_orders(period_df)
            
#             if items_df.empty:
#                 st.warning("⚠️ No se pudieron extraer productos de las órdenes. Verifica que la columna 'line_items' contenga datos válidos.")
#                 st.info("**Nota**: La columna 'line_items' debe contener JSON con la información de productos de cada orden.")
#                 return
            
#             # Obtener top productos
#             top_products = get_top_products(items_df, top_n=top_n)
            
#             if top_products.empty:
#                 st.warning("No se encontraron productos en el período seleccionado")
#                 return
            
#             # Mostrar métricas resumidas
#             col1, col2, col3 = st.columns(3)
            
#             with col1:
#                 total_units = items_df['quantity'].sum()
#                 st.metric("🔢 Total Unidades Vendidas", f"{int(total_units):,}")
            
#             with col2:
#                 total_revenue = items_df['line_total'].sum()
#                 st.metric("💰 Ventas Totales", format_currency(total_revenue))
            
#             with col3:
#                 unique_products = items_df['sku'].nunique()
#                 st.metric("📦 SKUs Únicos", f"{unique_products:,}")
            
#             st.divider()
            
#             # Mostrar tabla de top productos
#             st.subheader(f"Top {top_n} Productos - {period}")
            
#             # Formatear para display
#             display_df = format_product_table(top_products.copy())
            
#             # Agregar columna de ranking
#             display_df.insert(0, '#', range(1, len(display_df) + 1))
            
#             # Mostrar tabla
#             st.dataframe(
#                 display_df,
#                 use_container_width=True,
#                 hide_index=True,
#                 column_config={
#                     "#": st.column_config.NumberColumn(
#                         "Ranking",
#                         help="Posición en el ranking",
#                         width="small"
#                     ),
#                     "SKU": st.column_config.TextColumn(
#                         "SKU",
#                         help="Código del producto",
#                         width="medium"
#                     ),
#                     "Producto": st.column_config.TextColumn(
#                         "Nombre del Producto",
#                         help="Nombre o descripción del producto",
#                         width="large"
#                     ),
#                     "Unidades": st.column_config.TextColumn(
#                         "Unidades",
#                         help="Total de unidades vendidas",
#                         width="small"
#                     ),
#                     "Ventas (MXN)": st.column_config.TextColumn(
#                         "Ventas Totales",
#                         help="Ingresos totales generados",
#                         width="medium"
#                     ),
#                     "% del Total": st.column_config.TextColumn(
#                         "% Total",
#                         help="Porcentaje del total de ventas",
#                         width="small"
#                     )
#                 }
#             )
            
#             # Gráfica de top 10
#             st.subheader("Top 10 Productos - Visualización")
            
#             top_10 = top_products.head(10).copy()
#             # Revertir orden para que el #1 esté arriba en horizontal bar
#             top_10 = top_10.iloc[::-1]
            
#             # Convertir ventas a numérico si está como string
#             if top_10['Ventas (MXN)'].dtype == 'object':
#                 top_10['Ventas (MXN)'] = top_10['Ventas (MXN)'].str.replace('$', '').str.replace(',', '').astype(float)
            
#             fig = go.Figure(data=[
#                 go.Bar(
#                     y=top_10['Producto'],
#                     x=top_10['Ventas (MXN)'],
#                     orientation='h',
#                     text=[format_currency(v) for v in top_10['Ventas (MXN)']],
#                     textposition='auto',
#                     marker_color='#FF6B6B'
#                 )
#             ])
            
#             fig.update_layout(
#                 title=f"Top 10 Productos por Ventas - {period}",
#                 xaxis_title="Ventas (MXN)",
#                 yaxis_title="Producto",
#                 height=500,
#                 showlegend=False
#             )
            
#             st.plotly_chart(fig, use_container_width=True)
            
#         except Exception as e:
#             st.error(f"Error al procesar productos: {str(e)}")
#             st.info("**Sugerencia**: Verifica que tus órdenes en Supabase tengan la columna 'line_items' con datos en formato JSON válido.")

# def main():
#     """Función principal de la aplicación"""
    
#     # Sidebar con filtros
#     with st.sidebar:
#         st.title("🎛️ Filtros")
        
#         # Selector de rango de fechas
#         now = get_mexico_now()
#         today = now.date()
#         first_day_month = today.replace(day=1)
        
#         st.subheader("Rango de Fechas")
        
#         date_range = st.date_input(
#             "Seleccionar período:",
#             value=(first_day_month, today),
#             max_value=today,
#             key="date_range"
#         )
        
#         if isinstance(date_range, tuple) and len(date_range) == 2:
#             selected_start, selected_end = date_range
#         else:
#             selected_start = selected_end = today
        
#         st.divider()
        
#         # Información adicional
#         st.subheader("ℹ️ Información")
#         st.caption(f"Última actualización: {now.strftime('%Y-%m-%d %H:%M:%S')}")
#         st.caption(f"Timezone: America/Mexico_City")
        
#         # Botón para refrescar datos
#         if st.button("🔄 Refrescar Datos", use_container_width=True):
#             st.cache_data.clear()
#             st.rerun()
    
#     # Título principal
#     st.title("📊 Dashboard de Ventas - Shopify")
    
#     # Cargar datos
#     with st.spinner("Cargando datos..."):
#         start_iso, end_iso = get_date_range_filters(selected_start, selected_end)
#         df = load_orders_data(start_iso, end_iso)
    
#     if df.empty:
#         st.error("No se encontraron datos para el período seleccionado")
#         return
    
#     # Tabs principales
#     tab1, tab2 = st.tabs(["📈 Overview", "🏆 Top Productos"])
    
#     with tab1:
#         show_overview_tab(df, selected_start, selected_end)
    
#     with tab2:
#         show_top_products_tab(df)

# if __name__ == "__main__":
#     main()