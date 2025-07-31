# Versões das bibliotecas utilizadas:
# pandas: 2.3.0
# joblib: 1.5.1
# pyserial: 3.5
# matplotlib: 3.10.3
# seaborn: 0.13.2
# numpy: 2.3.1

import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import pandas as pd
import joblib 
import serial
import time
import threading
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import seaborn as sns
import numpy as np
import os

stop_coleta_flag = threading.Event()
coleta_thread = None

# Função para coletar dados.
def coletar_dados(porta, baud_rate, arquivo_saida, status_text_widget):
    try:
        arduino = serial.Serial(porta, baud_rate)
        time.sleep(2) # Espera o Arduino inicializar e a porta serial realmente abrir

        status_text_widget.insert(tk.END, f"Tentando sincronizar com o Arduino em {porta}...\n")
        status_text_widget.see(tk.END)

        # --- INÍCIO DA SINCRONIZAÇÃO COM O ARDUINO ---
        timeout_start = time.time()
        synced = False
        # Tenta sincronizar por até 10 segundos para dar tempo ao Arduino e descartar mensagens
        while time.time() - timeout_start < 10: 
            if arduino.in_waiting > 0: # Se houver dados na porta serial
                linha = arduino.readline().decode('utf-8').strip() # Lê a linha
                if linha: # Se a linha não estiver vazia
                    try:
                        # Tenta converter a linha para floats. Se der certo, encontramos os dados.
                        list(map(float, linha.split(',')))
                        synced = True # Marcamos que estamos sincronizados
                        status_text_widget.insert(tk.END, f"Sincronizado com os dados do Arduino. Iniciando gravação.\n")
                        status_text_widget.see(tk.END)
                        break # Saímos do loop de sincronização
                    except ValueError:
                        # Se não conseguir converter (é uma mensagem de texto), descartamos e avisamos
                        status_text_widget.insert(tk.END, f"Descartando linha de inicialização/não-dados: '{linha}'\n")
                        status_text_widget.see(tk.END)
                time.sleep(0.05)
            else:
                time.sleep(0.1) # Espera um pouco se não houver dados disponíveis

        if not synced:
            # Se o loop de sincronização terminar sem encontrar dados válidos, algo deu errado
            raise Exception("Não foi possível sincronizar com os dados do Arduino após várias tentativas. Verifique a saída serial do Arduino e a conexão.")
        # --- FIM DA SINCRONIZAÇÃO INICIAL ---

        with open(arquivo_saida, 'w') as f:
            f.write("MQ3,MQ5,MQ6,MQ8\n") # Escreve o cabeçalho no CSV APÓS a sincronização

        status_text_widget.insert(tk.END, f"Coletando dados em {porta}... Pressione 'Parar Coleta' ou feche a janela para encerrar.\n")
        status_text_widget.see(tk.END)

        with open(arquivo_saida, 'a') as f:
            while not stop_coleta_flag.is_set():
                if arduino.in_waiting > 0:
                    linha = arduino.readline().decode('utf-8').strip()
                    if linha:
                        try:
                            list(map(float, linha.split(',')))
                            f.write(linha + '\n') 
                        except ValueError:
                            # Caso uma linha inválida (não numérica) apareça no meio da coleta
                            status_text_widget.insert(tk.END, f"Aviso: Linha não numérica descartada durante a coleta: '{linha}'\n")
                            status_text_widget.see(tk.END)
                time.sleep(0.05)

        arduino.close()
        status_text_widget.insert(tk.END, f"Gravação encerrada. Dados salvos em {arquivo_saida}\n")
        status_text_widget.see(tk.END)
    except serial.SerialException as e:
        status_text_widget.insert(tk.END, f"Erro de porta serial: {e}\n")
        status_text_widget.see(tk.END)
    except Exception as e:
        status_text_widget.insert(tk.END, f"Erro na coleta de dados: {e}\n")
        status_text_widget.see(tk.END)

