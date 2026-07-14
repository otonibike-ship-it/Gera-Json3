"""
Aplicativo Streamlit - Gerador de JSONs Hybris
Versão 2.0 - Interface Web Completa

Executar com: streamlit run app_streamlit.py
"""

# ═══════════════════════════════════════════════════════════════════════
# IMPORTS - Importações necessárias para o funcionamento
# ═══════════════════════════════════════════════════════════════════════

import streamlit as st              # Framework web para criar a interface
import json                         # Biblioteca para manipular JSON
import os                           # Funções do sistema operacional
import sys                          # Sistema (para flush de stdout)
import hashlib                      # Hash para detectar mudanças
from pathlib import Path            # Trabalhar com caminhos de arquivos
import yaml                          # Para carregar config.yaml
import streamlit_authenticator as stauth  # Biblioteca de autenticação
from datetime import datetime       # Para timestamps
import requests                     # Para enviar JSON via HTTP POST
from hybris_json_generator import HybrisJSONGenerator  # Classe geradora do JSON
from postgres_manager import PostgresManager  # Gerenciador PostgreSQL

# ═══════════════════════════════════════════════════════════════════════
# AUTENTICAÇÃO - Proteção de acesso com streamlit-authenticator
# ═══════════════════════════════════════════════════════════════════════

def load_authenticator():
    """Carrega o autenticador usando config.yaml"""
    print("[load_authenticator] Iniciando...")

    # Tentar múltiplos caminhos possíveis
    possible_paths = [
        Path(__file__).parent.parent / "config.yaml",  # Caminho relativo
        Path.cwd() / "config.yaml",  # Diretório atual
        Path.cwd().parent / "config.yaml",  # Diretório pai
    ]

    config_path = None
    for path in possible_paths:
        if path.exists():
            config_path = path
            print(f"[load_authenticator] Encontrado config.yaml em: {path}")
            break

    if not config_path:
        print("[load_authenticator] ERRO: config.yaml não encontrado em nenhum caminho:")
        for p in possible_paths:
            print(f"  - {p}")
        st.error(f"Arquivo config.yaml nao encontrado")
        st.stop()

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        if not config:
            print("[load_authenticator] ERRO: config.yaml está vazio!")
            raise ValueError("config.yaml vazio")

        # Extrair credenciais e mostrar debug
        credentials_config = config.get('credentials', {})
        usernames = credentials_config.get('usernames', {})

        print(f"[load_authenticator] Config carregado:")
        print(f"  - Path: {config_path}")
        print(f"  - Usuarios: {list(usernames.keys())}")
        for username, user_data in usernames.items():
            has_password = bool(user_data.get('password', '').strip()) if isinstance(user_data, dict) else False
            print(f"    - {username}: email={user_data.get('email') if isinstance(user_data, dict) else 'N/A'}, senha={'[preenchida]' if has_password else '[VAZIA]'}")

        # Criar authenticator
        cookie_settings = config.get('cookie', {})
        authenticator = stauth.Authenticate(
            credentials=credentials_config,
            cookie_name=cookie_settings.get('name', 'hybris_auth'),
            cookie_key=cookie_settings.get('key', 'secret'),
            cookie_expiry_days=cookie_settings.get('expiry_days', 30)
        )
        print(f"[load_authenticator] OK: Authenticator inicializado com {len(usernames)} usuarios")
        return authenticator

    except Exception as e:
        print(f"[load_authenticator] ERRO: {e}")
        import traceback
        traceback.print_exc()
        st.error(f"Erro ao carregar authenticator: {str(e)}")
        st.stop()

def get_merchant_name_for_user(username: str, credentials: dict) -> str:
    """
    Retorna o merchantName personalizado para o usuário logado.

    Formato: "Fake callback - {DisplayName}"

    Prioridade:
    1. display_name (se preenchido) → "Fake callback - Kennedy"
    2. Primeiro nome do username → "Fake callback - Marcos" (de marcos.fernandes)
    3. Username inteiro → "Fake callback - Marco" (fallback)

    Args:
        username: Nome do usuário logado
        credentials: Dict com dados dos usuários

    Returns:
        String formatada para merchantName
    """
    user_data = credentials.get("users", {}).get(username, {})

    # Prioridade 1: display_name (se preenchido)
    display_name = user_data.get("display_name", "").strip()
    if display_name:
        return f"Fake callback - {display_name}"

    # Prioridade 2: Primeiro nome do username (ex: "marcos" de "marcos.fernandes")
    first_name = username.split('.')[0].split('_')[0].capitalize()
    return f"Fake callback - {first_name}"

