import streamlit as st
import pandas as pd
import gspread
import json
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from google.oauth2.service_account import Credentials

st.set_page_config(
    page_title="Econatura Costos y Precios",
    page_icon="logoweb.png",
    layout="wide"
)

LOGO_FILE = "logoweb.png"


def mostrar_encabezado(subtitulo=None):
    col1, col2 = st.columns([1, 8], vertical_alignment="center")

    with col1:
        st.image(LOGO_FILE, width=85)

    with col2:
        st.title("Econatura Costos y Precios")
        if subtitulo:
            st.write(subtitulo)


SPREADSHEET_ID = "16saFgtT5ihWJmm7hZU222k6hJ42U6DpPzk7r4F5oVWE"

def verificar_password():
    if st.session_state.get("password_correct", False):
        return True

    mostrar_encabezado()
    st.subheader("Acceso privado")

    password = st.text_input("Contraseña", type="password")

    if st.button("Entrar"):
        if password == st.secrets["app"]["password"]:
            st.session_state["password_correct"] = True
            st.rerun()
        else:
            st.error("Contraseña incorrecta.")

    st.stop()


verificar_password()


def obtener_credenciales_google():
    try:
        raw_json = st.secrets["gcp"]["service_account_json"]
    except KeyError:
        st.error(
            "Falta configurar el secreto [gcp] service_account_json en Streamlit Secrets."
        )
        st.stop()

    try:
        creds_dict = json.loads(raw_json)
    except json.JSONDecodeError:
        st.error(
            "El JSON de la cuenta de servicio no está en formato válido. "
            "Verifica que pegaste el JSON completo dentro de service_account_json."
        )
        st.stop()

    return creds_dict


def limpiar_numero(valor):
    if pd.isna(valor):
        return None

    valor = str(valor)
    valor = valor.replace("$", "")
    valor = valor.replace(",", "")
    valor = valor.strip()

    if valor in ["", "None", "nan"]:
        return None

    return pd.to_numeric(valor, errors="coerce")

def limpiar_porcentaje(valor):
    if pd.isna(valor):
        return 0

    texto = str(valor).replace("%", "").replace(",", "").strip()

    if texto in ["", "None", "nan"]:
        return 0

    numero = pd.to_numeric(texto, errors="coerce")

    if pd.isna(numero):
        return 0

    if numero > 1:
        return numero / 100

    return numero


def obtener_columna(df, posibles_nombres):
    for nombre in posibles_nombres:
        if nombre in df.columns:
            return nombre
    return None


@st.cache_data(ttl=60)
def cargar_productos():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets.readonly",
        "https://www.googleapis.com/auth/drive.readonly"
    ]

    creds_dict = obtener_credenciales_google()

    credentials = Credentials.from_service_account_info(
        creds_dict,
        scopes=scopes
    )

    client = gspread.authorize(credentials)
    spreadsheet = client.open_by_key(SPREADSHEET_ID)

    worksheet = spreadsheet.worksheet("Productos")

    rows = worksheet.get_all_values()

    headers = rows[2]
    data = rows[3:]

    df = pd.DataFrame(data, columns=headers)

    df.columns = [
        str(col).strip().replace("\n", " ").replace("  ", " ")
        for col in df.columns
    ]

    df = df[df["Artículo"].astype(str).str.strip() != ""]

    columnas_dinero = [
        "Costo capsula o empaque",
        "Costo capsula empaque",
        "Costo Producto oz",
        "Costo Label",
        "Costo Empaque",
        "Costo producto",
        "Precio de venta",
        "Ganancia por Producto",
        "Costo total",
        "Ganancia total"
    ]

    for col in columnas_dinero:
        if col in df.columns:
            df[col] = df[col].apply(limpiar_numero)

    if "Cantidad a calcular" in df.columns:
        df["Cantidad a calcular"] = df["Cantidad a calcular"].apply(limpiar_numero)

    if "Margen de ganancia" in df.columns:
        df["Margen de ganancia"] = df["Margen de ganancia"].apply(limpiar_porcentaje)

    return df.reset_index(drop=True)


