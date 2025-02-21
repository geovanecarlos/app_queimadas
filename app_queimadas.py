import streamlit as st
from streamlit_folium import folium_static
from st_social_media_links import SocialMediaIcons
import pandas as pd
import locale
locale.setlocale(locale.LC_TIME, 'Portuguese_Brazil.1252')  # Para Windows
import geopandas as gpd
import plotly.express as px
import plotly.graph_objects as go
import folium
from folium.plugins import HeatMap
from folium.features import FeatureGroup

# Configuração do Layout do APP
def layouts():
    st.set_page_config(
    page_title="Monitoramento de Queimadas em Itajubá-MG",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="expanded"
)
    
if __name__ == "__main__":
    layouts()

# Carregando os dados
@st.cache_data
def load_data():
    queimadas_shp = gpd.read_file("dataset/focos de queimadas 2019_22.shp")
    anos = ['19', '20', '21', '22'] # Adicionando a coluna total dos focos
    queimadas_shp['focos_total'] = sum(queimadas_shp[f'focos_{ano}'] for ano in anos)
    lim_itajuba = gpd.read_file("dataset/itajuba.shp")
    df_queimadas = pd.read_excel("dataset/QUEIMADAS_2019_2022.xlsx")
    df_queimadas['Data'] = pd.to_datetime(df_queimadas['Data'], format='%Y') # transformar as datas em datetime
    df_queimadas.set_index('Data', inplace=True) # definir a coluna de tempo como index do DataFrame
    df_queimadas['Número de Focos'] = int(1)
    df_queimadas = df_queimadas[df_queimadas["Bairro - Cidade"].astype(str).str.strip() != "SD"] # dropando os dados "SD: sem definição"
    df_queimadas['cidade'] = df_queimadas['Bairro - Cidade'].str.split(' - ').str[1].str.strip() # Extraindo infos de Itajubá
    df_queimadas = df_queimadas[df_queimadas['cidade'] == 'Itajubá'].drop(columns=['cidade']) 
    df_queimadas['Bairro - Cidade'] = df_queimadas['Bairro - Cidade'].str.split('-').str[0] # Selecionando os nomes dos bairros
    df_queimadas = df_queimadas[["Bairro - Cidade", "Número de Focos"]] # Filtrando as colunas dos Bairros
    df_queimadas = df_queimadas.rename(columns={'Bairro - Cidade': 'Bairro'}) # Renomenando a coluna para Bairro
    return df_queimadas, queimadas_shp, lim_itajuba

df_queimadas, queimadas_shp, lim_itajuba = load_data()

#Cálculo do acumulado total de queimadas por bairro
def calcular_focos_total(df_queimadas):
    df_total_bairros = df_queimadas.groupby('Bairro', as_index=False)['Número de Focos'].sum() #Soma dos focos por bairros
    df_total_bairros['Ano'] = 'Total'  # Indica que é o total do período analisado
    return df_total_bairros

# Processamento dos dados (inserindo 0 nos meses sem registros de QUEIMADAS)
def calcular_focos_mensal(df_queimadas):
    df_queimadas["Mês/Ano"] = df_queimadas.index.to_period("M")  # Criando coluna Mês/Ano
    df_grouped = df_queimadas.groupby(["Mês/Ano", "Bairro"])["Número de Focos"].sum().reset_index()
    meses = pd.period_range(df_queimadas.index.min(), df_queimadas.index.max(), freq="M")  # Lista dos meses do início ao fim (resolução mensal)
    bairros = sorted(df_queimadas["Bairro"].unique()) # Lista de bairros únicos
    df_completo = pd.MultiIndex.from_product([meses, bairros], names=["Mês/Ano", "Bairro"]).to_frame(index=False) # Agrupando os meses e bairros em um df 
    df_final = df_completo.merge(df_grouped, on=["Mês/Ano", "Bairro"], how="left").fillna(0)  # Preenchendo os meses sem registros com 0
    df_final["Mês/Ano"] = df_final["Mês/Ano"].astype(str)  # Converter para string para facilitar o plot
    df_final["Número de Focos"] = df_final["Número de Focos"].astype(int)  # Garantir tipo inteiro para gráfico
    return df_final

