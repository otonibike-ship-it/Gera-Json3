#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
DIAGNÓSTICO COMPLETO DO PROBLEMA DE AUTENTICAÇÃO

Este script investiga CADA CAMADA do sistema de autenticação.
Rode isto no Coolify para descobrir EXATAMENTE onde está o problema.

Uso:
  cd /app && python diagnostico_completo.py
"""

import sys
import json
from pathlib import Path
import yaml

# Adicionar src ao path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from postgres_manager import PostgresManager

def separator(title):
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)

# =============================================================================
# CAMADA 1: PostgreSQL
# =============================================================================

separator("CAMADA 1: PostgreSQL")

print("\n[1.1] Tentando conectar ao PostgreSQL...")
db = PostgresManager()
print(f"      Host: {db.db_config['host']}")
print(f"      Port: {db.db_config['port']}")
print(f"      User: {db.db_config['user']}")

try:
    db.ensure_table_exists()
    print("      [OK] Conexao bem-sucedida")
except Exception as e:
    print(f"      [ERRO] Nao conseguiu conectar: {e}")
    print("\n      DIAGNÓSTICO:")
    print("      - Verifique variáveis de ambiente (DB_HOST, DB_USER, DB_PASSWORD)")
    print("      - Verifique se PostgreSQL está rodando no Coolify")
    print("      - Verifique firewall/network do Coolify")
    sys.exit(1)

print("\n[1.2] Carregando usuarios do PostgreSQL...")
db_users = db.load_all_users()
users_list = list(db_users.get('users', {}).keys())
print(f"      Total: {len(users_list)} usuarios")
print(f"      Usuarios: {users_list}")

if not users_list:
    print("\n      [AVISO] Nenhum usuario no PostgreSQL!")
    print("      Soluçao: Acesse a interface Streamlit e crie os usuarios")
    sys.exit(1)

print("\n[1.3] Verificando integridade dos dados...")
for username, user_info in db_users.get('users', {}).items():
    password_val = user_info.get('password', '').strip()
    email = user_info.get('email', 'N/A')

    if not password_val:
        print(f"      [AVISO] {username}: senha VAZIA!")
    else:
        print(f"      [OK] {username}: senha ok, email={email}")

# =============================================================================
# CAMADA 2: config.yaml
# =============================================================================

separator("CAMADA 2: config.yaml")

print("\n[2.1] Procurando config.yaml...")
possible_paths = [
    Path.cwd() / "config.yaml",
    Path.cwd().parent / "config.yaml",
    Path(__file__).parent / "config.yaml",
    Path(__file__).parent.parent / "config.yaml",
]

config_path = None
for path in possible_paths:
    if path.exists():
        config_path = path
        print(f"      [OK] Encontrado em: {path}")
        break

if not config_path:
    print("      [ERRO] config.yaml nao encontrado!")
    print(f"      Procurado em:\n" + "\n".join(f"        - {p}" for p in possible_paths))
    sys.exit(1)

print("\n[2.2] Carregando config.yaml...")
try:
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    print("      [OK] Arquivo carregado")
except Exception as e:
    print(f"      [ERRO] Nao conseguiu ler: {e}")
    sys.exit(1)

print("\n[2.3] Verificando estrutura de credenciais...")
credentials = config.get('credentials', {})
usernames = credentials.get('usernames', {})
config_users = list(usernames.keys())

print(f"      Total: {len(config_users)} usuarios no config.yaml")
print(f"      Usuarios: {config_users}")

if not config_users:
    print("\n      [ERRO CRITICO] config.yaml está VAZIO!")
    print("      Isto significa que a sincronização do PostgreSQL NUNCAFOI EXECUTADA")
    print("\n      Proximas verificacoes:")
    print("      1. Rode a app streamlit normalmente")
    print("      2. Verifique os logs para [sync_credentials_to_config]")
    print("      3. Se houver erro, corrija antes de continuar")

print("\n[2.4] Verificando dados de cada usuario...")
for username, user_data in usernames.items():
    if isinstance(user_data, dict):
        password_val = user_data.get('password', '').strip()
        email = user_data.get('email', 'N/A')

        if not password_val:
            print(f"      [AVISO] {username}: senha VAZIA no config.yaml!")
        else:
            print(f"      [OK] {username}: senha ok, email={email}")
    else:
        print(f"      [ERRO] {username}: dados malformados (nao é dict)")

# =============================================================================
# CAMADA 3: Comparação PostgreSQL vs config.yaml
# =============================================================================

separator("CAMADA 3: Comparação PostgreSQL vs config.yaml")

pg_users_set = set(db_users.get('users', {}).keys())
yaml_users_set = set(config_users)

print(f"\nPostgreSQL: {sorted(pg_users_set)}")
print(f"config.yaml: {sorted(yaml_users_set)}")

if pg_users_set == yaml_users_set:
    print("\n[OK] Listas estao sincronizadas!")
else:
    print("\n[ERRO] Listas NAO estao sincronizadas!")

    em_pg_nao_em_yaml = pg_users_set - yaml_users_set
    em_yaml_nao_em_pg = yaml_users_set - pg_users_set

    if em_pg_nao_em_yaml:
        print(f"      Usuarios no PostgreSQL mas NAO em config.yaml: {em_pg_nao_em_yaml}")
        print("      CAUSA: sync_credentials_to_config() nao foi executado ou falhou")

    if em_yaml_nao_em_pg:
        print(f"      Usuarios em config.yaml mas NAO no PostgreSQL: {em_yaml_nao_em_pg}")
        print("      AVISO: Pode ser usuario antigo que foi deletado do BD")

# Verificar senhas sincronizadas
print("\n[3.2] Verificando sincronizacao de senhas...")
for username in pg_users_set:
    pg_user = db_users['users'].get(username, {})
    yaml_user = usernames.get(username, {})

    pg_pass = pg_user.get('password', '').strip() if pg_user else None
    yaml_pass = yaml_user.get('password', '').strip() if isinstance(yaml_user, dict) else None

    if pg_pass and yaml_pass:
        if pg_pass == yaml_pass:
            print(f"      [OK] {username}: senha sincronizada")
        else:
            print(f"      [ERRO] {username}: senha DIFERENTE entre PostgreSQL e config.yaml!")
            print(f"             PostgreSQL: {pg_pass[:20]}...")
            print(f"             config.yaml: {yaml_pass[:20]}...")
    elif not pg_pass and not yaml_pass:
        print(f"      [AVISO] {username}: senha VAZIA em ambos!")
    elif not pg_pass:
        print(f"      [AVISO] {username}: senha VAZIA no PostgreSQL, mas preenchida em config.yaml")
    else:
        print(f"      [ERRO] {username}: senha NO PostgreSQL mas VAZIA em config.yaml!")

# =============================================================================
# CAMADA 4: streamlit-authenticator
# =============================================================================

separator("CAMADA 4: streamlit-authenticator")

print("\n[4.1] Tentando inicializar authenticator...")
try:
    import streamlit_authenticator as stauth

    cookie_settings = config.get('cookie', {})
    authenticator = stauth.Authenticate(
        credentials=credentials,
        cookie_name=cookie_settings.get('name', 'hybris_auth'),
        cookie_key=cookie_settings.get('key', 'secret'),
        cookie_expiry_days=cookie_settings.get('expiry_days', 30)
    )
    print("      [OK] Authenticator inicializado com sucesso")

except Exception as e:
    print(f"      [ERRO] Nao conseguiu inicializar: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n[4.2] Testando login de cada usuario...")
for username in config_users:
    user_data = usernames.get(username, {})
    password = user_data.get('password', '') if isinstance(user_data, dict) else ''

    if not password:
        print(f"      [AVISO] {username}: nao pode testar (senha vazia)")
        continue

    # Teste simulado (sem streamlit)
    print(f"      [INFO] {username}: senha preenchida, pode fazer login")

# =============================================================================
# RESUMO FINAL
# =============================================================================

separator("RESUMO E DIAGNOSTICO")

print("\nSituacao atual:")
print(f"  - PostgreSQL: {len(pg_users_set)} usuarios")
print(f"  - config.yaml: {len(yaml_users_set)} usuarios")
print(f"  - Sincronizado: {'SIM' if pg_users_set == yaml_users_set else 'NAO'}")

if pg_users_set == yaml_users_set and len(yaml_users_set) > 0:
    print("\n[PROVAVEL] Tudo está configurado corretamente!")
    print("\nSe ainda nao consegue fazer login:")
    print("  1. Abra navegador INCOGNITO (ctrl+shift+p no Chrome)")
    print("  2. Tente login com cada usuario")
    print("  3. Se continuar não funcionando, rode este script novamente")
    print("  4. Procure por erros nos logs do Streamlit")

elif len(yaml_users_set) == 0:
    print("\n[PROBLEMA] config.yaml está vazio!")
    print("\nProximas acoes:")
    print("  1. Verifique os logs do Streamlit para erros de sync")
    print("  2. Rode a app novamente")
    print("  3. Execute este script novamente para verificar se foi atualizado")

elif pg_users_set != yaml_users_set:
    print("\n[PROBLEMA] PostgreSQL e config.yaml nao estao sincronizados!")
    print("\nProximas acoes:")
    print("  1. Verifique os logs de sync_credentials_to_config")
    print("  2. Rode a app novamente para forcar sync")
    print("  3. Verifique permissoes do arquivo config.yaml")

print("\n" + "=" * 80)
print("  FIM DO DIAGNÓSTICO")
print("=" * 80 + "\n")