# Função para Análise de Substância Desconhecida
def analisar_substancia_csv(arquivo_csv, modelo_arquivo, scaler_arquivo, status_text_widget, grafico_frame_radar):
    try:
        # Carrega o modelo treinado e o scaler
        modelo_carregado = joblib.load(modelo_arquivo)
        scaler_carregado = joblib.load(scaler_arquivo)
        status_text_widget.insert(tk.END, f"Modelo '{modelo_arquivo}' e Scaler '{scaler_arquivo}' carregados.\n")

        # Carrega os dados da nova substância
        dados_nova_substancia = pd.read_csv(arquivo_csv)
        status_text_widget.insert(tk.END, f"Dados de '{arquivo_csv}' carregados.\n")

        colunas_esperadas = ["MQ3", "MQ5", "MQ6", "MQ8"]
        if not all(coluna in dados_nova_substancia.columns for coluna in colunas_esperadas):
            if dados_nova_substancia.shape[1] == len(colunas_esperadas):
                dados_nova_substancia.columns = colunas_esperadas
                status_text_widget.insert(tk.END, "Aviso: Nomes das colunas ajustados para MQ3, MQ5, MQ6, MQ8.\n")
            else:
                raise ValueError("O arquivo CSV não possui as colunas esperadas ou o número de colunas é incompatível.")

        X_nova_substancia = dados_nova_substancia[colunas_esperadas]

        X_nova_substancia_scaled = scaler_carregado.transform(X_nova_substancia.values)
        
        # Obtém as probabilidades de predição para cada classe
        probabilidades = modelo_carregado.predict_proba(X_nova_substancia_scaled)
        probabilidades_medias = np.mean(probabilidades, axis=0)
        
        # Mapeia as probabilidades para os nomes das classes
        classes_modelo = modelo_carregado.classes_
        confianca_por_classe = pd.Series(probabilidades_medias, index=classes_modelo)

        # --- LÓGICA DE DECISÃO PARA CLASSIFICAR COMO "INDEFINIDA" ---
        # 1. Obtém a classe com maior probabilidade e seu valor
        substancia_predita_raw = confianca_por_classe.idxmax()
        confianca_raw = confianca_por_classe.max() * 100

        # Define os limiares (ajuste conforme necessário)
        LIMIAR_CONFIANCA_MINIMA = 75.0 # Se a confiança for menor que isso, é indefinido
        LIMIAR_DIFERENCA_TOP2 = 10.0  # Se a diferença entre as 2 maiores for menor que isso, é indefinido/mistura

        substancia_final_display = substancia_predita_raw
        confianca_final_display = confianca_raw

        if confianca_raw < LIMIAR_CONFIANCA_MINIMA:
            substancia_final_display = "INDEFINIDA (Confiança Baixa)"
            confianca_final_display = confianca_raw # Mantém a confiança real para exibir

        # Verifica se há um empate técnico entre as top 2 classes
        if len(confianca_por_classe) >= 2:
            top_2_classes = confianca_por_classe.nlargest(2) # Pega as 2 maiores probabilidades
            prob_top1 = top_2_classes.iloc[0] * 100
            prob_top2 = top_2_classes.iloc[1] * 100
            
            # Se a diferença for pequena E não for já indefinida por baixa confiança
            if (prob_top1 - prob_top2) < LIMIAR_DIFERENCA_TOP2 and substancia_final_display != "INDEFINIDA (Confiança Baixa)":
                substancia_final_display = "INDEFINIDA (Possível Mistura)"
                confianca_final_display = prob_top1 # Mostra a confiança da melhor classe
        # --- FIM DA LÓGICA DE DECISÃO ---

        # Plota o perfil dos sensores (gráfico radar)
        # Agora passando o scaler_carregado para normalização consistente no gráfico
        plotar_perfil_sensores(X_nova_substancia, modelo_carregado, substancia_final_display, confianca_final_display, grafico_frame_radar, status_text_widget, scaler_carregado)
        
        # Plota o gráfico de confiança da predição em uma NOVA JANELA
        plotar_confianca_predicao(confianca_por_classe, substancia_final_display, status_text_widget)

        # Atualiza a área de status com o resultado final
        status_text_widget.insert(tk.END, f"Análise Completa. Substância Predita: {substancia_final_display} (Confiança: {confianca_final_display:.2f}%)\n")
        status_text_widget.see(tk.END)

    except FileNotFoundError:
        messagebox.showerror("Erro de Arquivo", f"Verifique se o arquivo do modelo '{modelo_arquivo}', o scaler '{scaler_arquivo}' e o CSV '{arquivo_csv}' existem.")
        status_text_widget.insert(tk.END, f"Erro: Arquivo não encontrado.\n")
    except ValueError as e:
        messagebox.showerror("Erro de Dados", f"Erro na estrutura dos dados: {e}")
        status_text_widget.insert(tk.END, f"Erro: {e}\n")
    except Exception as e:
        messagebox.showerror("Erro de Análise", f"Ocorreu um erro durante a análise: {e}")
        status_text_widget.insert(tk.END, f"Erro na análise: {e}\n")
    status_text_widget.see(tk.END)

