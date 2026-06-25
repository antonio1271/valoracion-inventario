import streamlit as st
import pandas as pd

st.set_page_config(
    page_title="Valoración de Inventario",
    layout="wide"
)

EXCEL_FILE = "inventario.xlsx"

st.title("📦 Valoración de Inventario")
st.write("Sistema para calcular costos, precios de venta, ganancias y márgenes.")

@st.cache_data
def cargar_inventario():
    df_raw = pd.read_excel(EXCEL_FILE, sheet_name="Costos", header=None)

    headers = df_raw.iloc[3].tolist()
    df = df_raw.iloc[4:].copy()
    df.columns = headers

    df = df[df["Categoría"].notna()]
    df = df[df["Categoría"] != "TOTAL COSTOS REGISTRADOS"]

    columnas = [
        "Costo compra",
        "Cantidad compra",
        "Costo unitario",
        "Costo por  onza",
        "Costo por libra"
    ]

    for col in columnas:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

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
            df.at[i, "Costo por  onza"] = costo / (cantidad * 16)
            df.at[i, "Costo por libra"] = costo / cantidad
            df.at[i, "Costo unitario"] = None

        elif "onza" in unidad:
            df.at[i, "Costo por  onza"] = costo / cantidad
            df.at[i, "Costo por libra"] = (costo / cantidad) * 16
            df.at[i, "Costo unitario"] = None

        elif "unidad" in unidad or "label" in unidad:
            df.at[i, "Costo unitario"] = costo / cantidad
            df.at[i, "Costo por  onza"] = None
            df.at[i, "Costo por libra"] = None

    return df


inventario = cargar_inventario()
inventario = recalcular_costos(inventario)

tab1, tab2, tab3 = st.tabs([
    "📋 Inventario / Costos",
    "💰 Precios y Ganancia",
    "📊 Resumen"
])

with tab1:
    st.subheader("Inventario base")

    st.write("Esta tabla viene de tu archivo Excel final. Puedes editar los datos para probar escenarios.")

    inventario_editado = st.data_editor(
        inventario,
        use_container_width=True,
        num_rows="dynamic",
        column_config={
            "Costo compra": st.column_config.NumberColumn("Costo compra", format="$%.2f"),
            "Cantidad compra": st.column_config.NumberColumn("Cantidad compra", format="%.2f"),
            "Costo unitario": st.column_config.NumberColumn("Costo unitario", format="$%.4f"),
            "Costo por  onza": st.column_config.NumberColumn("Costo por onza", format="$%.4f"),
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
            costo_base = data_producto.get("Costo por  onza", 0)
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

    st.info("Esta versión usa el Excel como base. Los cambios editados en la app son temporales.")
