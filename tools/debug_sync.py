#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Script de debug para entender o fluxo de sincronização de credenciais"""

import sys
import json
from pathlib import Path

# Adicionar src ao path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from postgres_manager import PostgresManager
import yaml

print("=" * 80)
print("DEBUG: Sincronizacao de Credenciais")
print("=" * 80)

# PASSO 1: Carregar do PostgreSQL
print("\nPASSO 1: Carregando credenciais do PostgreSQL...")
db = PostgresManager()
db.ensure_table_exists()
db_users = db.load_all_users()

print("Usuarios no PostgreSQL:", list(db_users.get('users', {}).keys()))
for username, user_info in db_users.get('users', {}).items():
    password = user_info.get('password', '').strip()
    print("  - %s:" % username)
    print("      email: %s" % user_info.get('email', 'N/A'))
    print("      password length: %d" % len(password))
    if len(password) > 20:
        print("      password value: %s..." % password[:20])
    else:
        print("      password value: %s" % password)

# PASSO 2: Carregar config.yaml atual
print("\nPASSO 2: Carregando config.yaml atual...")
config_paths = [
    Path.cwd() / "config.yaml",
    Path.cwd().parent / "config.yaml",
]

config_path = None
for path in config_paths:
    if path.exists():
        config_path = path
        break

if config_path:
    print("Encontrado em: %s" % config_path)
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    print("Usuarios no config.yaml ANTES: %s" % list(config.get('credentials', {}).get('usernames', {}).keys()))
else:
    print("config.yaml nao encontrado!")
    config = {'credentials': {'usernames': {}}}

# PASSO 3: Sincronizar
print("\nPASSO 3: Sincronizando credenciais para config.yaml...")
config['credentials']['usernames'] = {}

for username, user_info in db_users.get('users', {}).items():
    password_plain = user_info.get('password', '').strip()

    if not password_plain:
        print("AVISO: Senha vazia para %s" % username)
        password_plain = '%s@123456' % username

    config['credentials']['usernames'][username] = {
        'email': user_info.get('email', '%s@example.com' % username),
        'name': user_info.get('name', username.title()),
        'password': password_plain
    }
    senha_status = '[preenchida]' if password_plain else '[vazia]'
    print("  %s: senha=%s" % (username, senha_status))

# Salvar config.yaml
if config_path:
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
    print("\nconfig.yaml salvo em: %s" % config_path)
else:
    print("\nNao foi possivel salvar config.yaml")

# PASSO 4: Verificar o que foi salvo
print("\nPASSO 4: Verificando config.yaml salvo...")
if config_path:
    with open(config_path, 'r', encoding='utf-8') as f:
        config_salvo = yaml.safe_load(f)

    print("Usuarios salvos no config.yaml: %s" % list(config_salvo.get('credentials', {}).get('usernames', {}).keys()))
    for username, user_data in config_salvo.get('credentials', {}).get('usernames', {}).items():
        print("  - %s:" % username)
        print("      email: %s" % user_data.get('email'))
        senha_status = '[preenchida]' if user_data.get('password') else '[vazia]'
        print("      password: %s" % senha_status)

print("\n" + "=" * 80)
print("Debug concluido!")
print("=" * 80)