# Função para plotar o perfil dos sensores (gráfico radar) com normalização consistente.
def plotar_perfil_sensores(dados_desconhecidos_df, modelo, substancia_predita, confianca, grafico_frame, status_text_widget, scaler_do_modelo):
    try:
        for widget in grafico_frame.winfo_children():
            widget.destroy()

        colunas_sensores = ["MQ3", "MQ5", "MQ6", "MQ8"]

        media_desconhecida = dados_desconhecidos_df[colunas_sensores].mean().values

        dataset_treinamento = pd.read_csv("dataset_nariz_eletronico.csv")
        if 'Tipo_álcool' in dataset_treinamento.columns:
            dataset_treinamento = dataset_treinamento.rename(columns={'Tipo_álcool': 'alcool'})

        perfis_conhecidos_df = dataset_treinamento.groupby('alcool')[colunas_sensores].mean()
        
        classes_conhecidas = modelo.classes_
        
        # Normaliza a amostra desconhecida usando o scaler do modelo
        media_desconhecida_norm = scaler_do_modelo.transform(media_desconhecida.reshape(1, -1))[0]

        perfis_conhecidos_norm = pd.DataFrame(
            scaler_do_modelo.transform(perfis_conhecidos_df[colunas_sensores].values),
            columns=colunas_sensores,
            index=perfis_conhecidos_df.index
        )
        
        num_vars = len(colunas_sensores)
        angles = np.linspace(0, 2 * np.pi, num_vars, endpoint=False).tolist()
        angles += angles[:1] 
        
        media_desconhecida_norm = np.append(media_desconhecida_norm, media_desconhecida_norm[0])

        fig, ax = plt.subplots(figsize=(6.5, 6.5), subplot_kw=dict(polar=True))
        
        for i, classe in enumerate(classes_conhecidas):
            if classe in perfis_conhecidos_norm.index:
                valores_classe = perfis_conhecidos_norm.loc[classe][colunas_sensores].values
                valores_classe = np.append(valores_classe, valores_classe[0])
                ax.plot(angles, valores_classe, linewidth=1, linestyle='solid', label=classe.upper(), color=sns.color_palette("tab10")[i])
                ax.fill(angles, valores_classe, color=sns.color_palette("tab10")[i], alpha=0.25)
        
        ax.plot(angles, media_desconhecida_norm, linewidth=2, linestyle='dashed', label=f'Amostra ({substancia_predita.upper()})', color='black', marker='o')
        ax.fill(angles, media_desconhecida_norm, color='gray', alpha=0.1)

        ax.set_theta_offset(np.pi / 2)
        ax.set_theta_direction(-1)
        ax.set_rlabel_position(0)
        
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(colunas_sensores)
        
        ax.set_yticks(np.arange(0, 1.1, 0.2))
        ax.set_yticklabels(['0', '0.2', '0.4', '0.6', '0.8', '1.0'], color='gray', size=8)
        ax.set_ylim(0, 1.0)
        
        ax.set_title('Perfil Comparativo de Sensores', fontsize=14, pad=20)
        
        ax.legend(loc='upper right', bbox_to_anchor=(2.0, 1.1))
        
        fig.subplots_adjust(top=0.81)

        canvas = FigureCanvasTkAgg(fig, master=grafico_frame)
        canvas_widget = canvas.get_tk_widget()
        canvas_widget.pack(side=tk.TOP, fill=tk.BOTH, expand=True) 
        canvas.draw()

    except FileNotFoundError:
        status_text_widget.insert(tk.END, "Erro: 'dataset_nariz_eletronico.csv' não encontrado. Não foi possível gerar o gráfico de perfil. Certifique-se de que o arquivo está no mesmo diretório do script ou o caminho está correto.\n")
    except Exception as e:
        status_text_widget.insert(tk.END, f"Erro ao gerar o gráfico de perfil: {e}\n")
    status_text_widget.see(tk.END)