# Função para calcular focos anuais por bairro
def calcular_focos_anual(df_queimadas):
    df_queimadas["Ano"] = df_queimadas.index.year  # Criar coluna de ano
    df_ano = df_queimadas.groupby(["Ano", "Bairro"])["Número de Focos"].sum().reset_index()
    list_bairros = sorted(df_queimadas["Bairro"].unique()) # Ordenar bairros alfabeticamente
    list_anos = sorted(df_ano["Ano"].unique())  # Ordenar anos
    return df_ano, list_bairros, list_anos

# Função para calcular o acumulado total de focos de queimadas em Itajubá
def calcular_sazonalidade_focos(df_queimadas):
    df_focos_totais_itajuba = df_queimadas.resample('ME')['Número de Focos'].sum().reset_index()
    df_focos_totais_itajuba['Mês'] = df_focos_totais_itajuba['Data'].dt.strftime('%B')
    df_focos_totais_itajuba['Ano'] = df_focos_totais_itajuba['Data'].dt.strftime('%y')
    df_mensal_anual = df_focos_totais_itajuba.copy()
    df_mensal_anual = df_mensal_anual[['Data', 'Mês', 'Ano', 'Número de Focos']]
    df_mensal_total = df_mensal_anual.groupby("Mês")["Número de Focos"].sum().reset_index()

    # Ordenando os meses na sequência correta
    list_meses = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho',
                  'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro']

    df_mensal_total["Mês"] = pd.Categorical(df_mensal_total["Mês"], categories=list_meses, ordered=True)
    df_mensal_total = df_mensal_total.sort_values("Mês")
    return df_mensal_anual, df_mensal_total

#Processando os dados
df_total_bairros = calcular_focos_total(df_queimadas)
df_grouped = calcular_focos_mensal(df_queimadas)
df_ano, list_bairros, list_anos = calcular_focos_anual(df_queimadas)
df_mensal_anual, df_mensal_total= calcular_sazonalidade_focos(df_queimadas)

#configurações da sidebar
with st.sidebar:
    #st.logo("dataset/imagem_fogo.png", size="large")
    st.subheader("Configurações") 

# Função para plotagem do gráficos
tab1, tab2, tab3 = st.tabs(["📃Início", "📊Gráficos", "🗺️Mapa"])

with tab1:
    def introducao():
        st.subheader('Caracterização das Queimadas no Município de Itajubá, MG')
        with st.expander("Informações:", expanded=True):
            horizontal_bar = "<hr style='margin-top: 0; margin-bottom: 0; height: 1px; border: 1px solid #ff9793;'><br>"    
            st.markdown(
            f""" 
            - Os resultados deste dashboard podem ser observados no artigo: 
            __Caracterização das Queimadas no Município de Itajubá, MG__, publicado na Revista Brasileira de Geografia Física em 2025.
            \n - Os dados de focos de queimadas em Itajubá-MG são provenientes do Corpo de Bombeiros de Itajubá e 
            referem-se ao período entre 2019 e 2022.""")
            st.markdown(horizontal_bar, True)
            
            st.markdown(""" 
            Podem ser observados:
            1. Acumulado anual e total de focos de queimadas por bairro.
            2. Distribuição mensal de focos de queimadas por bairro.
            3. Acumulado mensal e total de focos de queimadas em Itajubá.
            4. Distribuição espacial anual e total de focos de queimadas em Itajubá.
                        """)
            st.markdown(horizontal_bar, True)
                        
    if __name__ == "__main__":
        introducao()