def calcular_productos(df):
    df = df.copy()

    col_capsula = obtener_columna(df, [
        "Costo capsula o empaque",
        "Costo capsula empaque"
    ])

    columnas_base = [
        col_capsula,
        "Costo Producto oz",
        "Costo Label",
        "Costo Empaque"
    ]

    columnas_base = [col for col in columnas_base if col is not None]

    for col in [
        "Costo producto",
        "Cantidad a calcular",
        "Margen de ganancia",
        "Precio de venta",
        "Ganancia por Producto",
        "Costo total",
        "Ganancia total"
    ]:
        if col not in df.columns:
            df[col] = 0

    for i, row in df.iterrows():
        costo_producto = row.get("Costo producto", 0)

        if pd.isna(costo_producto) or costo_producto == 0:
            costo_producto = 0

            for col in columnas_base:
                valor = row.get(col, 0)
                if not pd.isna(valor):
                    costo_producto += valor

        cantidad = row.get("Cantidad a calcular", 1)
        margen = row.get("Margen de ganancia", 0)
        precio_venta = row.get("Precio de venta", 0)

        cantidad = 1 if pd.isna(cantidad) or cantidad == 0 else cantidad
        margen = 0 if pd.isna(margen) else margen

        if pd.isna(precio_venta) or precio_venta == 0:
            precio_venta = costo_producto * (1 + margen)

        ganancia_unidad = precio_venta - costo_producto
        costo_total = costo_producto * cantidad
        ganancia_total = ganancia_unidad * cantidad
        ingreso_total = precio_venta * cantidad

        df.at[i, "Costo producto"] = costo_producto
        df.at[i, "Precio de venta"] = precio_venta
        df.at[i, "Ganancia por Producto"] = ganancia_unidad
        df.at[i, "Costo total"] = costo_total
        df.at[i, "Ganancia total"] = ganancia_total
        df.at[i, "Ingreso total"] = ingreso_total
        df.at[i, "Margen %"] = margen * 100

    return df


def generar_pdf_productos(df):
    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(letter),
        rightMargin=24,
        leftMargin=24,
        topMargin=24,
        bottomMargin=24
    )

    styles = getSampleStyleSheet()
    elements = []

    titulo = Paragraph("Econatura Costos y Precios - Reporte de Productos", styles["Title"])
    elements.append(titulo)
    elements.append(Spacer(1, 12))

    columnas_pdf = [
        "Categoría",
        "Artículo",
        "Costo producto",
        "Cantidad a calcular",
        "Margen %",
        "Precio de venta",
        "Ganancia por Producto",
        "Costo total",
        "Ganancia total",
        "Ingreso total"
    ]

    df_pdf = df[[col for col in columnas_pdf if col in df.columns]].copy()

    for col in [
        "Costo producto",
        "Precio de venta",
        "Ganancia por Producto",
        "Costo total",
        "Ganancia total",
        "Ingreso total"
    ]:
        if col in df_pdf.columns:
            df_pdf[col] = df_pdf[col].apply(
                lambda x: f"${x:,.2f}" if pd.notna(x) else ""
            )

    if "Margen %" in df_pdf.columns:
        df_pdf["Margen %"] = df_pdf["Margen %"].apply(
            lambda x: f"{x:,.2f}%" if pd.notna(x) else ""
        )

    data = [df_pdf.columns.tolist()] + df_pdf.values.tolist()

    table = Table(data, repeatRows=1)

    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f4e78")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#EAF6FA")),
        ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))

    elements.append(table)

    doc.build(elements)

    buffer.seek(0)
    return buffer
@st.cache_data(ttl=60)
def cargar_inventario():
    scopes = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly"
]

    creds_dict = obtener_credenciales_google()

    credentials = Credentials.from_service_account_info(
        creds_dict,
        scopes=scopes
    )

    client = gspread.authorize(credentials)
    spreadsheet = client.open_by_key(SPREADSHEET_ID)

    worksheet = spreadsheet.get_worksheet(0)

    rows = worksheet.get_all_values()

    headers = rows[3]
    data = rows[4:]

    df = pd.DataFrame(data, columns=headers)

    df.columns = [
        str(col).strip().replace("  ", " ")
        for col in df.columns
    ]

    df = df[df["Categoría"].astype(str).str.strip() != ""]
    df = df[df["Categoría"] != "TOTAL COSTOS REGISTRADOS"]

    columnas_numericas = [
        "Costo compra",
        "Cantidad compra",
        "Costo unitario",
        "Costo por onza",
        "Costo por libra",
    ]

    for col in columnas_numericas:
        if col in df.columns:
            df[col] = df[col].apply(limpiar_numero)

    return df.reset_index(drop=True)


