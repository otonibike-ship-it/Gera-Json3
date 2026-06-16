# Usar Python 3.11 slim (mais leve que a imagem padrão)
FROM python:3.11-slim

# Definir diretório de trabalho
WORKDIR /app

# Instalar dependências do sistema (opcional, mas recomendado para evitar problemas)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements.txt
COPY requirements.txt .

# Instalar dependências Python (sem cache para economizar espaço)
RUN pip install --no-cache-dir -r requirements.txt

# ========================================================================
# Copiar TODOS os arquivos necessários para a aplicação
# ========================================================================

# 1. Código principal da aplicação
COPY src/ ./src/

# 2. Recursos estáticos (imagens, etc)
COPY img/ ./img/

# 3. Configuração do Streamlit
COPY .streamlit/ ./.streamlit/

# 4. Arquivos de autenticação e configuração (auto-gerados)
COPY credentials.json .
COPY config.yaml .

# 5. Scripts de diagnóstico e manutenção (reorganizados em tools/)
COPY tools/ ./tools/

# ========================================================================
# Configuração final
# ========================================================================

# Expor porta padrão do Streamlit
EXPOSE 8501

# Comando para iniciar a aplicação
CMD ["streamlit", "run", "src/app_streamlit.py", "--server.port=8501", "--server.address=0.0.0.0"]