# Função para plotar o gráfico de confiança da predição em uma nova janela
def plotar_confianca_predicao(confianca_por_classe, substancia_predita, status_text_widget):
    try:
        new_window = tk.Toplevel(app) 
        new_window.title(f"Confiança da Predição para {substancia_predita.upper()}")
        new_window.geometry("750x500") 

        fig, ax = plt.subplots(figsize=(6, 4)) 
        
        confianca_por_classe_percent = confianca_por_classe * 100 
        confianca_por_classe_sorted = confianca_por_classe_percent.sort_values(ascending=False)

        sns.barplot(x=confianca_por_classe_sorted.index, y=confianca_por_classe_sorted.values, ax=ax, palette="viridis", hue=confianca_por_classe_sorted.index, legend=False)
        
        ax.set_title(f"Confiança da Predição (Amostra: {substancia_predita.upper()})", fontsize=14)
        ax.set_xlabel("Tipo de Álcool")
        ax.set_ylabel("Probabilidade Média (%)")
        ax.set_ylim(0, 105) 
        
        ax.tick_params(axis='x', rotation=45, colors='black', labelsize=10) 
        ax.tick_params(axis='y', colors='black') 
        
        ax.grid(axis='y', linestyle='--', alpha=0.7)

        for index, value in enumerate(confianca_por_classe_sorted.values):
            ax.text(index, value + 2, f'{value:.1f}%', ha='center', va='bottom', fontsize=9, color='black')

        plt.tight_layout() 

        canvas = FigureCanvasTkAgg(fig, master=new_window) 
        canvas_widget = canvas.get_tk_widget()
        canvas_widget.pack(side=tk.TOP, fill=tk.BOTH, expand=True) 
        canvas.draw()

    except Exception as e:
        status_text_widget.insert(tk.END, f"Erro ao gerar o gráfico de confiança em nova janela: {e}\n")
    status_text_widget.see(tk.END)

# --- Funções da Interface (GUI) ---

def iniciar_coleta_btn_click():
    global coleta_thread
    if coleta_thread is not None and coleta_thread.is_alive():
        messagebox.showwarning("Aviso", "A coleta de dados já está em andamento!")
        return

    porta = porta_serial_entry.get()
    baud_rate = int(baud_rate_entry.get())
    arquivo_saida = nome_arquivo_coleta_entry.get()

    if not porta or not arquivo_saida:
        messagebox.showwarning("Campos Vazios", "Por favor, preencha a porta serial e o nome do arquivo de saída.")
        return
    
    if not arquivo_saida.endswith('.csv'):
        arquivo_saida += '.csv'
    
    # Verifica se o arquivo existe e pergunta se deseja sobrescrever
    if os.path.exists(arquivo_saida):
        if not messagebox.askyesno("Arquivo Existente", f"O arquivo '{arquivo_saida}' já existe. Deseja sobrescrevê-lo (isso apagará o conteúdo existente)?"):
            return
            
    stop_coleta_flag.clear()
    coleta_thread = threading.Thread(target=coletar_dados, args=(porta, baud_rate, arquivo_saida, status_output))
    coleta_thread.daemon = True
    coleta_thread.start()
    status_output.insert(tk.END, "Coleta iniciada. Os dados de Rs/R0 estão sendo salvos no arquivo CSV.\n") 
    status_output.see(tk.END)


def parar_coleta_btn_click():
    global coleta_thread
    if coleta_thread is not None and coleta_thread.is_alive():
        stop_coleta_flag.set()
        status_output.insert(tk.END, "Sinal para parar coleta enviado. Aguardando...\n")
    else:
        messagebox.showinfo("Informação", "Nenhuma coleta de dados em andamento.")

def selecionar_arquivo_analise():
    arquivo_selecionado = filedialog.askopenfilename(
        title="Selecione o arquivo CSV da substância para analisar",
        filetypes=(("Arquivos CSV", "*.csv"), ("Todos os arquivos", "*.*"))
    )
    if arquivo_selecionado:
        arquivo_analise_entry.delete(0, tk.END)
        arquivo_analise_entry.insert(0, arquivo_selecionado)

