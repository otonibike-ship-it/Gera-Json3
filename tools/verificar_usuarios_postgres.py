#!/usr/bin/env python3
"""
Script para verificar usuários no PostgreSQL
Executa apenas uma query SELECT para listar todos os usuários
"""

import psycopg2
import sys

DB_CONFIG = {
    'host': 'u48cw44ccwg4sowco4044goc',
    'port': 5432,
    'database': 'postgres',
    'user': 'postgres',
    'password': 'poMaf572450+@'
}

def verificar_usuarios():
    """Verifica todos os usuários no PostgreSQL"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        with conn.cursor() as cur:
            # Contar total
            cur.execute("SELECT COUNT(*) FROM usuarios")
            total = cur.fetchone()[0]

            print("\n" + "=" * 70)
            print("📊 VERIFICAÇÃO: Usuários no PostgreSQL")
            print("=" * 70)
            print(f"Total de usuários no banco: {total}\n")

            # Listar usuários com detalhes
            cur.execute("""
                SELECT username, email, name, enabled, created_at, last_modified
                FROM usuarios
                ORDER BY created_at DESC
            """)
            usuarios = cur.fetchall()

            if usuarios:
                print(f"{'Username':<20} {'Email':<30} {'Status':<12} {'Criado em':<20}")
                print("-" * 82)
                for username, email, name, enabled, created_at, last_modified in usuarios:
                    status = "Ativo" if enabled else "Inativo"
                    created_str = created_at.strftime('%Y-%m-%d %H:%M:%S') if created_at else 'N/A'
                    print(f"{username:<20} {email:<30} {status:<12} {created_str:<20}")
            else:
                print("⚠️  Nenhum usuário encontrado na tabela!")

            print("=" * 70)

        conn.close()

    except psycopg2.Error as e:
        print(f"❌ Erro ao conectar ao PostgreSQL: {e}")
        sys.exit(1)

if __name__ == '__main__':
    verificar_usuarios()
