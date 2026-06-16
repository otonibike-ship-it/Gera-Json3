"""
Script de Migração - Adicionar display_name aos usuários existentes

Este script popula o campo display_name para usuários que ainda não o têm,
usando valores padrão baseados no username.

Exemplos:
- kennedy.oliveira → "Kennedy"
- alisson.galvao → "Alisson"
- marcos.fernandes → "Marcos"
- marco → "Marco"

Execução: python tools/migrate_display_names.py
"""

import sys
from pathlib import Path

# Adicionar src ao path para importar PostgresManager
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from postgres_manager import PostgresManager

def get_default_display_name(username: str) -> str:
    """
    Extrai o primeiro nome do username para usar como display_name padrão.

    Args:
        username: Nome de usuário (ex: kennedy.oliveira, marco)

    Returns:
        Primeiro nome capitalizado (ex: Kennedy, Marco)
    """
    # Separar por '.' ou '_' e pegar primeiro elemento
    first_name = username.split('.')[0].split('_')[0]
    return first_name.capitalize()

def migrate_display_names():
    """
    Migra todos os usuários sem display_name, preenchendo com valor padrão.
    """
    print("=" * 60)
    print("🔄 MIGRAÇÃO - Adicionar display_name aos usuários")
    print("=" * 60)
    print()

    db = PostgresManager()

    # Garantir que a coluna display_name existe
    print("1️⃣ Verificando estrutura da tabela...")
    if not db.ensure_table_exists():
        print("❌ Erro ao verificar/criar tabela usuarios")
        return False
    print("✅ Tabela OK (coluna display_name criada se não existia)")
    print()

    # Carregar todos os usuários
    print("2️⃣ Carregando usuários do PostgreSQL...")
    users_data = db.load_all_users()
    users = users_data.get("users", {})

    if not users:
        print("⚠️ Nenhum usuário encontrado no banco de dados!")
        return True

    print(f"✅ {len(users)} usuário(s) encontrado(s)")
    print()

    # Contar usuários que precisam de migração
    needs_migration = []
    for username, user_data in users.items():
        display_name = user_data.get("display_name", "").strip()
        if not display_name:
            needs_migration.append(username)

    if not needs_migration:
        print("✨ Todos os usuários já têm display_name configurado!")
        print()
        print("📋 Resumo:")
        for username, user_data in users.items():
            display_name = user_data.get("display_name", "")
            print(f"   - {username}: '{display_name}' → Fake callback - {display_name}")
        return True

    print(f"3️⃣ Migrando {len(needs_migration)} usuário(s)...")
    print()

    # Migrar cada usuário
    success_count = 0
    for username in needs_migration:
        default_name = get_default_display_name(username)

        print(f"   🔄 {username}")
        print(f"      └─ display_name: '{default_name}'")
        print(f"      └─ MerchantName: 'Fake callback - {default_name}'")

        if db.update_display_name(username, default_name):
            success_count += 1
            print(f"      ✅ Migrado com sucesso!")
        else:
            print(f"      ❌ Erro ao atualizar")
        print()

    # Resumo final
    print("=" * 60)
    print("📊 RESUMO DA MIGRAÇÃO")
    print("=" * 60)
    print(f"Total de usuários: {len(users)}")
    print(f"Precisavam migração: {len(needs_migration)}")
    print(f"Migrados com sucesso: {success_count}")
    print(f"Falhas: {len(needs_migration) - success_count}")
    print()

    if success_count == len(needs_migration):
        print("✅ Migração concluída com sucesso!")
        print()
        print("💡 Agora cada usuário terá seu MerchantName personalizado:")

        # Recarregar para mostrar valores atualizados
        updated_users = db.load_all_users().get("users", {})
        for username in sorted(updated_users.keys()):
            display_name = updated_users[username].get("display_name", "")
            print(f"   - {username} → 'Fake callback - {display_name}'")

        return True
    else:
        print("⚠️ Migração concluída com algumas falhas")
        return False

if __name__ == "__main__":
    try:
        success = migrate_display_names()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ ERRO FATAL: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