def load_credentials() -> dict:
    """
    Carrega credenciais APENAS do PostgreSQL (fonte de verdade).
    PostgreSQL é a ÚNICA e exclusiva fonte de dados!
    Arquivo JSON é usado APENAS como fallback se PostgreSQL indisponível.
    """
    # ✨ PRIORIDADE 1: Carregar SEMPRE do PostgreSQL (fonte de verdade)
    print("[load_credentials] Iniciando carregamento...")
    try:
        print("[load_credentials] Conectando a PostgreSQL...")
        db = PostgresManager()
        db.ensure_table_exists()
        db_users = db.load_all_users()

        if db_users and "users" in db_users and db_users["users"]:
            # PostgreSQL tem dados - USAR APENAS POSTGRESQL
            print(f"[load_credentials] OK: Carregados {len(db_users['users'])} usuarios do PostgreSQL:")
            for username, user_info in db_users['users'].items():
                password_val = user_info.get('password', '').strip()
                print(f"  - {username}: senha={'[preenchida]' if password_val else '[VAZIA]'}, email={user_info.get('email', 'N/A')}")
            return db_users
        else:
            print("[load_credentials] AVISO: PostgreSQL vazio, usando fallback")
    except Exception as e:
        # PostgreSQL indisponível, fazer fallback para arquivo
        print(f"[load_credentials] AVISO: PostgreSQL indisponivel: {e}. Usando fallback de arquivo local.")

    # FALLBACK: Carregar do arquivo APENAS se PostgreSQL falhar
    print("[load_credentials] Tentando fallback com credentials.json...")
    possible_paths = [
        Path(__file__).parent.parent / "credentials.json",
        Path.cwd() / "credentials.json",
        Path.cwd().parent / "credentials.json",
    ]

    creds_path = None
    for path in possible_paths:
        if path.exists():
            creds_path = path
            print(f"[load_credentials] Encontrado credentials.json em: {path}")
            try:
                with open(creds_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if data and "users" in data and data["users"]:
                        print(f"[load_credentials] OK: Carregados {len(data['users'])} usuarios do arquivo")
                        return data
            except (json.JSONDecodeError, IOError) as e:
                print(f"[load_credentials] AVISO: Erro ao ler credentials.json: {e}")
                pass

    # ÚLTIMO RECURSO: Retornar usuário padrão
    print("[load_credentials] AVISO: Usando credenciais padrao (marco apenas)")
    return {
        "users": {
            "marco": {
                "password_hash": "sha256:8f68a0d4e226a2624a9c98778bf8d6b88919dc8a4d3b214316534272fd0490c8",
                "created_at": "2025-11-26",
                "last_login": None,
                "enabled": True,
                "password": "SenhaForte123!Marcos"
            }
        },
        "version": "1.0"
    }

def sync_credentials_to_config(credentials_data: dict) -> None:
    """Sincroniza credenciais do credentials.json para config.yaml para o streamlit-authenticator"""
    print(f"  [sync_credentials_to_config] Usuarios recebidos: {list(credentials_data.get('users', {}).keys())}")

    # Tentar múltiplos caminhos para config.yaml
    possible_config_paths = [
        Path(__file__).parent.parent / "config.yaml",
        Path.cwd() / "config.yaml",
        Path.cwd().parent / "config.yaml",
    ]

    config_path = None
    for path in possible_config_paths:
        if path.exists():
            config_path = path
            print(f"  [sync] Encontrado config.yaml em: {path}")
            break

    if not config_path:
        # Se não encontrou, criar no primeiro caminho
        config_path = Path(__file__).parent.parent / "config.yaml"
        print(f"  [sync] config.yaml nao encontrado, sera criado em: {config_path}")

    # Carregar config atual (ou criar novo se não existir)
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            if not config:
                config = {}
    except FileNotFoundError:
        print(f"  [sync] Criando novo config.yaml em: {config_path}")
        config = {}

    # Garantir estrutura básica
    if 'credentials' not in config:
        config['credentials'] = {}
    if 'usernames' not in config['credentials']:
        config['credentials']['usernames'] = {}
    if 'cookie' not in config:
        config['cookie'] = {
            'expiry_days': 30,
            'key': 'gerador_json_hybris_secret_key_2025',
            'name': 'hybris_json_generator_auth'
        }

    # Só sobrescrever usernames se o PostgreSQL retornou usuários de fato
    # Manter o config.yaml anterior se vier vazio (evita invalidar cookies válidos)
    incoming_users = credentials_data.get('users', {})
    if not incoming_users:
        print("  [sync] AVISO: nenhum usuario recebido do PostgreSQL — config.yaml mantido sem alteracao")
        return

    config['credentials']['usernames'] = {}

    # Converter credenciais de JSON para formato do config.yaml
    print(f"  [sync] Sincronizando {len(incoming_users)} usuarios...")

    for username, user_info in incoming_users.items():
        # Extrair senha em texto plano
        password_plain = user_info.get('password', '').strip()

        # Se password estiver vazio, usar um placeholder baseado no username
        if not password_plain:
            password_plain = f'{username}@123456'
            print(f"  [sync] AVISO: Senha vazia para {username}, usando placeholder")

        config['credentials']['usernames'][username] = {
            'email': user_info.get('email', f'{username}@example.com'),
            'name': user_info.get('name', username.title()),
            'password': password_plain
        }
        print(f"  [sync] OK: {username}")

    # Salvar config.yaml atualizado
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        print(f"  [sync] SUCESSO: config.yaml salvo em {config_path}")

        # VERIFICACAO: Ler de volta para confirmar que foi salvo
        with open(config_path, 'r', encoding='utf-8') as f:
            config_verificado = yaml.safe_load(f)
            usuarios_salvos = list(config_verificado.get('credentials', {}).get('usernames', {}).keys())
            print(f"  [sync] VERIFICACAO: {len(usuarios_salvos)} usuarios confirmados no arquivo: {usuarios_salvos}")

    except Exception as e:
        print(f"  [sync] ERRO ao salvar config.yaml: {e}")
        raise

# ═══════════════════════════════════════════════════════════════════════
# GERENCIAMENTO DE USUÁRIOS - Funções para administração
# ═══════════════════════════════════════════════════════════════════════

def log_user_action(action: str, username: str, details: str = "") -> None:
    """
    Registra ações de usuários em um arquivo de log para rastreamento.
    Importante: Evita perda de dados se sincronização falhar.
    """
    try:
        log_path = Path(__file__).parent.parent / "usuarios_log.txt"
        timestamp = __import__('datetime').datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {action}: {username} {details}\n"

        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(log_entry)
    except Exception:
        pass  # Falha silenciosa para não bloquear operação

def save_credentials(data: dict) -> bool:
    """
    Salva credenciais no arquivo JSON E sincroniza com PostgreSQL
    PostgreSQL é a fonte de verdade, arquivo é backup
    """
    # Tentar múltiplos caminhos possíveis
    possible_paths = [
        Path(__file__).parent.parent / "credentials.json",
        Path.cwd() / "credentials.json",
        Path.cwd().parent / "credentials.json",
    ]

    creds_path = None
    for path in possible_paths:
        if path.exists() or path.parent.exists():
            creds_path = path
            break

    if not creds_path:
        creds_path = Path(__file__).parent.parent / "credentials.json"

    try:
        # 1. Salvar no arquivo local (backup)
        with open(creds_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        # 2. Sincronizar com PostgreSQL (fonte de verdade)
        db = PostgresManager()
        db.ensure_table_exists()

        for username, user_info in data.get("users", {}).items():
            db.save_user(
                username,
                user_info.get('email', f'{username}@example.com'),
                user_info.get('name', username),
                user_info.get('password_hash', ''),
                user_info.get('password', '')
            )

        # 3. Sincronizar com config.yaml após salvar
        sync_credentials_to_config(data)
        return True
    except Exception as e:
        st.error(f"❌ Erro ao salvar credenciais: {e}")
        return False

def sync_config_to_credentials(config_data: dict, credentials_data: dict) -> dict:
    """
    Sincroniza usuários do config.yaml para credentials.json (direção inversa).
    Esto IMPORTANTE: Recupera usuários que podem ter sido perdidos no config.yaml.
    """
    try:
        for username, user_info in config_data.get('credentials', {}).get('usernames', {}).items():
            # Se usuário existe em config.yaml mas não em credentials.json, adicionar
            if username not in credentials_data.get('users', {}):
                credentials_data['users'][username] = {
                    'password_hash': f"sha256:placeholder_{username}",  # Placeholder temporário
                    'password': user_info.get('password', 'ChangeMe123!'),
                    'email': user_info.get('email', f'{username}@example.com'),
                    'name': user_info.get('name', username.title()),
                    'created_at': str(__import__('datetime').datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                    'last_login': None,
                    'enabled': True
                }
    except Exception as e:
        # Falha silenciosa
        pass

    return credentials_data

def hash_password(password: str) -> str:
    """Gera hash SHA256 da senha"""
    return f"sha256:{hashlib.sha256(password.encode()).hexdigest()}"

def page_admin_users():
    """Página de administração de usuários"""
    st.set_page_config(page_title="Gerenciar Usuários", layout="wide")
    st.title("👥 Gerenciar Usuários")
    st.markdown("---")

    credentials = load_credentials()
    users = credentials.get("users", {})

    # Sidebar com opções
    st.sidebar.title("⚙️ Opções")
    tab_option = st.sidebar.radio(
        "Escolha uma opção:",
        ["📋 Listar Usuários", "➕ Criar Usuário", "🔑 Alterar Senha", "❌ Remover Usuário"]
    )

    # TAB 1: LISTAR USUÁRIOS
    if tab_option == "📋 Listar Usuários":
        st.subheader("📋 Usuários Cadastrados")

        if not users:
            st.info("ℹ️ Nenhum usuário cadastrado")
        else:
            # Criar tabela de usuários
            for username, info in users.items():
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.write(f"**👤 {username}**")
                with col2:
                    status = "✅ Ativo" if info.get("enabled", True) else "❌ Inativo"
                    st.write(status)
                with col3:
                    created = info.get("created_at", "N/A")
                    st.write(f"Criado: {created}")
                with col4:
                    last_login = info.get("last_login", "Nunca")
                    st.write(f"Último acesso: {last_login}")
                st.divider()

    # TAB 2: CRIAR USUÁRIO
    elif tab_option == "➕ Criar Usuário":
        st.subheader("➕ Criar Novo Usuário")

        with st.form("form_add_user"):
            col1, col2 = st.columns(2)

            with col1:
                new_username = st.text_input(
                    "Nome do usuário *",
                    placeholder="Ex: joao, maria, carlos",
                    help="Mínimo 3 caracteres, apenas letras e números"
                )
                new_password = st.text_input(
                    "Senha *",
                    type="password",
                    placeholder="Ex: SenhaForte123!",
                    help="Mínimo 8 caracteres"
                )

            with col2:
                new_email = st.text_input(
                    "Email (opcional)",
                    placeholder="Ex: joao@example.com",
                    help="Email do usuário (usado para sincronização)"
                )
                confirm_password = st.text_input(
                    "Confirmar senha *",
                    type="password",
                    placeholder="Repita a senha",
                )

            submitted = st.form_submit_button("✅ Criar Usuário", use_container_width=True)

            if submitted:
                # Validações
                if not new_username or not new_password or not confirm_password:
                    st.error("❌ Todos os campos são obrigatórios!")
                elif len(new_username) < 3:
                    st.error("❌ Nome de usuário deve ter pelo menos 3 caracteres!")
                elif len(new_password) < 8:
                    st.error("❌ Senha deve ter pelo menos 8 caracteres!")
                elif new_password != confirm_password:
                    st.error("❌ As senhas não conferem!")
                elif new_username in users:
                    st.error(f"❌ Usuário '{new_username}' já existe!")
                else:
                    # Adicionar usuário
                    credentials["users"][new_username] = {
                        "password_hash": hash_password(new_password),
                        "password": new_password,  # Guardar senha em texto plano para config.yaml
                        "email": new_email if new_email else f'{new_username}@example.com',
                        "name": new_username.title(),
                        "created_at": str(__import__('datetime').datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                        "last_login": None,
                        "enabled": True
                    }

                    if save_credentials(credentials):
                        # Registrar criação do usuário em log
                        log_user_action("CREATE", new_username, f"email={new_email}")
                        st.success(f"✅ Usuário '{new_username}' criado com sucesso!")
                        st.info(f"""
                        💡 **O usuário pode fazer login agora com:**
                        - Usuário: **{new_username}**
                        - Senha: **{new_password}**

                        ⚠️ **Importante**: Faça logout e login novamente com o novo usuário para usar a aplicação.
                        """)
                        st.balloons()
                        st.session_state["_show_logout_btn"] = True

        # Botão exibido após o form (st.button não é permitido dentro de st.form)
        if st.session_state.get("_show_logout_btn"):
            st.info("👇 **Clique abaixo para fazer logout e testar o novo usuário**")
            if st.button("🔓 Fazer Logout para Testar Novo Usuário", use_container_width=True, type="primary"):
                st.session_state.clear()
                st.rerun()

    # TAB 3: ALTERAR SENHA
    elif tab_option == "🔑 Alterar Senha":
        st.subheader("🔑 Alterar Senha")

        if not users:
            st.warning("⚠️ Nenhum usuário cadastrado!")
        else:
            with st.form("form_change_password"):
                username_to_change = st.selectbox(
                    "Selecione o usuário:",
                    list(users.keys()),
                    help="Escolha o usuário cuja senha será alterada"
                )
                new_pass = st.text_input(
                    "Nova senha:",
                    type="password",
                    placeholder="Ex: SenhaNovaForte123!",
                    help="Mínimo 8 caracteres"
                )
                confirm_new_pass = st.text_input(
                    "Confirmar nova senha:",
                    type="password",
                    placeholder="Repita a nova senha",
                )

                submitted = st.form_submit_button("✅ Alterar Senha", use_container_width=True)

                if submitted:
                    if not new_pass or not confirm_new_pass:
                        st.error("❌ A nova senha e confirmação são obrigatórias!")
                    elif len(new_pass) < 8:
                        st.error("❌ Senha deve ter pelo menos 8 caracteres!")
                    elif new_pass != confirm_new_pass:
                        st.error("❌ As senhas não conferem!")
                    else:
                        # Alterar senha
                        credentials["users"][username_to_change]["password_hash"] = hash_password(new_pass)
                        credentials["users"][username_to_change]["password"] = new_pass  # Guardar senha em texto plano para config.yaml
                        credentials["users"][username_to_change]["last_modified"] = str(__import__('datetime').datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

                        if save_credentials(credentials):
                            # Registrar mudança de senha em log
                            log_user_action("CHANGE_PASSWORD", username_to_change)
                            st.success(f"✅ Senha de '{username_to_change}' alterada com sucesso!")
                            st.balloons()

    # TAB 4: REMOVER USUÁRIO
    elif tab_option == "❌ Remover Usuário":
        st.subheader("❌ Remover Usuário")

        if not users:
            st.warning("⚠️ Nenhum usuário cadastrado!")
        else:
            username_to_remove = st.selectbox(
                "Selecione o usuário para remover:",
                list(users.keys()),
                help="⚠️ Esta ação não pode ser desfeita!"
            )

            st.warning(f"⚠️ Você está prestes a remover o usuário '{username_to_remove}'. Esta ação não pode ser desfeita!")

            col1, col2 = st.columns(2)
            with col1:
                if st.button("❌ Confirmar Remoção", use_container_width=True, type="secondary"):
                    # Remover do credentials.json
                    del credentials["users"][username_to_remove]

                    # Remover do PostgreSQL também
                    db = PostgresManager()
                    db.delete_user(username_to_remove)

                    if save_credentials(credentials):
                        # Registrar remoção do usuário em log
                        log_user_action("DELETE", username_to_remove)
                        st.success(f"✅ Usuário '{username_to_remove}' removido com sucesso!")
                        st.rerun()

            with col2:
                st.button("🔙 Cancelar", use_container_width=True)

# ═══════════════════════════════════════════════════════════════════════
# HISTÓRICO DE PEDIDOS - Página de consulta
# ═══════════════════════════════════════════════════════════════════════

def page_historico():
    """Página de histórico de pedidos gerados"""
    st.subheader("📊 Histórico de Pedidos Gerados")
    st.markdown("---")

    st.markdown("### 🔍 Filtros")
    col1, col2, col3 = st.columns(3)
    with col1:
        f_numero = st.text_input("Número do Pedido", placeholder="Ex: 21381859", key="hist_numero")
    with col2:
        f_nome = st.text_input("Nome do Cliente", placeholder="Ex: RENATO BARBOSA", key="hist_nome")
    with col3:
        f_cpf = st.text_input("CPF do Cliente", placeholder="Ex: 123.456.789-00", key="hist_cpf")

    st.button("🔍 Buscar", use_container_width=True, key="hist_buscar")

    st.markdown("---")

    try:
        db = PostgresManager()
        db.ensure_pedidos_table_exists()
        rows = db.get_pedidos(
            numero_pedido=f_numero.strip() if f_numero else None,
            nome_cliente=f_nome.strip() if f_nome else None,
            cpf_cliente=f_cpf.strip() if f_cpf else None
        )

        if rows:
            st.success(f"✅ {len(rows)} transação(ões) encontrada(s)")
            data = []
            for row in rows:
                numero_pedido, nome_cliente, cpf_cliente, transaction_id, \
                amount, terminal_number, authorization_code, generated_at, generated_by = row
                data.append({
                    "Nº Pedido": numero_pedido or "",
                    "Nome Cliente": nome_cliente or "",
                    "CPF": cpf_cliente or "",
                    "ID Transação": transaction_id or "",
                    "Valor (R$)": f"R$ {(amount or 0)/100:,.2f}",
                    "Nº Terminal": terminal_number or "",
                    "Cód. Autorização": authorization_code or "",
                    "Gerado Em": generated_at.strftime("%d/%m/%Y %H:%M") if generated_at else "",
                    "Gerado Por": generated_by or ""
                })
            st.dataframe(data, use_container_width=True)
            st.caption(f"Mostrando até 500 registros mais recentes")
        else:
            st.info("ℹ️ Nenhum registro encontrado. Gere alguns JSONs para ver o histórico aqui.")

    except Exception as e:
        st.error(f"❌ Erro ao carregar histórico: {str(e)}")


# ═══════════════════════════════════════════════════════════════════════
# FUNÇÃO HELPER - Extrair transação de diferentes formatos Hybris
# ═══════════════════════════════════════════════════════════════════════

def validate_header_json(header_data: dict) -> tuple[bool, list]:
    """
    Valida se o JSON do cabeçalho tem os campos obrigatórios.

    Args:
        header_data: Dicionário com dados do cabeçalho

    Returns:
        (is_valid: bool, errors: list of strings)
    """
    errors = []

    if not header_data:
        return False, ["Header vazio ou não carregado"]

    # Campos obrigatórios do cabeçalho
    if not header_data.get("id"):
        errors.append("'id' é obrigatório no cabeçalho")

    if not header_data.get("price") and header_data.get("price") != 0:
        errors.append("'price' é obrigatório no cabeçalho")

    if not header_data.get("number"):
        errors.append("'number' é obrigatório no cabeçalho")

    if not header_data.get("items") or not isinstance(header_data["items"], list):
        errors.append("'items' é obrigatório no cabeçalho (deve ser um array)")

    if not header_data.get("created_at"):
        errors.append("'created_at' é obrigatório no cabeçalho")

    if not header_data.get("updated_at"):
        errors.append("'updated_at' é obrigatório no cabeçalho")

    return len(errors) == 0, errors


def validate_json_transaction(trans_data: dict, trans_type: str = None) -> tuple[bool, list]:
    """
    Valida se o JSON colado tem os campos obrigatórios.

    Args:
        trans_data: Dicionário com dados da transação
        trans_type: Tipo esperado (PIX, DEBITO, CREDITO) ou None para auto-detectar

    Returns:
        (is_valid: bool, errors: list of strings)
    """
    errors = []

    if not trans_data:
        return False, ["JSON vazio ou não carregado"]

    # Campos universalmente obrigatórios
    if not trans_data.get("amount") and trans_data.get("amount") != 0:
        errors.append("'amount' é obrigatório")

    if not trans_data.get("number"):
        errors.append("'number' é obrigatório")

    # Detectar tipo se não informado
    if not trans_type:
        if "payment_fields" in trans_data:
            product_code = trans_data["payment_fields"].get("primaryProductCode")
            if product_code == 25:
                trans_type = "PIX"
            elif product_code == 2000:
                trans_type = "DEBITO"
            elif product_code == 1000:
                trans_type = "CREDITO"

    # Validação por tipo
    if trans_type == "PIX":
        if not trans_data.get("payment_fields"):
            errors.append("'payment_fields' é obrigatório para PIX")
        elif not trans_data["payment_fields"].get("merchantName"):
            errors.append("'payment_fields.merchantName' é obrigatório para PIX")

    elif trans_type == "DEBITO":
        if not trans_data.get("card"):
            errors.append("'card' é obrigatório para DÉBITO")
        elif not trans_data["card"].get("mask") or not trans_data["card"].get("brand"):
            errors.append("'card.mask' e 'card.brand' são obrigatórios para DÉBITO")

        if not trans_data.get("authorization_code"):
            errors.append("'authorization_code' é obrigatório para DÉBITO")

        if not trans_data.get("payment_fields"):
            errors.append("'payment_fields' é obrigatório para DÉBITO")
        elif not trans_data["payment_fields"].get("merchantName"):
            errors.append("'payment_fields.merchantName' é obrigatório para DÉBITO")

    elif trans_type == "CREDITO":
        if not trans_data.get("card"):
            errors.append("'card' é obrigatório para CRÉDITO")
        elif not trans_data["card"].get("mask") or not trans_data["card"].get("brand"):
            errors.append("'card.mask' e 'card.brand' são obrigatórios para CRÉDITO")

        if not trans_data.get("authorization_code"):
            errors.append("'authorization_code' é obrigatório para CRÉDITO")

        if not trans_data.get("payment_fields"):
            errors.append("'payment_fields' é obrigatório para CRÉDITO")
        elif not trans_data["payment_fields"].get("merchantName"):
            errors.append("'payment_fields.merchantName' é obrigatório para CRÉDITO")
        # numberOfQuotas pode ser 0 em JSONs colados, então apenas verificar se existe a chave
        elif "numberOfQuotas" not in trans_data["payment_fields"]:
            errors.append("'payment_fields.numberOfQuotas' é obrigatório para CRÉDITO")

    return len(errors) == 0, errors


def normalize_amount_from_json(amount_value) -> float:
    """
    Normaliza o amount para Reais quando vem do JSON (centavos).

    O Hybris SEMPRE envia amount em centavos (inteiro).
    Exemplos:
    - 33 centavos = R$ 0,33
    - 100 centavos = R$ 1,00
    - 284050 centavos = R$ 2840,50

    Args:
        amount_value: Valor em centavos (int) ou string

    Returns:
        Valor normalizado em Reais (float)
    """
    if amount_value is None:
        return 0.0

    # Hybris sempre envia em centavos (inteiro)
    # Converter para float primeiro se for string
    try:
        if isinstance(amount_value, str):
            amount_value = float(amount_value)

        # Converter centavos para Reais (dividir por 100)
        # Isso funciona para qualquer valor: 33 → 0.33, 100 → 1.00, 284050 → 2840.50
        return float(amount_value) / 100
    except (ValueError, TypeError):
        return 0.0


def try_fix_incomplete_json(json_str: str) -> str:
    """
    Tenta corrigir JSONs incompletos ou mal formados.

    Estratégias:
    1. Remove símbolos extras no final (] } etc)
    2. Se não começa com {, adiciona
    3. Se não termina com }, adiciona
    4. Remove vírgula final antes de adicionar }
    5. Tenta várias combinações de chaves de fechamento

    Args:
        json_str: String JSON potencialmente incompleta ou mal formada

    Returns:
        String JSON corrigida (ou original se não conseguir)
    """
    json_str = json_str.strip()

    # Se JSON está vazio, retorna
    if not json_str:
        return json_str

    # Estratégia PRÉ-0: Corrigir estrutura básica (adicionar { se falta)
    original_json_str = json_str

    # Primeiro: adicionar { no início se não houver
    if not json_str.startswith('{'):
        json_str = '{\n' + json_str

    # Segundo: encontrar a posição do primeiro } que fecha o objeto raiz
    # e remover tudo após ele
    brace_count = 0
    last_valid_brace_pos = -1

    for i, char in enumerate(json_str):
        if char == '{':
            brace_count += 1
        elif char == '}':
            brace_count -= 1
            if brace_count == 0:
                # Encontrou o fechamento do objeto raiz
                last_valid_brace_pos = i + 1
                break

    if last_valid_brace_pos > 0:
        json_str = json_str[:last_valid_brace_pos]

    # Se agora está vazio, retorna original
    if not json_str:
        return original_json_str

    # Se já está bem formado, retorna
    if json_str.startswith('{') and json_str.endswith('}'):
        try:
            json.loads(json_str)
            return json_str
        except json.JSONDecodeError:
            pass

    # Estratégia 1: Adicionar } no final
    if not json_str.endswith('}'):
        if json_str.endswith(','):
            # Remove vírgula e adiciona }
            fixed = json_str.rstrip(',').rstrip() + '\n}'
        else:
            # Adiciona direto
            fixed = json_str + '\n}'

        # Tentar fazer parse para validar
        try:
            json.loads(fixed)
            return fixed
        except json.JSONDecodeError:
            pass

    # Estratégia 2: Tentar adicionar múltiplos } (para JSONs mais complexos)
    for num_braces in range(2, 6):
        fixed = json_str.rstrip(',').rstrip()
        if not fixed.startswith('{'):
            fixed = '{\n' + fixed
        fixed = fixed + '\n' + ('}' * num_braces)
        try:
            json.loads(fixed)
            return fixed
        except json.JSONDecodeError:
            pass

    # Se nenhuma estratégia funcionou, retorna original
    return original_json_str


def extract_transaction_from_hybris(data: dict) -> dict:
    """
    Extrai a transação de diferentes formatos que o Hybris pode retornar.

    Inteligentemente detecta e navega por múltiplos níveis de aninhamento,
    suportando diversos formatos de resposta da API Hybris.

    Suporta:
    1. Objeto direto: { "id": "...", "amount": ... }
    2. Com chave "transaction": { "transaction": { "id": "...", ... } }
    3. Com chave "trasaction" (typo): { "trasaction": { "id": "...", ... } }
    4. Com chave "transactions" (array): { "transactions": [{ "id": "...", ... }] }
    5. Aninhado com order: { "id": "order", "trasaction": { "id": "trans", ... } }
    6. Múltiplos campos + transação: { "id": "...", "order_id": "...", "transactions": [...] }

    Args:
        data: Dict com a transação em qualquer formato

    Returns:
        Dict com a transação extraída, ou Dict vazio se não encontrar
    """
    # Estratégia 1: Se for um objeto direto com "id" e "amount", retornar como está
    # (indica que é a transação própria)
    if data.get("id") and data.get("amount"):
        return data

    # Estratégia 2: Procurar por chaves conhecidas de transação (em ordem de prioridade)
    transaction_keys = ["transaction", "trasaction", "transactions"]

    for key in transaction_keys:
        if key in data:
            value = data[key]

            # Se for um dict direto, retornar
            if isinstance(value, dict):
                # Verificar se é a transação ou se precisa descer mais
                if value.get("id") and value.get("amount"):
                    return value
                # Se não tem amount, pode estar em outro nível (improvável mas seguro)
                return value

            # Se for um array, pegar o primeiro elemento
            if isinstance(value, (list, tuple)) and len(value) > 0:
                first_item = value[0]
                if isinstance(first_item, dict):
                    if first_item.get("id") and first_item.get("amount"):
                        return first_item
                    return first_item

    # Estratégia 3: Se não encontrou nas chaves conhecidas, procurar recursivamente
    # por um objeto que tem "id" e "amount" em qualquer nível
    for key, value in data.items():
        if isinstance(value, dict):
            # Tentar extrair recursivamente
            if value.get("id") and value.get("amount"):
                return value

            # Se for um array, tentar o primeiro elemento
            if isinstance(value, (list, tuple)) and len(value) > 0:
                first_item = value[0]
                if isinstance(first_item, dict) and first_item.get("id") and first_item.get("amount"):
                    return first_item

    # Estratégia 4: Se o objeto tem muitos campos mas não tem "amount",
    # procurar por "amount" dentro de sub-objetos
    for key, value in data.items():
        if isinstance(value, dict) and value.get("amount"):
            return value

    # Se nada encontrar, retornar o original
    # (pode ser que já seja a transação correta mesmo sem amount no nível superior)
    return data

# ═══════════════════════════════════════════════════════════════════════
# STARTUP - Executa ao inicializar a aplicação
# ═══════════════════════════════════════════════════════════════════════
# AGORA todos as funções já estão definidas, seguro chamar!

# ✨ PASSO 0: Garantir que tabela de histórico existe
try:
    _db_init = PostgresManager()
    _db_init.ensure_pedidos_table_exists()
    print("[startup] OK: Tabela pedidos_gerados verificada")
except Exception as _e:
    print(f"[startup] AVISO: Nao foi possivel verificar tabela pedidos_gerados: {_e}")
sys.stdout.flush()

# ✨ PASSO 1: Carregar credenciais DO POSTGRESQL (fonte de verdade)
print("[startup] PASSO 1: Carregando credenciais")
sys.stdout.flush()
credentials = load_credentials()
usuarios_carregados = list(credentials.get('users', {}).keys())
print(f"[startup] Usuarios carregados: {usuarios_carregados}")
sys.stdout.flush()

# ✨ PASSO 2: Sincronizar credenciais para config.yaml (para streamlit-authenticator)
# Isso CONVERTE de credentials.json (PostgreSQL) para o formato do config.yaml
print("\n[startup] PASSO 2: Sincronizando para config.yaml")
sys.stdout.flush()
sync_status = False
try:
    sync_credentials_to_config(credentials)
    sync_status = True
    print("[startup] OK: Sincronizacao concluida com sucesso")
except Exception as e:
    print(f"[startup] ERRO critico ao sincronizar: {e}")
    import traceback
    traceback.print_exc()
    sync_status = False
sys.stdout.flush()

# ✨ PASSO 3: AGORA inicializar o authenticator (com dados já sincronizados)
print(f"\n[startup] PASSO 3: Inicializando authenticator (sync_status={sync_status})")
sys.stdout.flush()
authenticator = load_authenticator()
sys.stdout.flush()

# ✨ Inicializar flag de logout se não existir
if "should_logout" not in st.session_state:
    st.session_state.should_logout = False

# ✨ Se usuário clicou em logout, limpar ANTES de renderizar qualquer coisa
if st.session_state.should_logout:
    st.session_state.clear()
    st.rerun()

# Renderizar widget de login
auth_error = None
try:
    authenticator.login()
except Exception as e:
    # Erro ao exibir widget de login
    auth_error = str(e)
    print(f"DEBUG: Erro de autenticação: {auth_error}")

# Verificar se o usuário está autenticado
if st.session_state.get("authentication_status") == True:
    # ✅ Usuário logado com sucesso
    authenticator.logout(location="sidebar")

    # ✨ Atualizar last_login no PostgreSQL
    try:
        username = st.session_state.get("username", "")
        if username:
            db = PostgresManager()
            db.update_last_login(username)
    except Exception:
        pass  # Falha silenciosa para não bloquear o acesso

    # Continuar com o aplicativo (resto do código)

elif st.session_state.get("authentication_status") == False:
    # ❌ Credenciais inválidas
    st.error("❌ Usuário ou senha incorretos")
    st.divider()
    st.info("💡 Credenciais não reconhecidas. Clique abaixo para limpar a sessão e tentar novamente.")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 Tentar Novamente", use_container_width=True, key="retry_btn"):
            st.session_state.should_logout = True
    with col2:
        if st.button("🔓 Limpar Sessão Completa", use_container_width=True, type="secondary", key="clear_btn"):
            st.session_state.should_logout = True
    st.stop()

elif auth_error:
    if "not authorized" in auth_error.lower():
        # Cookie JWT inválido — apagar o cookie via authenticator e recarregar automaticamente
        # (st.session_state.clear() sozinho não apaga o cookie do browser)
        try:
            authenticator.logout()
        except Exception:
            pass
        st.session_state.clear()
        st.rerun()
    else:
        # Outro erro de autenticação — mostrar para diagnóstico
        st.error(f"❌ Erro ao exibir widget de login")
        st.divider()
        st.subheader("⚠️ Erro de Autenticação")
        st.warning(f"**Erro**: {auth_error}")
        st.info("Clique em **Fazer Logout** para limpar a sessão e tentar novamente.")
        if st.button("🔓 Fazer Logout", use_container_width=True, type="primary", key="logout_btn"):
            try:
                authenticator.logout()
            except Exception:
                pass
            st.session_state.clear()
            st.rerun()
        st.stop()

else:
    # ⏳ Não tentou fazer login ainda
    st.warning("⚠️ Por favor, faça login para continuar")
    st.stop()

# ═══════════════════════════════════════════════════════════════════════
# CONFIGURAÇÃO DA PÁGINA - Personalizações do Streamlit
# ═══════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="Gerador JSON Hybris",   # Título que aparece na aba do navegador
    page_icon="🚀",                     # Ícone da aba
    layout="wide",                      # Layout largo (sem bordas laterais)
    initial_sidebar_state="expanded"    # Sidebar começa expandida
)

# ═══════════════════════════════════════════════════════════════════════
# FORÇA TEMA ESCURO - Configuração direta em JavaScript
# ═══════════════════════════════════════════════════════════════════════

# Injetar JavaScript para forçar tema escuro (caso config.toml não funcione)
st.markdown("""
<script>
    // Força tema escuro no Streamlit
    let darkModeToggle = document.querySelector('[data-testid="stAppViewContainer"]');
    if (darkModeToggle) {
        // Tenta mudar tema para dark
        document.documentElement.setAttribute('data-theme', 'dark');
    }
</script>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════
# CSS CUSTOMIZADO - Estilos visuais para a aplicação
# ═══════════════════════════════════════════════════════════════════════

st.markdown("""
<style>
    # Estilos para o cabeçalho principal
    .main-header {
        font-size: 2.5rem;              # Tamanho grande do texto
        color: #1f77b4;                 # Cor azul
        text-align: center;             # Centralizar
        margin-bottom: 2rem;            # Espaço embaixo
    }

    # Estilos para caixa de sucesso (verde)
    .success-box {
        padding: 1rem;                  # Espaço interno
        background-color: #d4edda;      # Fundo verde claro
        border: 1px solid #c3e6cb;      # Borda verde
        border-radius: 0.25rem;         # Cantos ligeiramente arredondados
        color: #155724;                 # Texto verde escuro
    }

    # Estilos para caixa de erro (vermelho)
    .error-box {
        padding: 1rem;
        background-color: #f8d7da;      # Fundo vermelho claro
        border: 1px solid #f5c6cb;      # Borda vermelha
        border-radius: 0.25rem;
        color: #721c24;                 # Texto vermelho escuro
    }

    # Estilos para caixa de informação (azul)
    .info-box {
        padding: 1rem;
        background-color: #d1ecf1;      # Fundo azul claro
        border: 1px solid #bee5eb;      # Borda azul
        border-radius: 0.25rem;
        color: #0c5460;                 # Texto azul escuro
    }

    /* Scroll horizontal para abas - v6.0 - Força scroll no tab-list */

    /* Remover overflow hidden de TODOS os containers pais */
    .main .block-container,
    .stTabs,
    [data-testid="stTabs"],
    .stTabs > div,
    [data-testid="stTabs"] > div {
        overflow-x: visible !important;
        overflow-y: visible !important;
    }

    /* Tab list - AQUI fica o scroll */
    .stTabs [data-baseweb="tab-list"],
    [data-testid="stTabs"] [role="tablist"],
    div[role="tablist"] {
        overflow-x: auto !important;
        overflow-y: hidden !important;
        display: flex !important;
        flex-wrap: nowrap !important;
        white-space: nowrap !important;
        width: 100% !important;
        /* Firefox */
        scrollbar-width: thin !important;
        scrollbar-color: #1f77b4 #f0f0f0 !important;
    }

    /* Scrollbar styling (Webkit - Chrome/Edge/Safari) */
    .stTabs [data-baseweb="tab-list"]::-webkit-scrollbar,
    [data-testid="stTabs"] [role="tablist"]::-webkit-scrollbar,
    div[role="tablist"]::-webkit-scrollbar {
        height: 10px !important;
        display: block !important;
    }

    .stTabs [data-baseweb="tab-list"]::-webkit-scrollbar-track,
    [data-testid="stTabs"] [role="tablist"]::-webkit-scrollbar-track,
    div[role="tablist"]::-webkit-scrollbar-track {
        background: #f0f0f0 !important;
        border-radius: 5px !important;
    }

    .stTabs [data-baseweb="tab-list"]::-webkit-scrollbar-thumb,
    [data-testid="stTabs"] [role="tablist"]::-webkit-scrollbar-thumb,
    div[role="tablist"]::-webkit-scrollbar-thumb {
        background: #1f77b4 !important;
        border-radius: 5px !important;
    }

    .stTabs [data-baseweb="tab-list"]::-webkit-scrollbar-thumb:hover,
    [data-testid="stTabs"] [role="tablist"]::-webkit-scrollbar-thumb:hover,
    div[role="tablist"]::-webkit-scrollbar-thumb:hover {
        background: #1565c0 !important;
    }

    /* Cada tab individual - compacta mas legível */
    .stTabs [data-baseweb="tab"],
    [data-testid="stTabs"] [role="tab"],
    div[role="tab"] {
        min-width: 80px !important;
        max-width: 150px !important;
        flex-shrink: 0 !important;
        padding: 8px 12px !important;
        font-size: 0.9rem !important;
    }
</style>

<script>
// Força scroll nas tabs após carregamento - v6.0
(function() {
    function enableTabScroll() {
        // Encontra todos os possíveis seletores de tab-list
        const selectors = [
            '[data-baseweb="tab-list"]',
            '[role="tablist"]'
        ];

        selectors.forEach(selector => {
            const tabLists = document.querySelectorAll(selector);
            tabLists.forEach(tabList => {
                // Força propriedades de scroll via JavaScript
                tabList.style.overflowX = 'auto';
                tabList.style.overflowY = 'hidden';
                tabList.style.display = 'flex';
                tabList.style.flexWrap = 'nowrap';
                tabList.style.whiteSpace = 'nowrap';
                tabList.style.width = '100%';

                console.log('✅ Scroll habilitado em:', selector, tabList);
            });
        });
    }

    // Executa imediatamente
    enableTabScroll();

    // Executa novamente após 100ms (caso Streamlit re-renderize)
    setTimeout(enableTabScroll, 100);

    // Executa ao detectar mudanças no DOM
    const observer = new MutationObserver(enableTabScroll);
    observer.observe(document.body, { childList: true, subtree: true });
})();
</script>
""", unsafe_allow_html=True)  # unsafe_allow_html=True permite usar HTML/CSS puro

# ═══════════════════════════════════════════════════════════════════════
# TÍTULO PRINCIPAL - Cabeçalho da aplicação
# ═══════════════════════════════════════════════════════════════════════

# Renderiza o título usando a classe CSS "main-header" definida acima
st.markdown('<h1 class="main-header">🚀 Gerador de JSON (Fake Callback) -  Hybris</h1>', unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════
# SIDEBAR - Barra lateral com instruções e informações
# ═══════════════════════════════════════════════════════════════════════

# O contexto "with st.sidebar:" cria uma área na barra lateral esquerda
with st.sidebar:
    # Logo da empresa
    logo_path = Path(__file__).parent.parent / "img" / "logo_S2.png"
    if logo_path.exists():
        st.image(str(logo_path), width='stretch')
        st.markdown("---")

    # MENU PRINCIPAL - Escolher entre Gerador JSON ou Gerenciar Usuários
    menu_option = st.radio(
        "📋 Escolha uma opção:",
        ["🚀 Gerador JSON", "👥 Gerenciar Usuários", "📊 Histórico"],
        help="Selecione o que deseja fazer"
    )

    st.markdown("---")

    if menu_option == "👥 Gerenciar Usuários":
        page_admin_users()
        st.stop()

    if menu_option == "📊 Histórico":
        page_historico()
        st.stop()

    # Caso contrário, continuar com Gerador JSON
    st.header("📋 Instruções")
    st.markdown("""
    ### Como usar:

    1. **Cole o JSON do cabeçalho** obtido no Hybris
    2. **Selecione o tipo** de transação
    3. **Preencha os campos** específicos
    4. **Clique em "Gerar JSON"**
    5. **Clique em "Enviar JSON"** para postar direto na API Hybris

    ---

    ### Tipos de Transação:
    - **PIX**: Pagamento instantâneo
    - **DÉBITO**: Cartão de débito
    - **CRÉDITO**: Cartão de crédito (parcelado)
    - **MÚLTIPLAS**: Combinação de pagamentos

    ---

    ### Suporte:
    - Em caso de dúvida, consulte a documentação
    - Todos os IDs são gerados automaticamente
    - Timestamps usam timezone do Brasil
    """)

    st.info("**Versão:** 2.0\n\n**Status:** Operacional ✅")

# Área principal do formulário
st.markdown("---")

# SEÇÃO 1: JSON DO CABEÇALHO
st.subheader("1️⃣ JSON do Cabeçalho (do Hybris)")

st.info("ℹ️ **Importante:** Cole TODO o JSON do pedido ATÉ ANTES do campo `\"transactions\"`. Pode terminar com vírgula - o sistema corrige automaticamente.")

# Inicializar session_state para o header se não existir
if "header_json_input" not in st.session_state:
    st.session_state.header_json_input = ""

header_json_str = st.text_area(
    "Cole aqui o JSON do cabeçalho do pedido (até antes de 'transactions'):",
    value=st.session_state.header_json_input,
    height=300,
    placeholder="""{
  "id": "c777434f-a679-4298-9803-12d069a4a13d",
  "items": [{
    "id": 1186914740,
    "sku": "08389316",
    "name": "Leandro teixeira Filipe",
    "uuid": "fedcb39b-09d9-4951-9415-8b5a88522662",
    "details": null,
    "order_id": 3741538564,
    "quantity": 1,
    "created_at": "2022-09-09T14:58:12Z",
    "unit_price": 599000,
    "updated_at": "2022-09-09T14:58:12Z",
    ...
  }],
  "price": 599000,
  "number": "08389316",
  "status": "PAID",
  "reference": "Leandro teixeira Filipe",
  "created_at": "2022-09-09T14:58:12Z",
  "updated_at": "2022-09-09T14:58:12Z",

OU (com vírgula no final também funciona):
  ...
  "updated_at": "2022-09-09T14:58:12Z",
""",
    help="Cole até antes de 'transactions'. Pode ter vírgula no final - o sistema corrige.",
    key="header_json_input"
)

st.markdown("---")

# SEÇÃO 2: DADOS DO CLIENTE
st.subheader("2️⃣ Dados do Cliente")

st.info("ℹ️ **Número do Pedido** e **Nome do Cliente** são preenchidos automaticamente do cabeçalho. Preencha apenas o **CPF**.")

col_d1, col_d2, col_d3 = st.columns(3)

with col_d1:
    numero_pedido_val = st.text_input(
        "Número do Pedido *",
        placeholder="Ex: 21381859",
        help="Preenchido automaticamente do cabeçalho (campo 'number')",
        key="numero_pedido_input"
    )

with col_d2:
    nome_cliente_val = st.text_input(
        "Nome do Cliente *",
        placeholder="Ex: RENATO BARBOSA RIBEIRO",
        help="Preenchido automaticamente do cabeçalho (items[0].name)",
        key="nome_cliente_input"
    )

with col_d3:
    cpf_cliente_val = st.text_input(
        "CPF do Cliente *",
        placeholder="Ex: 123.456.789-00",
        help="Preencha o CPF do cliente no formato XXX.XXX.XXX-XX",
        key="cpf_cliente_input"
    )

st.markdown("---")

# SEÇÃO 3: MERCHANT NAME (OBRIGATÓRIO)
st.subheader("3️⃣ MerchantName (Obrigatório)")

st.info("ℹ️ **Importante:** Este campo será usado em TODAS as transações. Personalize com o nome da pessoa e assunto do email de solicitação.")

# Inicializar session_state para merchant_name global se não existir
# Usar merchantName personalizado para o usuário logado
if "global_merchant_name" not in st.session_state:
    logged_username = st.session_state.get("username", "")
    st.session_state.global_merchant_name = get_merchant_name_for_user(logged_username, credentials)

global_merchant_name = st.text_input(
    "MerchantName *",
    value=st.session_state.global_merchant_name,
    placeholder="Ex: Fake callback - Kennedy - RE: Transferência de 15/11/2024",
    help="Personalize este campo com o nome da pessoa e o assunto da operação (já vem pré-preenchido com seu nome)",
    key="global_merchant_name"
)

st.markdown("---")

# SEÇÃO 4: TIPO DE TRANSAÇÃO
st.subheader("4️⃣ Tipo de Transação")

transaction_type = st.selectbox(
    "Selecione o tipo de transação:",
    ["", "PIX", "DEBITO", "CREDITO", "MULTIPLAS"],
    help="Escolha o tipo de pagamento que será vinculado",
    key="transaction_type_select"
)

# Se mudou o tipo de transação, resetar flag de JSON gerado
if 'previous_transaction_type' not in st.session_state:
    st.session_state.previous_transaction_type = transaction_type
elif st.session_state.previous_transaction_type != transaction_type:
    st.session_state.json_generated = False
    st.session_state.generated_result = None
    st.session_state.generated_result_obj = None
    st.session_state.previous_transaction_type = transaction_type

st.markdown("---")

# Inicializar variáveis
transactions_data = []
result_json = None
error_message = None
prefill_data = None  # Inicializar prefill_data (removida seção 2.1)

# Inicializar session_state para controlar regeneração
if 'json_generated' not in st.session_state:
    st.session_state.json_generated = False
if 'generated_result' not in st.session_state:
    st.session_state.generated_result = None
if 'generated_result_obj' not in st.session_state:
    st.session_state.generated_result_obj = None
if 'last_header_json_hash' not in st.session_state:
    st.session_state.last_header_json_hash = None

# Detectar mudanças no header JSON para resetar json_generated e auto-preencher dados do cliente
current_header_hash = hashlib.md5(header_json_str.encode()).hexdigest()
if st.session_state.last_header_json_hash != current_header_hash:
    st.session_state.json_generated = False
    st.session_state.generated_result = None
    st.session_state.generated_result_obj = None
    st.session_state.last_header_json_hash = current_header_hash
    # Auto-preencher número do pedido e nome do cliente a partir do novo cabeçalho
    if header_json_str.strip():
        try:
            _cleaned_hdr = try_fix_incomplete_json(header_json_str.strip())
            _tmp_hdr = json.loads(_cleaned_hdr)
            st.session_state.numero_pedido_input = str(_tmp_hdr.get("number", ""))
            _items_tmp = _tmp_hdr.get("items", [])
            if _items_tmp:
                st.session_state.nome_cliente_input = _items_tmp[0].get("name", "")
        except Exception:
            pass
    else:
        st.session_state.numero_pedido_input = ""
        st.session_state.nome_cliente_input = ""
    st.rerun()

# SEÇÃO 5: CAMPOS ESPECÍFICOS POR TIPO
if transaction_type:
    st.subheader(f"5️⃣ Dados da Transação - {transaction_type}")

    # ==================== PIX ====================
    if transaction_type == "PIX":
        # Pergunta: Já existe a transação?
        pix_has_existing = st.radio(
            "Já existe a transação?",
            ["Não", "Sim"],
            index=0,
            help="Se você já tem o JSON desta transação, pode colar aqui",
            key="pix_has_existing"
        )

        # Extrair dados de pré-preenchimento se existirem
        prefill_pix = None
        if prefill_data and len(prefill_data) > 0:
            prefill_pix = prefill_data[0]

        # ========== BLOCO: SIM (Apenas JSON) ==========
        if pix_has_existing == "Sim":
            st.info("ℹ️ Cole o JSON desta transação específica.")

            pix_json_str = st.text_area(
                "Cole aqui o JSON da transação PIX:",
                height=200,
                placeholder="""{
  "amount": 284050,
  "number": "1111111",
  "status": "PAID",
  "payment_fields": {
    "merchantName": "Fake callback ",
    "primaryProductCode": 25
  }
}""",
                key="pix_json_input"
            )

            prefill_pix_json = None
            if pix_json_str.strip():
                try:
                    # Tentar corrigir JSON incompleto
                    cleaned_pix_json = try_fix_incomplete_json(pix_json_str.strip())
                    json_loaded = json.loads(cleaned_pix_json)
                    # Extrair transação de diferentes formatos Hybris
                    prefill_pix_json = extract_transaction_from_hybris(json_loaded)
                    # Normalizar amount: converter centavos para Reais se necessário
                    if prefill_pix_json and "amount" in prefill_pix_json:
                        prefill_pix_json["amount"] = normalize_amount_from_json(prefill_pix_json["amount"])

                    # Validar se tem campos obrigatórios
                    is_valid, errors = validate_json_transaction(prefill_pix_json, "PIX")
                    if not is_valid:
                        st.warning("⚠️ JSON tem problemas:")
                        for error in errors:
                            st.warning(f"  • {error}")
                        prefill_pix_json = None
                    else:
                        st.success("✅ Transação carregada com sucesso!")
                except json.JSONDecodeError as e:
                    st.error(f"❌ Erro ao fazer parse do JSON: {str(e)}")
                    prefill_pix_json = None

            trans_data = prefill_pix_json if prefill_pix_json else {}
            if trans_data:
                # Adicionar merchant_name global se não existir
                if "merchant_name" not in trans_data:
                    trans_data["merchant_name"] = global_merchant_name
                transactions_data = [trans_data]

        # ========== BLOCO: NÃO (Formulário Manual) ==========
        else:
            col1, col2 = st.columns(2)

            with col1:
                pix_amount = st.number_input(
                    "amount *",
                    min_value=0.00,
                    value=prefill_pix.get("amount", 0.0) if prefill_pix else 0.00,
                    step=0.01,
                    format="%.2f",
                    help="Valor da transação em Reais",
                    key="pix_amount_input"
                )

                pix_number = st.text_input(
                    "number *",
                    value=prefill_pix.get("number", "") if prefill_pix else "",
                    help="Número da transação/terminal"
                )

            with col2:
                # Usar merchant_name global (preenchido na seção 2.5)
                pix_merchant_name = st.text_input(
                    "merchantName *",
                    value=global_merchant_name,
                    help="Nome do estabelecimento comercial (preenchido na seção acima)",
                    disabled=True  # Desabilitar pois o valor vem da seção 2.5
                )

                default_auth = ""
                if prefill_pix and prefill_pix.get("authorization_code"):
                    default_auth = prefill_pix["authorization_code"]

                pix_auth_code = st.text_input(
                    "authorization_code (opcional)",
                    value=default_auth,
                    help="Deixe em branco para gerar automaticamente"
                )

            # Preparar dados
            trans_data = {
                "amount": pix_amount,
                "number": pix_number,
                "merchant_name": pix_merchant_name,
                "authorization_code": pix_auth_code if pix_auth_code else None
            }
            # Preservar payment_fields originais se houver pré-preenchimento
            if prefill_pix and prefill_pix.get("payment_fields"):
                trans_data["preserve_payment_fields"] = prefill_pix["payment_fields"]

            # Botão para gerar
            if st.button("🚀 Gerar JSON", type="primary"):
                # Formulário manual - validar campos
                if not pix_number or not pix_merchant_name:
                    st.error("⚠️ Por favor, preencha todos os campos obrigatórios!")
                else:
                    transactions_data = [trans_data]

        # Bloco para JSON colado
        if pix_has_existing == "Sim":
            # Botão para gerar (quando JSON colado)
            if st.button("🚀 Gerar JSON", type="primary", key="pix_gerar_json"):
                # JSON colado - validar apenas número
                if not transactions_data or not transactions_data[0].get("number"):
                    st.error("⚠️ JSON colado precisa ter 'number'!")
                else:
                    transactions_data = [transactions_data[0]]

    # ==================== DÉBITO ====================
    elif transaction_type == "DEBITO":
        # Pergunta: Já existe a transação?
        deb_has_existing = st.radio(
            "Já existe a transação?",
            ["Não", "Sim"],
            index=0,
            help="Se você já tem o JSON desta transação, pode colar aqui",
            key="deb_has_existing"
        )

        # Extrair dados de pré-preenchimento se existirem
        prefill_deb = None
        if prefill_data and len(prefill_data) > 0:
            prefill_deb = prefill_data[0]

        # ========== BLOCO: SIM (Apenas JSON) ==========
        if deb_has_existing == "Sim":
            st.info("ℹ️ Cole o JSON desta transação específica.")

            deb_json_str = st.text_area(
                "Cole aqui o JSON da transação DÉBITO:",
                height=200,
                placeholder="""{
  "amount": 100000,
  "number": "1111111",
  "status": "CONFIRMED",
  "payment_fields": {
    "merchantName": "Fake callback ",
    "primaryProductCode": 2000,
    "authorization_code": "abc123"
  }
}""",
                key="deb_json_input"
            )

            prefill_deb_json = None
            if deb_json_str.strip():
                try:
                    # Tentar corrigir JSON incompleto
                    cleaned_deb_json = try_fix_incomplete_json(deb_json_str.strip())
                    json_loaded = json.loads(cleaned_deb_json)
                    # Extrair transação de diferentes formatos Hybris
                    prefill_deb_json = extract_transaction_from_hybris(json_loaded)
                    # Normalizar amount: converter centavos para Reais se necessário
                    if prefill_deb_json and "amount" in prefill_deb_json:
                        prefill_deb_json["amount"] = normalize_amount_from_json(prefill_deb_json["amount"])

                    # Validar se tem campos obrigatórios
                    is_valid, errors = validate_json_transaction(prefill_deb_json, "DEBITO")
                    if not is_valid:
                        st.warning("⚠️ JSON tem problemas:")
                        for error in errors:
                            st.warning(f"  • {error}")
                        prefill_deb_json = None
                    else:
                        st.success("✅ Transação carregada com sucesso!")
                except json.JSONDecodeError as e:
                    st.error(f"❌ Erro ao fazer parse do JSON: {str(e)}")
                    prefill_deb_json = None

            trans_data = prefill_deb_json if prefill_deb_json else {}
            if trans_data:
                # Adicionar merchant_name global se não existir
                if "merchant_name" not in trans_data:
                    trans_data["merchant_name"] = global_merchant_name
                transactions_data = [trans_data]

        # ========== BLOCO: NÃO (Formulário Manual) ==========
        else:
            col1, col2 = st.columns(2)

            with col1:
                deb_amount = st.number_input(
                    "amount *",
                    min_value=0.00,
                    value=prefill_deb.get("amount", 0.0) if prefill_deb else 0.00,
                    step=0.01,
                    format="%.2f",
                    key="deb_amount_input"
                )

                deb_number = st.text_input(
                    "number *",
                    value=prefill_deb.get("number", "") if prefill_deb else ""
                )

            with col2:
                # Usar merchant_name global (preenchido na seção 2.5)
                deb_merchant_name = st.text_input(
                    "merchantName *",
                    value=global_merchant_name,
                    help="Nome do estabelecimento comercial (preenchido na seção acima)",
                    disabled=True  # Desabilitar pois o valor vem da seção 2.5
                )

                default_auth = ""
                if prefill_deb and prefill_deb.get("authorization_code"):
                    default_auth = prefill_deb["authorization_code"]

                deb_auth_code = st.text_input(
                    "authorization_code *",
                    value=default_auth
                )

            # Preparar dados
            trans_data = {
                "amount": deb_amount,
                "number": deb_number,
                "merchant_name": deb_merchant_name,
                "card_mask": "************XXXX",
                "card_brand": "XXXXXXXX",
                "authorization_code": deb_auth_code
            }
            # Preservar campos originais se houver pré-preenchimento
            if prefill_deb:
                if prefill_deb.get("payment_fields"):
                    trans_data["preserve_payment_fields"] = prefill_deb["payment_fields"]
                if prefill_deb.get("card"):
                    trans_data["preserve_card"] = prefill_deb["card"]
                if prefill_deb.get("external_id"):
                    trans_data["preserve_external_id"] = prefill_deb["external_id"]

            # Botão para gerar
            if st.button("🚀 Gerar JSON", type="primary"):
                # Formulário manual - validar campos
                if not all([deb_number, deb_merchant_name, deb_auth_code]):
                    st.error("⚠️ Por favor, preencha todos os campos obrigatórios!")
                else:
                    transactions_data = [trans_data]

        # Bloco para JSON colado
        if deb_has_existing == "Sim":
            # Botão para gerar (quando JSON colado)
            if st.button("🚀 Gerar JSON", type="primary", key="deb_gerar_json"):
                # JSON colado - validar apenas número
                if not transactions_data or not transactions_data[0].get("number"):
                    st.error("⚠️ JSON colado precisa ter 'number'!")
                else:
                    transactions_data = [transactions_data[0]]

    # ==================== CRÉDITO ====================
    elif transaction_type == "CREDITO":
        # Pergunta: Já existe a transação?
        cred_has_existing = st.radio(
            "Já existe a transação?",
            ["Não", "Sim"],
            index=0,
            help="Se você já tem o JSON desta transação, pode colar aqui",
            key="cred_has_existing"
        )

        # Extrair dados de pré-preenchimento se existirem
        prefill_cred = None
        if prefill_data and len(prefill_data) > 0:
            prefill_cred = prefill_data[0]

        # ========== BLOCO: SIM (Apenas JSON) ==========
        if cred_has_existing == "Sim":
            st.info("ℹ️ Cole o JSON desta transação específica.")

            cred_json_str = st.text_area(
                "Cole aqui o JSON da transação CRÉDITO:",
                height=200,
                placeholder="""{
  "amount": 240000,
  "number": "1111111",
  "status": "CONFIRMED",
  "payment_fields": {
    "merchantName": "Fake callback ",
    "primaryProductCode": 1000,
    "numberOfQuotas": 12,
    "authorization_code": "abc123"
  }
}""",
                key="cred_json_input"
            )

            prefill_cred_json = None
            if cred_json_str.strip():
                try:
                    # Tentar corrigir JSON incompleto
                    cleaned_cred_json = try_fix_incomplete_json(cred_json_str.strip())
                    json_loaded = json.loads(cleaned_cred_json)
                    # Extrair transação de diferentes formatos Hybris
                    prefill_cred_json = extract_transaction_from_hybris(json_loaded)
                    # Normalizar amount: converter centavos para Reais se necessário
                    if prefill_cred_json and "amount" in prefill_cred_json:
                        prefill_cred_json["amount"] = normalize_amount_from_json(prefill_cred_json["amount"])

                    # Validar se tem campos obrigatórios
                    is_valid, errors = validate_json_transaction(prefill_cred_json, "CREDITO")
                    if not is_valid:
                        st.warning("⚠️ JSON tem problemas:")
                        for error in errors:
                            st.warning(f"  • {error}")
                        prefill_cred_json = None
                    else:
                        st.success("✅ Transação carregada com sucesso!")
                except json.JSONDecodeError as e:
                    st.error(f"❌ Erro ao fazer parse do JSON: {str(e)}")
                    prefill_cred_json = None

            trans_data = prefill_cred_json if prefill_cred_json else {}
            if trans_data:
                # Adicionar merchant_name global e extrair numberOfQuotas
                if "merchant_name" not in trans_data:
                    trans_data["merchant_name"] = global_merchant_name

                # Extrair numberOfQuotas do JSON colado se existir em payment_fields
                if trans_data.get("payment_fields") and trans_data["payment_fields"].get("numberOfQuotas"):
                    trans_data["number_of_quotas"] = trans_data["payment_fields"].get("numberOfQuotas")

                transactions_data = [trans_data]

        # ========== BLOCO: NÃO (Formulário Manual) ==========
        else:
            col1, col2 = st.columns(2)

            with col1:
                cred_amount = st.number_input(
                    "amount *",
                    min_value=0.00,
                    value=prefill_cred.get("amount", 0.0) if prefill_cred else 0.00,
                    step=0.01,
                    format="%.2f",
                    key="cred_amount_input"
                )

                cred_number = st.text_input(
                    "number *",
                    value=prefill_cred.get("number", "") if prefill_cred else ""
                )

                # Determinar valor padrão para numberOfQuotas
                # Opções: vazio (0) ou 1-24
                quotas_options = [""] + [str(i) for i in range(1, 25)]

                default_quotas_index = 0  # Vazio por padrão
                if prefill_cred and prefill_cred.get("payment_fields"):
                    quotas_from_prefill = prefill_cred["payment_fields"].get("numberOfQuotas")
                    if quotas_from_prefill and 1 <= quotas_from_prefill <= 24:
                        default_quotas_index = quotas_from_prefill

                cred_quotas_str = st.selectbox(
                    "numberOfQuotas *",
                    quotas_options,
                    index=default_quotas_index,
                    help="Selecione entre 1 e 24 parcelas"
                )

                # Converter para inteiro (0 se vazio)
                cred_quotas = int(cred_quotas_str) if cred_quotas_str else 0

            with col2:
                # Usar merchant_name global (preenchido na seção 2.5)
                cred_merchant_name = st.text_input(
                    "merchantName *",
                    value=global_merchant_name,
                    help="Nome do estabelecimento comercial (preenchido na seção acima)",
                    disabled=True  # Desabilitar pois o valor vem da seção 2.5
                )

                default_auth = ""
                if prefill_cred and prefill_cred.get("authorization_code"):
                    default_auth = prefill_cred["authorization_code"]

                cred_auth_code = st.text_input(
                    "authorization_code *",
                    value=default_auth
                )

            # Preparar dados
            trans_data = {
                "amount": cred_amount,
                "number": cred_number,
                "merchant_name": cred_merchant_name,
                "number_of_quotas": int(cred_quotas),
                "card_mask": "************XXXX",
                "card_brand": "XXXXXXXX",
                "authorization_code": cred_auth_code
            }
            # Preservar campos originais se houver pré-preenchimento
            if prefill_cred:
                if prefill_cred.get("payment_fields"):
                    trans_data["preserve_payment_fields"] = prefill_cred["payment_fields"]
                if prefill_cred.get("card"):
                    trans_data["preserve_card"] = prefill_cred["card"]
                if prefill_cred.get("external_id"):
                    trans_data["preserve_external_id"] = prefill_cred["external_id"]

            # Botão para gerar
            if st.button("🚀 Gerar JSON", type="primary"):
                # Formulário manual - validar campos
                if not all([cred_number, cred_merchant_name, cred_auth_code]) or cred_quotas == 0:
                    st.error("⚠️ Por favor, preencha todos os campos obrigatórios (incluindo numberOfQuotas)!")
                else:
                    transactions_data = [trans_data]

        # Bloco para JSON colado
        if cred_has_existing == "Sim":
            # Botão para gerar (quando JSON colado)
            if st.button("🚀 Gerar JSON", type="primary", key="cred_gerar_json"):
                # JSON colado - validar apenas número
                if not transactions_data or not transactions_data[0].get("number"):
                    st.error("⚠️ JSON colado precisa ter 'number'!")
                else:
                    transactions_data = [transactions_data[0]]

    # ==================== MÚLTIPLAS TRANSAÇÕES ====================
    elif transaction_type == "MULTIPLAS":
        st.info("ℹ️ Configure cada transação individualmente. A soma dos valores deve ser igual ao 'price' do cabeçalho.")

        # Determinar número de transações baseado em prefill_data ou input do usuário
        default_num_trans = len(prefill_data) if prefill_data else 2

        # Mostrar informação se foi detectado automaticamente
        if prefill_data and len(prefill_data) > 0:
            st.success(f"✅ Detectadas {len(prefill_data)} transações no JSON. Criando {len(prefill_data)} tabs automaticamente...")

        # Número de transações
        num_transactions = st.number_input(
            "Quantas transações?",
            min_value=2,
            max_value=20,
            value=default_num_trans,
            help="Ajuste se necessário. Valor pré-definido com base no JSON colado." if prefill_data else "Entre 2 e 20 transações"
        )

        # Usar session_state para armazenar dados das transações
        if 'multi_transactions' not in st.session_state:
            st.session_state.multi_transactions = []

        # Criar abas para cada transação
        tabs = st.tabs([f"Transação {i+1}" for i in range(int(num_transactions))])

        # Reinicializar temp_transactions a cada render (importante para Streamlit)
        temp_transactions = [None] * int(num_transactions)

        for idx, tab in enumerate(tabs):
            with tab:
                st.markdown(f"### Transação {idx+1}")

                # ========== PERGUNTA: JÁ EXISTE A TRANSAÇÃO? ==========
                has_existing_trans = st.radio(
                    "Já existe a transação?",
                    ["Não", "Sim"],
                    index=0,
                    help="Se você já tem o JSON desta transação, pode colar aqui",
                    key=f"has_existing_{idx}"
                )

                # Variável para armazenar dados extraídos da transação
                prefill_trans = None

                if has_existing_trans == "Sim":
                    st.info("ℹ️ Cole o JSON desta transação específica.")

                    existing_trans_str = st.text_area(
                        f"Cole aqui o JSON da transação {idx+1}:",
                        height=200,
                        placeholder="""{
  "amount": 284050,
  "number": "1111111",
  "status": "PAID",
  "payment_fields": {
    "merchantName": "Fake callback ",
    "authorization_code": "abc123"
  }
}""",
                        key=f"existing_trans_{idx}"
                    )

                    if existing_trans_str.strip():
                        try:
                            # Tentar corrigir JSON incompleto
                            fixed_json_str = try_fix_incomplete_json(existing_trans_str.strip())
                            json_loaded = json.loads(fixed_json_str)
                            # Extrair transação de diferentes formatos Hybris
                            prefill_trans = extract_transaction_from_hybris(json_loaded)
                            # Normalizar amount: converter centavos para Reais se necessário
                            if prefill_trans and "amount" in prefill_trans:
                                prefill_trans["amount"] = normalize_amount_from_json(prefill_trans["amount"])

                            # Validar se tem campos obrigatórios (auto-detectar tipo)
                            is_valid, errors = validate_json_transaction(prefill_trans)

                            # Mostrar validação com st.divider para ser mais visível
                            st.divider()
                            if not is_valid:
                                st.warning(f"⚠️ Transação {idx+1} tem problemas:")
                                for error in errors:
                                    st.warning(f"  • {error}")
                                prefill_trans = None
                            else:
                                st.success(f"✅ Transação {idx+1} carregada com sucesso!")
                        except json.JSONDecodeError as e:
                            st.divider()
                            st.error(f"❌ Erro ao fazer parse do JSON: {str(e)}")
                            prefill_trans = None

                    # Apenas preparar dados do JSON colado
                    trans_data = prefill_trans if prefill_trans else {}
                    if trans_data:
                        # ✨ IMPORTANTE: Sempre usar o merchant_name global (da seção 2.5) para transações MULTIPLAS
                        # Isso garante consistência em todas as transações quando coladas
                        trans_data["merchant_name"] = global_merchant_name

                        # Extrair numberOfQuotas se for CREDITO e passar como number_of_quotas
                        if trans_data.get("payment_fields"):
                            num_quotas = trans_data["payment_fields"].get("numberOfQuotas")
                            if num_quotas and isinstance(num_quotas, int):
                                trans_data["number_of_quotas"] = num_quotas
                        temp_transactions[idx] = trans_data

                else:  # has_existing_trans == "Não"
                    # Mostrar formulário manual APENAS quando responder "Não"

                    # Extrair dados de pré-preenchimento para esta transação específica
                    if prefill_data and idx < len(prefill_data):
                        prefill_trans = prefill_data[idx]
                    else:
                        prefill_trans = None

                    detected_type = "PIX"  # Default

                    if prefill_trans and prefill_trans.get("payment_fields"):
                        product_code = prefill_trans["payment_fields"].get("primaryProductCode", 25)
                        if product_code == 25:
                            detected_type = "PIX"
                        elif product_code == 2000:
                            detected_type = "DEBITO"
                        elif product_code == 1000:
                            detected_type = "CREDITO"

                    # Selecionar tipo de transação
                    type_options = ["PIX", "DEBITO", "CREDITO"]
                    type_index = type_options.index(detected_type) if detected_type in type_options else 0

                    trans_type = st.selectbox(
                        f"Tipo",
                        type_options,
                        index=type_index,
                        key=f"type_{idx}"
                    )

                    col1, col2 = st.columns(2)

                    with col1:
                        default_amount = 0.00
                        if prefill_trans and prefill_trans.get("amount"):
                            default_amount = max(0.00, prefill_trans.get("amount", 0.0))

                        trans_amount = st.number_input(
                            "amount *",
                            min_value=0.00,
                            value=default_amount,
                            step=0.01,
                            format="%.2f",
                            key=f"amount_{idx}"
                        )

                        trans_number = st.text_input(
                            "number *",
                            value=prefill_trans.get("number", "") if prefill_trans else "",
                            key=f"number_{idx}"
                        )

                        # Usar merchant_name global (preenchido na seção 2.5)
                        # IMPORTANTE: Este campo é EDITÁVEL para cada transação se o usuário desejar
                        trans_merchant = st.text_input(
                            "merchantName *",
                            value=global_merchant_name,
                            key=f"merchant_{idx}",
                            help="Nome do estabelecimento comercial. Padrão: valor da seção 2.5. Editar aqui afeta apenas esta transação."
                        )

                    with col2:
                        # Campos condicionais por tipo
                        if trans_type in ["DEBITO", "CREDITO"]:
                            default_auth = ""
                            if prefill_trans and prefill_trans.get("authorization_code"):
                                default_auth = prefill_trans["authorization_code"]

                            trans_auth = st.text_input(
                                "authorization_code *",
                                value=default_auth,
                                key=f"auth_{idx}"
                            )
                        else:
                            trans_auth = None

                        if trans_type == "CREDITO":
                            # Opções: vazio (0) ou 1-24
                            quotas_options = [""] + [str(i) for i in range(1, 25)]

                            default_quotas_index = 0  # Vazio por padrão
                            if prefill_trans and prefill_trans.get("payment_fields"):
                                quotas_from_prefill = prefill_trans["payment_fields"].get("numberOfQuotas")
                                if quotas_from_prefill and 1 <= quotas_from_prefill <= 24:
                                    default_quotas_index = quotas_from_prefill

                            trans_quotas_str = st.selectbox(
                                "numberOfQuotas *",
                                quotas_options,
                                index=default_quotas_index,
                                key=f"quotas_{idx}",
                                help="Selecione entre 1 e 24 parcelas"
                            )

                            # Converter para inteiro (0 se vazio)
                            trans_quotas = int(trans_quotas_str) if trans_quotas_str else 0
                        else:
                            trans_quotas = None

                    # Preparar dados desta transação
                    trans_data = {
                        "type": trans_type,
                        "amount": trans_amount,
                        "number": trans_number,
                        "merchant_name": trans_merchant
                    }

                    if trans_type in ["DEBITO", "CREDITO"]:
                        trans_data["card_mask"] = "************XXXX"
                        trans_data["card_brand"] = "XXXXXXXX"
                        trans_data["authorization_code"] = trans_auth

                    if trans_type == "CREDITO":
                        trans_data["number_of_quotas"] = int(trans_quotas)

                    # Preservar campos originais se houver pré-preenchimento
                    if prefill_trans:
                        if prefill_trans.get("payment_fields"):
                            trans_data["preserve_payment_fields"] = prefill_trans["payment_fields"]
                        if prefill_trans.get("card"):
                            trans_data["preserve_card"] = prefill_trans["card"]
                        if prefill_trans.get("external_id"):
                            trans_data["preserve_external_id"] = prefill_trans["external_id"]

                    temp_transactions[idx] = trans_data

        # Botão para gerar
        if st.button("🚀 Gerar JSON", type="primary"):
            # Filtrar transações válidas (remover None)
            valid_transactions = [t for t in temp_transactions if t is not None]

            # Validar se tem pelo menos 2 transações
            if len(valid_transactions) < 2:
                st.error(f"⚠️ Preencha pelo menos 2 transações! Você preencheu {len(valid_transactions)}.")
            else:
                # Validar campos obrigatórios
                all_valid = True
                for i, trans in enumerate(valid_transactions):
                    # Se for transação colada (JSON pronto), não validar campos do formulário
                    if "type" not in trans:
                        # É um JSON colado pronto - validar apenas número
                        if not trans.get("number"):
                            st.error(f"⚠️ Transação {i+1}: JSON colado precisa ter 'number'!")
                            all_valid = False
                    else:
                        # É transação preenchida manualmente - validar campos completos
                        if not trans.get("number") or not trans.get("merchant_name"):
                            st.error(f"⚠️ Transação {i+1}: Preencha todos os campos obrigatórios!")
                            all_valid = False

                        if trans["type"] in ["DEBITO", "CREDITO"]:
                            if not trans.get("authorization_code"):
                                st.error(f"⚠️ Transação {i+1}: Preencha authorization_code!")
                                all_valid = False

                        if trans["type"] == "CREDITO":
                            if not trans.get("number_of_quotas") or trans.get("number_of_quotas") == 0:
                                st.error(f"⚠️ Transação {i+1}: Preencha numberOfQuotas!")
                                all_valid = False

                if all_valid:
                    transactions_data = valid_transactions

# GERAR JSON (quando há dados a consolidar)
# Esta seção processa e gera o JSON, armazenando em session_state
if transactions_data and not st.session_state.json_generated:
    try:
        # Parse do cabeçalho
        if not header_json_str.strip():
            st.error("❌ Por favor, cole o JSON do cabeçalho!")
        else:
            # Limpar o JSON: remover vírgula final e adicionar } se necessário
            cleaned_json = header_json_str.strip()

            # Se não termina com }, adicionar
            if not cleaned_json.endswith('}'):
                # Remover vírgula final antes de adicionar }
                if cleaned_json.endswith(','):
                    cleaned_json = cleaned_json.rstrip(',').rstrip()
                cleaned_json += '\n}'

            header_json = json.loads(cleaned_json)

            # Forçar silenciosamente o status do cabeçalho para "PAID"
            header_json["status"] = "PAID"

            # Validar se o header tem campos obrigatórios
            is_valid, errors = validate_header_json(header_json)
            if not is_valid:
                st.error("❌ Cabeçalho tem problemas:")
                for error in errors:
                    st.error(f"  • {error}")
            else:
                # Gerar JSON
                generator = HybrisJSONGenerator()
                result = generator.generate_json_with_header(
                    header_json=header_json,
                    transaction_type=transaction_type,
                    transactions_data=transactions_data
                )

                # Verificar se houve erro
                if isinstance(result, dict) and not result.get("success", True):
                    st.error("❌ Erro na validação:")
                    for error in result.get("validation_errors", []):
                        st.error(f"  • {error}")
                else:
                    # Armazenar resultado em session_state
                    result_obj = json.loads(result)
                    st.session_state.generated_result = result
                    st.session_state.generated_result_obj = result_obj
                    st.session_state.json_generated = True

                    # Salvar cada transação no histórico do banco de dados
                    _num_pedido = st.session_state.get("numero_pedido_input", "").strip()
                    _nome_cli = st.session_state.get("nome_cliente_input", "").strip()
                    _cpf_cli = st.session_state.get("cpf_cliente_input", "").strip()
                    _gen_by = st.session_state.get("username", "")
                    if _num_pedido and _cpf_cli:
                        try:
                            _db = PostgresManager()
                            _db.ensure_pedidos_table_exists()  # garante que a tabela existe
                            _saved = 0
                            for _trans in result_obj.get("transactions", []):
                                _ok = _db.save_pedido_transacao(
                                    numero_pedido=_num_pedido,
                                    nome_cliente=_nome_cli,
                                    cpf_cliente=_cpf_cli,
                                    transaction_id=_trans.get("id", ""),
                                    amount=_trans.get("amount", 0),
                                    terminal_number=str(_trans.get("number", "")),
                                    authorization_code=str(_trans.get("authorization_code", "")),
                                    generated_by=_gen_by
                                )
                                if _ok:
                                    _saved += 1
                            print(f"[db] {_saved} transação(ões) salva(s) para pedido {_num_pedido}")
                            st.session_state["_db_save_count"] = _saved
                            st.session_state["_db_save_pedido"] = _num_pedido
                        except Exception as _db_err:
                            print(f"[db] AVISO: Erro ao salvar histórico: {_db_err}")
                            st.session_state["_db_save_count"] = 0
                            st.session_state["_db_save_error"] = str(_db_err)
                    else:
                        print(f"[db] AVISO: numero_pedido ou cpf vazio — histórico não salvo")
                        st.session_state["_db_save_count"] = -1  # CPF vazio

                    st.rerun()  # Reexecuta a página para mostrar resultado

    except json.JSONDecodeError as e:
        st.error(f"❌ Erro ao fazer parse do JSON do cabeçalho: {str(e)}")
        st.info("💡 **Dicas para corrigir o erro:**")
        st.info("• Verifique se há vírgula dupla ou dados duplicados")
        st.info("• Remova qualquer texto após o JSON")
        st.info("• Certifique-se de que não há caracteres extras no final")
        st.info("• Se houver múltiplos JSONs colados, separe um de cada vez")
    except Exception as e:
        st.error(f"❌ Erro ao gerar JSON: {str(e)}")
        st.exception(e)

# MOSTRAR RESULTADO ARMAZENADO
# Mostrar resultado apenas se JSON já foi gerado (evita regeneração ao editar transações)
if st.session_state.json_generated and st.session_state.generated_result:
    st.markdown("---")
    st.subheader("6️⃣ Resultado (Consolidado)")

    # Usar resultado armazenado em session_state (não regenerar)
    result = st.session_state.generated_result
    result_obj = st.session_state.generated_result_obj

    # Mostrar sucesso
    st.success("✅ JSON gerado com sucesso!")

    # Feedback do salvamento no banco de dados
    _save_count = st.session_state.get("_db_save_count")
    if _save_count is not None:
        _save_pedido = st.session_state.get("_db_save_pedido", "")
        if _save_count > 0:
            st.info(f"💾 **{_save_count} transação(ões) salva(s) no histórico** (Pedido {_save_pedido})")
        elif _save_count == -1:
            st.warning("⚠️ **Histórico NÃO salvo** — CPF do cliente não preenchido na Seção 2. Preencha o CPF e gere novamente para registrar.")
        else:
            _db_err_msg = st.session_state.get("_db_save_error", "")
            st.error(f"❌ **Falha ao salvar no histórico**\n\n`{_db_err_msg}`")
            if "_db_save_error" in st.session_state:
                del st.session_state["_db_save_error"]
        del st.session_state["_db_save_count"]
        if "_db_save_pedido" in st.session_state:
            del st.session_state["_db_save_pedido"]

    # Informações do resultado
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Número do Pedido", result_obj["number"])
    with col2:
        st.metric("Total de Transações", len(result_obj["transactions"]))
    with col3:
        st.metric("Valor Total", f"R$ {result_obj['price']/100:.2f}")

    st.markdown("---")

    # COMPARAÇÃO DE TOTAIS: Header vs Transações
    st.markdown("### 💰 Validação de Totais:")

    # O price já foi ajustado automaticamente pelo generator para bater com a soma
    final_total = result_obj["price"]  # em centavos (já ajustado)
    transactions_total = sum(t.get("amount", 0) for t in result_obj["transactions"])

    final_total_reais = final_total / 100
    transactions_total_reais = transactions_total / 100

    # Exibir cards de comparação
    col1, col2 = st.columns(2)

    with col1:
        st.markdown(f"""
        <div style="
            background-color: #f0f2f6;
            padding: 20px;
            border-radius: 10px;
            border-left: 5px solid #3498db;
        ">
            <h4 style="margin-top: 0; color: #333;">📋 Total do Pedido (price)</h4>
            <p style="font-size: 24px; font-weight: bold; color: #3498db; margin: 10px 0;">
                R$ {final_total_reais:,.2f}
            </p>
            <p style="color: #666; font-size: 12px; margin: 0;">
                Valor final do JSON
            </p>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div style="
            background-color: #f0f2f6;
            padding: 20px;
            border-radius: 10px;
            border-left: 5px solid #27ae60;
        ">
            <h4 style="margin-top: 0; color: #333;">💳 Soma das Transações</h4>
            <p style="font-size: 24px; font-weight: bold; color: #27ae60; margin: 10px 0;">
                R$ {transactions_total_reais:,.2f}
            </p>
            <p style="color: #666; font-size: 12px; margin: 0;">
                Soma dos amounts
            </p>
        </div>
        """, unsafe_allow_html=True)

    # Status — sempre vai bater pois o generator ajusta automaticamente
    if final_total == transactions_total:
        st.success("✅ **Totais conferem** — JSON pronto para envio!")
    else:
        st.info(f"ℹ️ O valor do pedido foi ajustado automaticamente para R$ {transactions_total_reais:,.2f} para bater com a soma das transações.")

    st.markdown("---")

    # JSON formatado
    st.markdown("### 📄 JSON Gerado:")
    st.code(result, language="json", line_numbers=True)

    # Botão de ação
    st.markdown("### 💾 Ações:")

    # Toggle modo teste
    modo_teste = st.toggle("🧪 Modo Teste (simula envio sem postar na API)", value=True)

    col1, col2, col3 = st.columns(3)

    with col1:
        # Botão de enviar JSON via POST
        if st.button("🚀 Enviar JSON", type="primary", use_container_width=True):
            API_URL = "https://portal.sensebike.com.br/glstorefront/cielo/lio/pedido/notificar/status"

            if modo_teste:
                # MODO TESTE: mostra o que seria enviado sem fazer o POST real
                st.warning("🧪 **MODO TESTE** — Nenhum dado foi enviado à API.")
                st.markdown(f"**URL:** `{API_URL}`")
                st.markdown("**Método:** `POST`")
                st.markdown("**Header:** `Content-Type: application/json`")
                st.markdown("**Body (JSON que seria enviado):**")
                st.code(result, language="json")
                st.info("✅ JSON válido e pronto para envio. Desative o Modo Teste para enviar de verdade.")
            else:
                # MODO PRODUÇÃO: envia de fato
                try:
                    with st.spinner("Enviando JSON para a API Hybris..."):
                        response = requests.post(
                            API_URL,
                            data=result,
                            headers={"Content-Type": "application/json"},
                            timeout=30
                        )

                    if response.status_code == 200:
                        st.success(f"✅ JSON enviado com sucesso! (HTTP {response.status_code})")
                        if response.text:
                            with st.expander("📄 Resposta da API", expanded=True):
                                st.code(response.text, language="json")
                    else:
                        st.error(f"❌ Erro ao enviar JSON (HTTP {response.status_code})")
                        if response.text:
                            with st.expander("📄 Detalhes do erro"):
                                st.code(response.text)

                except requests.exceptions.Timeout:
                    st.error("❌ Timeout: A API não respondeu em 30 segundos.")
                except requests.exceptions.ConnectionError:
                    st.error("❌ Erro de conexão: Não foi possível conectar à API.")
                except Exception as e:
                    st.error(f"❌ Erro inesperado: {str(e)}")

    with col2:
        # Botão de download (secundário)
        st.download_button(
            label="📥 Baixar JSON",
            data=result,
            file_name=f"hybris_{result_obj['number']}.json",
            mime="application/json",
            use_container_width=True
        )

    with col3:
        # Botão Clear All
        if st.button("🔄 Limpar Tudo", use_container_width=True):
            for key in list(st.session_state.keys()):
                if key in [
                    "json_generated",
                    "generated_result",
                    "generated_result_obj",
                    "previous_transaction_type",
                    "last_header_json_hash",
                    "transaction_type_select",
                    "header_json_input",
                    "global_merchant_name",
                    "numero_pedido_input",
                    "nome_cliente_input",
                    "cpf_cliente_input",
                    "pix_has_existing",
                    "deb_has_existing",
                    "cred_has_existing",
                    "has_existing_trans",
                ]:
                    if key in st.session_state:
                        del st.session_state[key]
            st.rerun()

# Footer
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #666; padding: 2rem 0;">
    <p><strong>Gerador de JSON (Fake Callback) -  Hybris</strong></p>
    <p>Versão 2.0 | Desenvolvido para automação de vinculação de pagamentos</p>
    </div>
""", unsafe_allow_html=True)