def recalcular_costos(df):
    df = df.copy()

    for i, row in df.iterrows():
        costo = row.get("Costo compra", 0)
        cantidad = row.get("Cantidad compra", 0)
        unidad = str(row.get("Unidad medida", "")).lower()

        if pd.isna(costo) or pd.isna(cantidad) or cantidad == 0:
            continue

        if "libra" in unidad:
            df.at[i, "Costo por onza"] = costo / (cantidad * 16)
            df.at[i, "Costo por libra"] = costo / cantidad
            df.at[i, "Costo unitario"] = None

        elif "onza" in unidad:
            df.at[i, "Costo por onza"] = costo / cantidad
            df.at[i, "Costo por libra"] = (costo / cantidad) * 16
            df.at[i, "Costo unitario"] = None

        elif "unidad" in unidad or "label" in unidad:
            df.at[i, "Costo unitario"] = costo / cantidad
            df.at[i, "Costo por onza"] = None
            df.at[i, "Costo por libra"] = None

    return df


mostrar_encabezado(
    "Sistema privado para calcular costos, precios de venta, ganancias y márgenes."
)

if st.button("🔄 Actualizar datos desde Google Sheets"):
    st.cache_data.clear()
    st.rerun()


inventario = cargar_inventario()
inventario = recalcular_costos(inventario)


tab1, tab2, tab3 = st.tabs([
    "📋 Inventario / Costos",
    "💰 Precios y Ganancia",
    "📊 Resumen"
])


with tab1:
    st.subheader("Inventario base")

    st.write(
        "Esta tabla viene directamente de Google Sheets. "
        "Los cambios realizados en Google Sheets se reflejan aquí al actualizar."
    )

    inventario_editado = st.data_editor(
        inventario,
        use_container_width=True,
        num_rows="dynamic",
        column_config={
            "Costo compra": st.column_config.NumberColumn("Costo compra", format="$%.2f"),
            "Cantidad compra": st.column_config.NumberColumn("Cantidad compra", format="%.2f"),
            "Costo unitario": st.column_config.NumberColumn("Costo unitario", format="$%.4f"),
            "Costo por onza": st.column_config.NumberColumn("Costo por onza", format="$%.4f"),
            "Costo por libra": st.column_config.NumberColumn("Costo por libra", format="$%.4f"),
        }
    )

    inventario_editado = recalcular_costos(inventario_editado)

    st.download_button(
        "⬇️ Descargar inventario CSV",
        data=inventario_editado.to_csv(index=False).encode("utf-8"),
        file_name="inventario_costos.csv",
        mime="text/csv"
    )