def analisar_btn_click():
    arquivo_csv_analise = arquivo_analise_entry.get()
    if not arquivo_csv_analise:
        messagebox.showwarning("Campo Vazio", "Por favor, selecione o arquivo CSV para análise.")
        return

    # Nomes dos arquivos do modelo e do scaler (devem ser os mesmos que você salvou no treinamento)
    modelo_arquivo = "modelo_nariz_eletronico.pkl"
    scaler_arquivo = "scaler_nariz_eletronico.pkl"

    analisar_substancia_csv(arquivo_csv_analise, modelo_arquivo, scaler_arquivo, status_output, grafico_frame_radar) 

# Função chamada ao fechar a aplicação
def on_closing():
    if messagebox.askokcancel("Sair", "Deseja realmente sair do aplicativo? A coleta de dados será interrompida."):
        stop_coleta_flag.set()
        if coleta_thread and coleta_thread.is_alive():
            coleta_thread.join(timeout=1.0)
        plt.close('all')
        app.destroy()

# --- Configuração da Janela Principal ---
app = tk.Tk()
app.title("Nariz Eletrônico - Detecção de Álcoois")
app.geometry("1000x800")

app.protocol("WM_DELETE_WINDOW", on_closing)

# --- Frame de Coleta de Dados ---
frame_coleta = tk.LabelFrame(app, text="Coleta de Dados", padx=10, pady=10)
frame_coleta.pack(padx=10, pady=10, fill="x")

tk.Label(frame_coleta, text="Porta Serial (Ex: COM3 /dev/ttyACM0):").grid(row=0, column=0, sticky="w", pady=2)
porta_serial_entry = tk.Entry(frame_coleta, width=30)
porta_serial_entry.grid(row=0, column=1, sticky="ew", pady=2)
porta_serial_entry.insert(0, 'COM3')

tk.Label(frame_coleta, text="Baud Rate (Arduino):").grid(row=1, column=0, sticky="w", pady=2)
baud_rate_entry = tk.Entry(frame_coleta, width=30)
baud_rate_entry.grid(row=1, column=1, sticky="ew", pady=2)
baud_rate_entry.insert(0, '9600')

tk.Label(frame_coleta, text="Nome do Arquivo de Saída (.csv):").grid(row=2, column=0, sticky="w", pady=2)
nome_arquivo_coleta_entry = tk.Entry(frame_coleta, width=30)
nome_arquivo_coleta_entry.grid(row=2, column=1, sticky="ew", pady=2)
nome_arquivo_coleta_entry.insert(0, 'nova_amostra.csv')

btn_iniciar_coleta = tk.Button(frame_coleta, text="Iniciar Coleta", command=iniciar_coleta_btn_click)
btn_iniciar_coleta.grid(row=3, column=0, pady=5, sticky="ew")

btn_parar_coleta = tk.Button(frame_coleta, text="Parar Coleta", command=parar_coleta_btn_click)
btn_parar_coleta.grid(row=3, column=1, pady=5, sticky="ew")

# --- Frame de Análise de Substância Desconhecida ---
frame_analise = tk.LabelFrame(app, text="Análise de Substância Desconhecida", padx=10, pady=10)
frame_analise.pack(padx=10, pady=10, fill="x")

tk.Label(frame_analise, text="Arquivo CSV para Análise:").grid(row=0, column=0, sticky="w", pady=2)
arquivo_analise_entry = tk.Entry(frame_analise, width=40)
arquivo_analise_entry.grid(row=0, column=1, sticky="ew", pady=2)

btn_selecionar_arquivo = tk.Button(frame_analise, text="Procurar...", command=selecionar_arquivo_analise)
btn_selecionar_arquivo.grid(row=0, column=2, padx=5, pady=2)

btn_analisar = tk.Button(frame_analise, text="Analisar Substância", command=analisar_btn_click)
btn_analisar.grid(row=1, column=0, columnspan=3, pady=10, sticky="ew")

# --- Frame para o Gráfico de Radar (Perfil de Sensores) ---
grafico_frame_radar = tk.LabelFrame(app, text="Perfil de Sensores", padx=10, pady=15)
grafico_frame_radar.pack(padx=10, pady=10, fill="both", expand=True)

# --- Área de Status ---
tk.Label(app, text="Status:").pack(padx=10, pady=(10,0), anchor="w")
status_output = scrolledtext.ScrolledText(app, wrap=tk.WORD, width=60, height=10)
status_output.pack(padx=10, pady=10, fill="both", expand=True)

app.mainloop()
