#!/usr/bin/env python3
"""
Script de Migração: JSON → PostgreSQL
Migra usuários de credentials.json para tabela usuarios no PostgreSQL
"""

import json
import psycopg2
from psycopg2 import sql
from datetime import datetime
import sys

# ═══════════════════════════════════════════════════════════════════════
# CONFIGURAÇÕES
# ═══════════════════════════════════════════════════════════════════════

DB_CONFIG = {
    'host': 'u48cw44ccwg4sowco4044goc',  # Container PostgreSQL da aplicação no Coolify
    'port': 5432,
    'database': 'postgres',
    'user': 'postgres',
    'password': 'poMaf572450+@'
}

CREDENTIALS_FILE = 'credentials.json'

# ═══════════════════════════════════════════════════════════════════════
# SQL PARA CRIAR TABELA
# ═══════════════════════════════════════════════════════════════════════

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS usuarios (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(255) NOT NULL,
    name VARCHAR(255),
    password_hash VARCHAR(255) NOT NULL,
    password VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    last_modified TIMESTAMP,
    enabled BOOLEAN DEFAULT TRUE,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_usuarios_username ON usuarios(username);
CREATE INDEX IF NOT EXISTS idx_usuarios_email ON usuarios(email);
"""

# ═══════════════════════════════════════════════════════════════════════
# FUNÇÕES
# ═══════════════════════════════════════════════════════════════════════

def conectar_postgres():
    """Conecta ao PostgreSQL"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        print("✅ Conectado ao PostgreSQL com sucesso!")
        return conn
    except psycopg2.Error as e:
        print(f"❌ Erro ao conectar ao PostgreSQL: {e}")
        sys.exit(1)

def carregar_usuarios_json(arquivo):
    """Carrega usuários do arquivo JSON"""
    try:
        with open(arquivo, 'r', encoding='utf-8') as f:
            data = json.load(f)
        usuarios = data.get('users', {})
        print(f"✅ Carregados {len(usuarios)} usuários do {arquivo}")
        return usuarios
    except FileNotFoundError:
        print(f"❌ Arquivo {arquivo} não encontrado!")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Erro ao ler JSON: {e}")
        sys.exit(1)

def criar_tabela(conn):
    """Cria a tabela usuarios no PostgreSQL"""
    try:
        with conn.cursor() as cur:
            cur.execute(CREATE_TABLE_SQL)
        conn.commit()
        print("✅ Tabela 'usuarios' criada (ou já existe)")
    except psycopg2.Error as e:
        print(f"❌ Erro ao criar tabela: {e}")
        conn.rollback()
        sys.exit(1)

def migrar_usuarios(conn, usuarios_dict):
    """Migra usuários para o PostgreSQL"""
    migrados = 0
    erros = 0

    for username, user_info in usuarios_dict.items():
        try:
            with conn.cursor() as cur:
                # Converter timestamps se forem strings
                created_at = user_info.get('created_at')
                if isinstance(created_at, str):
                    try:
                        created_at = datetime.strptime(created_at, '%Y-%m-%d %H:%M:%S')
                    except:
                        created_at = datetime.now()

                last_modified = user_info.get('last_modified')
                if isinstance(last_modified, str):
                    try:
                        last_modified = datetime.strptime(last_modified, '%Y-%m-%d %H:%M:%S')
                    except:
                        last_modified = None

                # INSERT OR UPDATE (UPSERT)
                sql_upsert = """
                INSERT INTO usuarios (
                    username, email, name, password_hash, password,
                    created_at, last_modified, enabled
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (username) DO UPDATE SET
                    email = EXCLUDED.email,
                    name = EXCLUDED.name,
                    password_hash = EXCLUDED.password_hash,
                    password = EXCLUDED.password,
                    last_modified = EXCLUDED.last_modified,
                    updated_at = CURRENT_TIMESTAMP;
                """

                cur.execute(sql_upsert, (
                    username,
                    user_info.get('email', f'{username}@example.com'),
                    user_info.get('name', username),
                    user_info.get('password_hash', ''),
                    user_info.get('password', ''),
                    created_at,
                    last_modified,
                    user_info.get('enabled', True)
                ))

            conn.commit()
            migrados += 1
            print(f"  ✅ {username} → Migrado com sucesso")

        except psycopg2.Error as e:
            conn.rollback()
            erros += 1
            print(f"  ❌ {username} → Erro: {e}")

    return migrados, erros

def verificar_migracao(conn):
    """Verifica a migração"""
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM usuarios")
            total = cur.fetchone()[0]

            print(f"\n📊 Verificação da Migração:")
            print(f"   Total de usuários no banco: {total}")

            # Listar usuários
            cur.execute("SELECT username, email, enabled FROM usuarios ORDER BY created_at DESC")
            usuarios = cur.fetchall()

            print(f"\n   Usuários migrados:")
            for username, email, enabled in usuarios:
                status = "✅ Ativo" if enabled else "❌ Inativo"
                print(f"   - {username} ({email}) {status}")

    except psycopg2.Error as e:
        print(f"❌ Erro ao verificar: {e}")

# ═══════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════

def main():
    print("=" * 70)
    print("🚀 MIGRAÇÃO: credentials.json → PostgreSQL")
    print("=" * 70)

    # 1. Conectar ao PostgreSQL
    print("\n[1/4] Conectando ao PostgreSQL...")
    conn = conectar_postgres()

    # 2. Criar tabela
    print("\n[2/4] Criando tabela 'usuarios'...")
    criar_tabela(conn)

    # 3. Carregar usuários do JSON
    print("\n[3/4] Carregando usuários do JSON...")
    usuarios = carregar_usuarios_json(CREDENTIALS_FILE)

    # 4. Migrar usuários
    print("\n[4/4] Migrando usuários para PostgreSQL...")
    migrados, erros = migrar_usuarios(conn, usuarios)

    # 5. Verificar
    print("\n" + "=" * 70)
    print(f"✅ Migração Concluída!")
    print(f"   Migrados com sucesso: {migrados}")
    if erros > 0:
        print(f"   Erros: {erros}")

    verificar_migracao(conn)

    # Fechar conexão
    conn.close()
    print("\n✅ Conexão fechada")
    print("=" * 70)

if __name__ == '__main__':
    main()