with tab2:
    st.subheader("Cálculo de precio de venta y ganancia")

    productos = inventario_editado["Artículo"].dropna().tolist()

    ventas_inicial = pd.DataFrame([
        {
            "Producto Venta": "Bicarbonato 100 cápsulas",
            "Ingrediente Principal": "Bicarbonato",
            "Cantidad Usada": 3.0,
            "Unidad Usada": "oz",
            "Cápsulas Usadas": 100,
            "Costo Empaque": 0.30,
            "Costo Label": 0.30,
            "Otros Costos": 0.00,
            "Precio Venta": 15.00
        },
        {
            "Producto Venta": "Cúrcuma 100 cápsulas",
            "Ingrediente Principal": "Cúrcuma",
            "Cantidad Usada": 1.0,
            "Unidad Usada": "oz",
            "Cápsulas Usadas": 100,
            "Costo Empaque": 0.30,
            "Costo Label": 0.30,
            "Otros Costos": 0.00,
            "Precio Venta": 15.00
        }
    ])

    ventas = st.data_editor(
        ventas_inicial,
        use_container_width=True,
        num_rows="dynamic",
        column_config={
            "Ingrediente Principal": st.column_config.SelectboxColumn(
                "Ingrediente Principal",
                options=productos
            ),
            "Unidad Usada": st.column_config.SelectboxColumn(
                "Unidad Usada",
                options=["oz", "lb", "unidad"]
            ),
            "Cantidad Usada": st.column_config.NumberColumn(format="%.2f"),
            "Cápsulas Usadas": st.column_config.NumberColumn(format="%d"),
            "Costo Empaque": st.column_config.NumberColumn(format="$%.2f"),
            "Costo Label": st.column_config.NumberColumn(format="$%.2f"),
            "Otros Costos": st.column_config.NumberColumn(format="$%.2f"),
            "Precio Venta": st.column_config.NumberColumn(format="$%.2f"),
        }
    )

    costos = inventario_editado.set_index("Artículo").to_dict("index")

    resultados = []

    for _, row in ventas.iterrows():
        producto_venta = row.get("Producto Venta")
        ingrediente = row.get("Ingrediente Principal")

        if pd.isna(producto_venta) or pd.isna(ingrediente):
            continue

        data_producto = costos.get(ingrediente, {})
        unidad_usada = row.get("Unidad Usada", "oz")

        if unidad_usada == "oz":
            costo_base = data_producto.get("Costo por onza", 0)
        elif unidad_usada == "lb":
            costo_base = data_producto.get("Costo por libra", 0)
        else:
            costo_base = data_producto.get("Costo unitario", 0)

        if pd.isna(costo_base):
            costo_base = 0

        cantidad_usada = row.get("Cantidad Usada", 0)
        capsulas_usadas = row.get("Cápsulas Usadas", 0)
        costo_empaque = row.get("Costo Empaque", 0)
        costo_label = row.get("Costo Label", 0)
        otros_costos = row.get("Otros Costos", 0)
        precio_venta = row.get("Precio Venta", 0)

        cantidad_usada = 0 if pd.isna(cantidad_usada) else cantidad_usada
        capsulas_usadas = 0 if pd.isna(capsulas_usadas) else capsulas_usadas
        costo_empaque = 0 if pd.isna(costo_empaque) else costo_empaque
        costo_label = 0 if pd.isna(costo_label) else costo_label
        otros_costos = 0 if pd.isna(otros_costos) else otros_costos
        precio_venta = 0 if pd.isna(precio_venta) else precio_venta

        costo_ingrediente = costo_base * cantidad_usada

        data_capsulas = costos.get("Cápsulas", {})
        costo_capsula = data_capsulas.get("Costo unitario", 0)
        costo_capsula = 0 if pd.isna(costo_capsula) else costo_capsula

        costo_capsulas = costo_capsula * capsulas_usadas

        costo_total = (
            costo_ingrediente
            + costo_capsulas
            + costo_empaque
            + costo_label
            + otros_costos
        )

        ganancia = precio_venta - costo_total
        margen = (ganancia / precio_venta) * 100 if precio_venta > 0 else 0

        resultados.append({
            "Producto Venta": producto_venta,
            "Ingrediente Principal": ingrediente,
            "Costo Ingrediente": costo_ingrediente,
            "Costo Cápsulas": costo_capsulas,
            "Costo Empaque": costo_empaque,
            "Costo Label": costo_label,
            "Otros Costos": otros_costos,
            "Costo Total": costo_total,
            "Precio Venta": precio_venta,
            "Ganancia": ganancia,
            "Margen %": margen
        })

    resultados_df = pd.DataFrame(resultados)

    st.subheader("Resultados")

    if not resultados_df.empty:
        st.dataframe(
            resultados_df.style.format({
                "Costo Ingrediente": "${:.2f}",
                "Costo Cápsulas": "${:.2f}",
                "Costo Empaque": "${:.2f}",
                "Costo Label": "${:.2f}",
                "Otros Costos": "${:.2f}",
                "Costo Total": "${:.2f}",
                "Precio Venta": "${:.2f}",
                "Ganancia": "${:.2f}",
                "Margen %": "{:.2f}%"
            }),
            use_container_width=True
        )

        st.download_button(
            "⬇️ Descargar tabla de ganancias CSV",
            data=resultados_df.to_csv(index=False).encode("utf-8"),
            file_name="precios_ganancias.csv",
            mime="text/csv"
        )
    else:
        st.warning("No hay productos de venta para calcular.")


with tab3:
    st.subheader("Resumen general")

    total_costos = inventario_editado["Costo compra"].sum()

    st.metric("Costo total registrado", f"${total_costos:,.2f}")

    if "resultados_df" in locals() and not resultados_df.empty:
        st.metric("Ganancia promedio", f"${resultados_df['Ganancia'].mean():,.2f}")
        st.metric("Margen promedio", f"{resultados_df['Margen %'].mean():.2f}%")

    st.info(
        "La información viene desde Google Sheets privado. "
        "Para ver cambios recientes, presiona el botón de actualizar datos."
    )