with tab2:
    def plot_graficos():     
        #Gráfico do total de queimadas por bairro durante o período
        num_bairros = st.sidebar.slider("Escolha o número de bairros", min_value=10, max_value=60, value=20)
        df_top_bairros = df_total_bairros.sort_values(by="Número de Focos", ascending=True).reset_index(drop=True)[-num_bairros:] #Escolhendo ps n bairros com maiores focos
        fig_01 = px.bar(df_top_bairros,
                        x="Número de Focos",
                        y="Bairro", 
                        orientation="h",
                        title=f"Acumulado de focos de queimadas por bairro: {list_anos[0]} - {list_anos[-1]}",
                        width=1200,
                        height=600
        )

        fig_01.update_traces(hovertemplate="<br>".join(["Número de Focos: %{x}","Bairro: %{y}"]),
                            textfont_size=14,
                            textangle=0,
                            textposition="outside",
                            cliponaxis=False,
                            marker_color='#FF0000',
                            marker_line_color='#FF0000',
                            marker_line_width=1.5,
                            opacity=0.6
        )

        #Gráfico do total de queimadas por bairro durante o período
        # Criar filtro no sidebar
        ano_selecionado = st.sidebar.selectbox("📆 Selecione o ano", list_anos)
        bairro_selecionado = st.sidebar.selectbox("🏡 Selecione um bairro", list_bairros)

        # Filtrar os dados para o ano selecionado
        df_anual_filtrado = df_ano[df_ano["Ano"] == ano_selecionado]
        df_anual_filtrado = df_anual_filtrado.sort_values(by="Número de Focos", ascending=True).reset_index(drop=True)[-num_bairros:] #Escolhendo ps n bairros com maiores focos

        # Criar gráfico de barras anual
        fig_02= px.bar(df_anual_filtrado,
                    x="Número de Focos",
                    y="Bairro", 
                    orientation="h",
                    title=f"Acumulado de focos de queimadas por bairro em {ano_selecionado}",
                    width=1200,
                    height=600
                    )

        fig_02.update_traces(hovertemplate="<br>".join(["Número de Focos: %{x}","Bairro: %{y}"]),
                            textfont_size=14,
                            textangle=0,
                            textposition="outside",
                            cliponaxis=False,marker_color='#FF0000',
                            marker_line_color='#FF0000',
                            marker_line_width=1.5,
                            opacity=0.6
                            )
        
        # Gráfico do n° de queimadas por bairro/mês
        # Filtrar os dados para o bairro selecionado
        df_filtrado = df_grouped[df_grouped["Bairro"] == bairro_selecionado]

        # Gráfico de barras
        fig_03 = px.bar(
            df_filtrado, 
            x="Mês/Ano", 
            y="Número de Focos",
            title=f"Distribuição Mensal dos Focos de Queimadas no Bairro {bairro_selecionado}",
            hover_data={"Mês/Ano": True, "Número de Focos": True},
            width=1200, 
            height=400   
    )
        
        # Personalizando o texto do pop-up
        fig_03.update_traces(hovertemplate="<br>".join(["Mês/Ano: %{x}","Número de Focos: %{y}"]),
                            textfont_size=14,
                            textangle=0,
                            textposition="outside",
                            cliponaxis=False,
                            marker_color='#FF0000',
                            marker_line_color='#FF0000',
                            marker_line_width=1.5,
                            opacity=0.6
        )  

        # Gráfico de distribuição anual e total de focos de queimadas em Itajubá
        fig_04 = go.Figure()

        # Adicionando o gráfico de barras (total de cada mês)
        fig_04.add_trace(go.Bar(
            x=df_mensal_total["Mês"],
            y=df_mensal_total["Número de Focos"],
            name="Total",
            marker_color="rgb(250, 76, 76)"
        ))

        lista_cores = ["#FFFF00", "#1ce001", "#1E90FF", "#FFFFFF"]
        for i, ano in enumerate(df_mensal_anual["Ano"].unique()):
            df_total_ano = df_mensal_anual[df_mensal_anual['Ano'] == ano]
            fig_04.add_trace(go.Scatter(
                x=df_total_ano['Mês'],
                y=df_total_ano['Número de Focos'],
                mode='lines+markers',
                name=str(ano),
                line=dict(color=lista_cores[i], width=2)
                ))
            
        # Ajuste de layout
        fig_04.update_layout(
            title='Focos de Queimadas por Mês - Comparativo Anual',
            xaxis=dict(title='Mês', tickmode='linear'),
            yaxis_title='Número de Focos',
            hovermode='x unified',
            legend_title='Legenda',
            barmode='overlay')

        # Exibindo os gráficos 01 e 02 lado a lado
        st.subheader("Distribuição Anual dos Focos de Queimadas por Bairro")
        col1, col2 = st.columns(2)
        with col1:
            st.plotly_chart(fig_01, use_container_width=True)
        with col2:
            st.plotly_chart(fig_02, use_container_width=True)
        #Exibindo o gráfico 03
        st.subheader("Distribuição Mensal dos Focos de Queimadas por Bairro")
        st.plotly_chart(fig_03, use_container_width=True)
        #Exibindo o gráfico 04
        st.subheader("Distribuição Anual dos Focos de Queimadas em Itajubá-MG")
        st.plotly_chart(fig_04, use_container_width=True)

    # Exibindo os gráficos no Streamlit
    if __name__ == "__main__":
        plot_graficos()

