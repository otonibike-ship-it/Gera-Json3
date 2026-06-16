#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Debug: Verificar dados de marcos.fernandes no PostgreSQL
"""
import sys
import os

sys.path.insert(0, 'src')
os.chdir(os.path.dirname(os.path.abspath(__file__)))

try:
    from postgres_manager import PostgresManager
    
    db = PostgresManager()
    users = db.load_all_users()
    
    print("\n" + "="*80)
    print("DEBUG: Usuário marcos.fernandes no PostgreSQL")
    print("="*80)
    
    marcos = users.get('users', {}).get('marcos.fernandes', {})
    
    if not marcos:
        print("❌ marcos.fernandes NÃO ENCONTRADO no PostgreSQL!")
        print(f"Usuários disponíveis: {list(users.get('users', {}).keys())}")
    else:
        print(f"✅ marcos.fernandes ENCONTRADO!")
        print(f"\n📊 Dados:")
        for key, value in marcos.items():
            if key == 'password':
                print(f"  - {key}: {'[PREENCHIDO]' if value and value.strip() else '[VAZIO]'}")
                if value:
                    print(f"    Comprimento: {len(value)} caracteres")
                    print(f"    Primeiros 20 chars: {value[:20] if len(value) > 20 else value}")
            else:
                print(f"  - {key}: {value}")
    
    print("\n" + "="*80)

except Exception as e:
    print(f"❌ Erro: {e}")
    import traceback
    traceback.print_exc()