with tab3:
    # Plotagem do MAPA
    def plot_mapa():
        # Convertendo o contorno do município para o formato GeoJSON
        lim_itajuba_geojson = lim_itajuba.__geo_interface__

        #Informações auxiliares para a criação do mapa
        queimadas_shp['lat'] = queimadas_shp.geometry.y
        queimadas_shp['lon'] = queimadas_shp.geometry.x
        
        #Configuração da sidebar
        list_anos = ['2019', '2020', '2021', '2022', 'Total']
        ano_sidebar = st.sidebar.selectbox("📆 Selecione o ano para o mapa", list_anos)
        focos_total_mapa = 'focos_total' if ano_sidebar == 'Total' else f'focos_{ano_sidebar[-2:]}' # Determinar qual coluna usar
        
        # Criando o mapa com o folium
        m = folium.Map(location=[ -22.44, -45.40], zoom_start=11)
        folium.GeoJson(lim_itajuba_geojson, name="Contorno do Município", style_function=lambda x: {'color': 'black', 'weight': 2, 'fillOpacity': 0}).add_to(m)
        heat_data = [[row['lat'], row['lon'], row[focos_total_mapa]] for _, row in queimadas_shp.iterrows()]
        HeatMap(heat_data, radius=20, name="Mapa de Calor").add_to(m)

        # Adicionar marcadores com pop-ups
        marker_group = FeatureGroup(name="Focos de Queimadas por Bairros")
        for _, row in queimadas_shp.iterrows():
            popup_text = f"""
            <b>Bairro:</b> {row['Name']}<br>
            <b>N° de focos:</b> {row[focos_total_mapa]}
            """
            folium.Marker(location=[row['lat'], row['lon']],
                        popup=folium.Popup(popup_text, max_width=300),
                        icon=folium.Icon(color="red", icon="fire", icon_color="white", icon_size=(35, 45))
                        ).add_to(marker_group)
        marker_group.add_to(m)

        folium.LayerControl(position="topright").add_to(m)

        # Exibindo o mapa no Streamlit
        st.subheader("Mapa de Calor dos Focos de Queimadas em Itajubá-MG")

        folium_static(m, width=950, height=400)

    # Exibindo o mapa no Streamlit
    if __name__ == "__main__":
        plot_mapa()

#configurações da sidebar
with st.sidebar:
    st.markdown("---")
    st.markdown('<h6>Desenvolvido por <a href="https://www.linkedin.com/in/geovane-carlos-0561a8177/">Geovane Carlos</a></h6>',
    unsafe_allow_html=True
    )
    social_media_links = ["https://www.linkedin.com/in/geovanecarlos",
                            "https://github.com/geovanecarlos"
                            ]
    social_media_icons = SocialMediaIcons(social_media_links)
    social_media_icons.render()
    