"""
Gerenciador PostgreSQL - Sincronização de Usuários
Mantém sincronização automática entre aplicação e banco de dados
"""

import psycopg2
from psycopg2 import sql
from datetime import datetime
import os

class PostgresManager:
    """Gerencia operações com PostgreSQL para usuários"""

    def __init__(self):
        """Inicializa configuração do banco de dados a partir de variáveis de ambiente"""
        host = os.getenv('DB_HOST')
        password = os.getenv('DB_PASSWORD')

        if not host or not password:
            raise EnvironmentError(
                "As variáveis de ambiente DB_HOST e DB_PASSWORD são obrigatórias. "
                "Configure-as no Coolify (Settings → Environment Variables) antes de iniciar a aplicação."
            )

        # Schema dedicado (evita depender do 'public', que em bancos
        # compartilhados acumula tabelas de outros sistemas). Padrão
        # 'public' mantém compatibilidade com ambientes que não definirem
        # DB_SCHEMA.
        schema = os.getenv('DB_SCHEMA', 'public')
        self.schema = schema

        self.db_config = {
            'host': host,
            'port': int(os.getenv('DB_PORT', '5432')),
            'database': os.getenv('DB_NAME', 'postgres'),
            'user': os.getenv('DB_USER', 'postgres'),
            'password': password,
            'options': f'-c search_path={schema}'
        }

    def get_connection(self):
        """Obtém conexão com PostgreSQL"""
        try:
            conn = psycopg2.connect(**self.db_config)
            return conn
        except psycopg2.Error as e:
            print(f"❌ Erro ao conectar ao PostgreSQL: {e}")
            return None

    def ensure_table_exists(self):
        """Cria tabela hybris_usuarios se não existir, migra dados da tabela antiga se necessário"""
        try:
            conn = self.get_connection()
            if not conn:
                return False

            with conn.cursor() as cur:
                # Garantir que o schema dedicado existe (no-op se DB_SCHEMA=public)
                cur.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(self.schema)))

                # Criar tabela se não existir
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS hybris_usuarios (
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

                    CREATE INDEX IF NOT EXISTS idx_hybris_usuarios_username ON hybris_usuarios(username);
                    CREATE INDEX IF NOT EXISTS idx_hybris_usuarios_email ON hybris_usuarios(email);
                """)

                # Adicionar coluna display_name se não existir (migration)
                cur.execute("""
                    DO $$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM information_schema.columns
                            WHERE table_name='hybris_usuarios' AND column_name='display_name'
                        ) THEN
                            ALTER TABLE hybris_usuarios ADD COLUMN display_name VARCHAR(100);
                            COMMENT ON COLUMN hybris_usuarios.display_name IS 'Nome de exibição para merchantName (ex: Kennedy, Alisson)';
                        END IF;
                    END $$;
                """)

                # Migração automática: copiar dados da tabela antiga 'usuarios' se existir
                cur.execute("""
                    DO $$
                    BEGIN
                        IF EXISTS (
                            SELECT 1 FROM information_schema.tables
                            WHERE table_name = 'usuarios'
                        ) AND NOT EXISTS (
                            SELECT 1 FROM hybris_usuarios LIMIT 1
                        ) THEN
                            INSERT INTO hybris_usuarios
                                (username, email, name, password_hash, password,
                                 created_at, last_login, last_modified, enabled, updated_at)
                            SELECT username, email, name, password_hash, password,
                                   created_at, last_login, last_modified, enabled, updated_at
                            FROM usuarios
                            ON CONFLICT (username) DO NOTHING;
                            RAISE NOTICE 'Migração: dados copiados de usuarios para hybris_usuarios';
                        END IF;
                    END $$;
                """)

                # Seed/reset do usuário admin via variáveis de ambiente
                # UPSERT: cria na primeira vez, atualiza senha se já existe
                # Permite reset de senha sem acesso ao banco: mudar env var + redeploy
                admin_user = os.getenv('ADMIN_USER', '').strip()
                admin_pass = os.getenv('ADMIN_PASSWORD', '').strip()
                if admin_user and admin_pass:
                    cur.execute("""
                        INSERT INTO hybris_usuarios
                            (username, email, name, password_hash, password, enabled)
                        VALUES (%s, %s, %s, '', %s, TRUE)
                        ON CONFLICT (username) DO UPDATE SET
                            password = EXCLUDED.password,
                            enabled  = TRUE
                    """, (
                        admin_user,
                        f'{admin_user}@sensebike.com.br',
                        admin_user.replace('.', ' ').title(),
                        admin_pass
                    ))
                    print(f"[seed] ADMIN_USER='{admin_user}' sincronizado com senha de ADMIN_PASSWORD")

            conn.commit()
            conn.close()
            return True
        except psycopg2.Error as e:
            print(f"❌ Erro ao criar tabela: {e}")
            return False

    def load_all_users(self) -> dict:
        """
        Carrega TODOS os usuários do PostgreSQL
        Retorna dict no formato de credentials.json: {"users": {...}}
        """
        try:
            conn = self.get_connection()
            if not conn:
                return {"users": {}}

            with conn.cursor() as cur:
                cur.execute("""
                    SELECT username, password_hash, password, email, name,
                           enabled, created_at, last_login, last_modified, display_name
                    FROM hybris_usuarios
                    ORDER BY created_at
                """)
                users = {}
                for row in cur.fetchall():
                    username, password_hash, password, email, name, enabled, \
                    created_at, last_login, last_modified, display_name = row

                    users[username] = {
                        'password_hash': password_hash or '',
                        'password': password or '',
                        'email': email or '',
                        'name': name or username,
                        'enabled': enabled,
                        'created_at': created_at.strftime('%Y-%m-%d %H:%M:%S') if created_at else None,
                        'last_login': last_login.strftime('%Y-%m-%d %H:%M:%S') if last_login else None,
                        'last_modified': last_modified.strftime('%Y-%m-%d %H:%M:%S') if last_modified else None,
                        'display_name': display_name or ''
                    }
            conn.close()
            # Retornar no formato de credentials.json
            return {"users": users, "version": "1.0"}
        except psycopg2.Error as e:
            print(f"❌ Erro ao carregar usuários do PostgreSQL: {e}")
            return {"users": {}}

    def save_user(self, username: str, email: str, name: str,
                  password_hash: str, password: str, enabled: bool = True,
                  display_name: str = None) -> bool:
        """
        Salva/atualiza um usuário no PostgreSQL
        Args:
            display_name: Nome para exibição no merchantName (ex: "Kennedy", "Alisson")
        """
        try:
            conn = self.get_connection()
            if not conn:
                return False

            with conn.cursor() as cur:
                sql_upsert = """
                INSERT INTO hybris_usuarios (username, email, name, password_hash, password, enabled, display_name)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (username) DO UPDATE SET
                    email = EXCLUDED.email,
                    name = EXCLUDED.name,
                    password_hash = EXCLUDED.password_hash,
                    password = EXCLUDED.password,
                    enabled = EXCLUDED.enabled,
                    display_name = EXCLUDED.display_name,
                    updated_at = CURRENT_TIMESTAMP
                """
                cur.execute(sql_upsert, (username, email, name, password_hash, password, enabled, display_name))
            conn.commit()
            conn.close()
            return True
        except psycopg2.Error as e:
            print(f"❌ Erro ao salvar usuário no PostgreSQL: {e}")
            return False

    def delete_user(self, username: str) -> bool:
        """
        Delete usuário do PostgreSQL
        """
        try:
            conn = self.get_connection()
            if not conn:
                return False

            with conn.cursor() as cur:
                cur.execute("DELETE FROM hybris_usuarios WHERE username = %s", (username,))
            conn.commit()
            conn.close()
            return True
        except psycopg2.Error as e:
            print(f"❌ Erro ao deletar usuário do PostgreSQL: {e}")
            return False

    def update_last_login(self, username: str) -> bool:
        """
        Atualiza last_login após login bem-sucedido
        """
        try:
            conn = self.get_connection()
            if not conn:
                return False

            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE hybris_usuarios
                    SET last_login = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE username = %s
                """, (username,))
            conn.commit()
            conn.close()
            return True
        except psycopg2.Error as e:
            print(f"⚠️ Erro ao atualizar last_login: {e}")
            return False

    def user_exists(self, username: str) -> bool:
        """Verifica se usuário existe no PostgreSQL"""
        try:
            conn = self.get_connection()
            if not conn:
                return False

            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM hybris_usuarios WHERE username = %s", (username,))
                result = cur.fetchone()
            conn.close()
            return result[0] > 0 if result else False
        except psycopg2.Error:
            return False

    def get_user_count(self) -> int:
        """Retorna total de usuários no banco"""
        try:
            conn = self.get_connection()
            if not conn:
                return 0

            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM hybris_usuarios")
                result = cur.fetchone()
            conn.close()
            return result[0] if result else 0
        except psycopg2.Error:
            return 0

    def update_display_name(self, username: str, display_name: str) -> bool:
        """
        Atualiza apenas o display_name de um usuário
        Args:
            username: Nome de usuário
            display_name: Nome para exibição (ex: "Kennedy", "Alisson")
        """
        try:
            conn = self.get_connection()
            if not conn:
                return False

            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE hybris_usuarios
                    SET display_name = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE username = %s
                """, (display_name, username))
            conn.commit()
            conn.close()
            return True
        except psycopg2.Error as e:
            print(f"⚠️ Erro ao atualizar display_name: {e}")
            return False

    # ═══════════════════════════════════════════════════════════════════════
    # HISTÓRICO DE PEDIDOS GERADOS
    # ═══════════════════════════════════════════════════════════════════════

    def ensure_pedidos_table_exists(self) -> bool:
        """Cria tabela hybris_pedidos para armazenar histórico de JSONs gerados"""
        try:
            conn = self.get_connection()
            if not conn:
                return False
            with conn.cursor() as cur:
                # Garantir que o schema dedicado existe (no-op se DB_SCHEMA=public)
                cur.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(self.schema)))

                cur.execute("""
                    CREATE TABLE IF NOT EXISTS hybris_pedidos (
                        id SERIAL PRIMARY KEY,
                        numero_pedido VARCHAR(20) NOT NULL,
                        nome_cliente VARCHAR(255),
                        cpf_cliente VARCHAR(14),
                        transaction_id VARCHAR(100),
                        amount BIGINT,
                        terminal_number VARCHAR(50),
                        authorization_code VARCHAR(50),
                        generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        generated_by VARCHAR(100)
                    );
                    CREATE INDEX IF NOT EXISTS idx_pedidos_numero ON hybris_pedidos(numero_pedido);
                    CREATE INDEX IF NOT EXISTS idx_pedidos_cpf ON hybris_pedidos(cpf_cliente);
                    CREATE INDEX IF NOT EXISTS idx_pedidos_generated_at ON hybris_pedidos(generated_at);
                    CREATE INDEX IF NOT EXISTS idx_pedidos_nsu_auth ON hybris_pedidos(terminal_number, authorization_code);
                """)

                # Migração automática: copiar dados da tabela antiga 'pedidos_gerados' se existir
                cur.execute("""
                    DO $$
                    BEGIN
                        IF EXISTS (
                            SELECT 1 FROM information_schema.tables
                            WHERE table_name = 'pedidos_gerados'
                        ) AND NOT EXISTS (
                            SELECT 1 FROM hybris_pedidos LIMIT 1
                        ) THEN
                            INSERT INTO hybris_pedidos
                                (numero_pedido, nome_cliente, cpf_cliente, transaction_id,
                                 amount, terminal_number, authorization_code, generated_at, generated_by)
                            SELECT numero_pedido, nome_cliente, cpf_cliente, transaction_id,
                                   amount, terminal_number, authorization_code, generated_at, generated_by
                            FROM pedidos_gerados;
                            RAISE NOTICE 'Migração: dados copiados de pedidos_gerados para hybris_pedidos';
                        END IF;
                    END $$;
                """)
            conn.commit()
            conn.close()
            return True
        except psycopg2.Error as e:
            print(f"❌ Erro ao criar tabela hybris_pedidos: {e}")
            return False

    def save_pedido_transacao(
        self,
        numero_pedido: str,
        nome_cliente: str,
        cpf_cliente: str,
        transaction_id: str,
        amount: int,
        terminal_number: str,
        authorization_code: str,
        generated_by: str
    ) -> bool:
        """Salva uma transação de pedido gerado no histórico"""
        try:
            conn = self.get_connection()
            if not conn:
                return False
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO hybris_pedidos
                        (numero_pedido, nome_cliente, cpf_cliente, transaction_id,
                         amount, terminal_number, authorization_code, generated_by)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    numero_pedido, nome_cliente, cpf_cliente,
                    transaction_id, int(amount), terminal_number,
                    authorization_code, generated_by
                ))
            conn.commit()
            conn.close()
            return True
        except psycopg2.Error as e:
            print(f"❌ Erro ao salvar transação no histórico: {e}")
            raise  # propaga para o caller ver a mensagem real

    def get_pedidos(
        self,
        numero_pedido: str = None,
        nome_cliente: str = None,
        cpf_cliente: str = None
    ) -> list:
        """Busca histórico de pedidos gerados com filtros opcionais"""
        try:
            conn = self.get_connection()
            if not conn:
                return []
            conditions = []
            params = []
            if numero_pedido:
                conditions.append("numero_pedido ILIKE %s")
                params.append(f"%{numero_pedido}%")
            if nome_cliente:
                conditions.append("nome_cliente ILIKE %s")
                params.append(f"%{nome_cliente}%")
            if cpf_cliente:
                conditions.append("cpf_cliente ILIKE %s")
                params.append(f"%{cpf_cliente}%")
            where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
            with conn.cursor() as cur:
                cur.execute(f"""
                    SELECT numero_pedido, nome_cliente, cpf_cliente,
                           transaction_id, amount, terminal_number,
                           authorization_code, generated_at, generated_by
                    FROM hybris_pedidos
                    {where}
                    ORDER BY generated_at DESC
                    LIMIT 500
                """, params)
                rows = cur.fetchall()
            conn.close()
            return rows
        except psycopg2.Error as e:
            print(f"❌ Erro ao buscar histórico: {e}")
            return []

    def find_duplicate_transaction(self, terminal_number: str, authorization_code: str):
        """
        Verifica se o par (NSU, Autenticação) já foi usado em algum pedido anterior.

        NSU = terminal_number (campo 'number' do formulário)
        Autenticação = authorization_code

        Juntos, esse par identifica um pagamento real único (comprovante físico).
        Se já existir no histórico — mesmo que para o mesmo número de pedido —
        é sinal de erro humano (reenvio do mesmo comprovante) ou fraude.

        Retorna o registro mais recente que colide, ou None se não houver duplicidade.
        """
        if not terminal_number or not authorization_code:
            return None
        try:
            conn = self.get_connection()
            if not conn:
                return None
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT numero_pedido, nome_cliente, cpf_cliente, generated_at, generated_by
                    FROM hybris_pedidos
                    WHERE terminal_number = %s AND authorization_code = %s
                    ORDER BY generated_at DESC
                    LIMIT 1
                """, (terminal_number, authorization_code))
                row = cur.fetchone()
            conn.close()
            if not row:
                return None
            numero_pedido, nome_cliente, cpf_cliente, generated_at, generated_by = row
            return {
                "numero_pedido": numero_pedido,
                "nome_cliente": nome_cliente,
                "cpf_cliente": cpf_cliente,
                "generated_at": generated_at.strftime("%d/%m/%Y %H:%M") if generated_at else "",
                "generated_by": generated_by or ""
            }
        except psycopg2.Error as e:
            print(f"❌ Erro ao verificar duplicidade NSU/Autenticação: {e}")
            return None

    # ═══════════════════════════════════════════════════════════════════════
    # PAGAMENTOS DIRETOS (importados do Hybris via CSV)
    # ═══════════════════════════════════════════════════════════════════════
    # Pagamentos feitos dentro do pedido na maquininha chegam pagos automati-
    # camente no Hybris e nunca passam pelo Gera JSON — por isso o histórico
    # de hybris_pedidos sozinho não é suficiente pra checar duplicidade de
    # NSU/Autenticação: alguém poderia reaproveitar o comprovante de um
    # pagamento direto antigo pra "vincular" outro pedido de má fé. Essa
    # tabela guarda um snapshot importado manualmente (CSV) desses pagamentos
    # diretos, pra cruzar na mesma checagem.

    def ensure_pagamentos_diretos_table_exists(self) -> bool:
        """Cria tabela hybris_pagamentos_diretos (snapshot importado do Hybris)"""
        try:
            conn = self.get_connection()
            if not conn:
                return False
            with conn.cursor() as cur:
                cur.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(self.schema)))
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS hybris_pagamentos_diretos (
                        id SERIAL PRIMARY KEY,
                        pedido VARCHAR(50),
                        nsu VARCHAR(100) NOT NULL,
                        authorization_code VARCHAR(100) NOT NULL,
                        valor_pago VARCHAR(50),
                        data_pagamento VARCHAR(50),
                        bandeira VARCHAR(50),
                        tipo_transacao VARCHAR(100),
                        parcelas VARCHAR(10),
                        terminal VARCHAR(50),
                        status_pedido VARCHAR(50),
                        usuario VARCHAR(150),
                        imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        imported_by VARCHAR(100),
                        UNIQUE (nsu, authorization_code)
                    );
                    CREATE INDEX IF NOT EXISTS idx_pagdiretos_nsu_auth
                        ON hybris_pagamentos_diretos(nsu, authorization_code);
                """)
            conn.commit()
            conn.close()
            return True
        except psycopg2.Error as e:
            print(f"❌ Erro ao criar tabela hybris_pagamentos_diretos: {e}")
            return False

    def import_pagamentos_diretos(self, rows: list, imported_by: str) -> dict:
        """
        Importa (upsert por nsu+authorization_code) linhas do CSV de pagamentos
        diretos exportado do Hybris. Cada item de `rows` é um dict com pelo
        menos 'nsu' e 'authorization_code'; demais chaves são opcionais.

        Retorna {"imported": int, "skipped": int}
        """
        imported = 0
        skipped = 0
        try:
            conn = self.get_connection()
            if not conn:
                return {"imported": 0, "skipped": len(rows)}
            with conn.cursor() as cur:
                for row in rows:
                    nsu = (row.get("nsu") or "").strip()
                    auth = (row.get("authorization_code") or "").strip()
                    if not nsu or not auth:
                        skipped += 1
                        continue
                    cur.execute("""
                        INSERT INTO hybris_pagamentos_diretos
                            (pedido, nsu, authorization_code, valor_pago, data_pagamento,
                             bandeira, tipo_transacao, parcelas, terminal, status_pedido,
                             usuario, imported_by)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (nsu, authorization_code) DO UPDATE SET
                            pedido = EXCLUDED.pedido,
                            valor_pago = EXCLUDED.valor_pago,
                            data_pagamento = EXCLUDED.data_pagamento,
                            bandeira = EXCLUDED.bandeira,
                            tipo_transacao = EXCLUDED.tipo_transacao,
                            parcelas = EXCLUDED.parcelas,
                            terminal = EXCLUDED.terminal,
                            status_pedido = EXCLUDED.status_pedido,
                            usuario = EXCLUDED.usuario,
                            imported_at = CURRENT_TIMESTAMP,
                            imported_by = EXCLUDED.imported_by
                    """, (
                        row.get("pedido"), nsu, auth, row.get("valor_pago"),
                        row.get("data_pagamento"), row.get("bandeira"),
                        row.get("tipo_transacao"), row.get("parcelas"),
                        row.get("terminal"), row.get("status_pedido"),
                        row.get("usuario"), imported_by
                    ))
                    imported += 1
            conn.commit()
            conn.close()
            return {"imported": imported, "skipped": skipped}
        except psycopg2.Error as e:
            print(f"❌ Erro ao importar pagamentos diretos: {e}")
            return {"imported": imported, "skipped": skipped + (len(rows) - imported - skipped)}

    def find_duplicate_in_pagamentos_diretos(self, nsu: str, authorization_code: str):
        """
        Verifica se o par (NSU, Autenticação) já aparece nos pagamentos diretos
        importados do Hybris (pagamento automático, fora do Gera JSON).

        Retorna o registro que colide, ou None se não houver duplicidade.
        """
        if not nsu or not authorization_code:
            return None
        try:
            conn = self.get_connection()
            if not conn:
                return None
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT pedido, valor_pago, data_pagamento, bandeira,
                           tipo_transacao, parcelas, terminal, status_pedido, usuario
                    FROM hybris_pagamentos_diretos
                    WHERE nsu = %s AND authorization_code = %s
                    LIMIT 1
                """, (nsu, authorization_code))
                row = cur.fetchone()
            conn.close()
            if not row:
                return None
            (pedido, valor_pago, data_pagamento, bandeira,
             tipo_transacao, parcelas, terminal, status_pedido, usuario) = row
            return {
                "pedido": pedido or "",
                "valor_pago": valor_pago or "",
                "data_pagamento": data_pagamento or "",
                "bandeira": bandeira or "",
                "tipo_transacao": tipo_transacao or "",
                "parcelas": parcelas or "",
                "terminal": terminal or "",
                "status_pedido": status_pedido or "",
                "usuario": usuario or ""
            }
        except psycopg2.Error as e:
            print(f"❌ Erro ao verificar duplicidade em pagamentos diretos: {e}")
            return None

    # ═══════════════════════════════════════════════════════════════════════
    # OVERRIDE DE DUPLICIDADE (trocas de pedido legítimas)
    # ═══════════════════════════════════════════════════════════════════════
    # Quando um comprovante (NSU + Autenticação) já usado é reaproveitado de
    # propósito numa troca de pedido (cliente troca de bicicleta por tamanho
    # ou defeito), o usuário pode liberar a geração mesmo assim. Registramos
    # quem liberou e quando, para manter rastreabilidade do anti-fraude.

    def ensure_duplicate_overrides_table_exists(self) -> bool:
        """Cria tabela hybris_duplicate_overrides (auditoria de liberações manuais)"""
        try:
            conn = self.get_connection()
            if not conn:
                return False
            with conn.cursor() as cur:
                cur.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(self.schema)))
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS hybris_duplicate_overrides (
                        id SERIAL PRIMARY KEY,
                        numero_pedido VARCHAR(20) NOT NULL,
                        nsu VARCHAR(100),
                        authorization_code VARCHAR(100),
                        source VARCHAR(20),
                        pedido_original VARCHAR(50),
                        overridden_by VARCHAR(100),
                        overridden_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                    CREATE INDEX IF NOT EXISTS idx_overrides_numero ON hybris_duplicate_overrides(numero_pedido);
                    CREATE INDEX IF NOT EXISTS idx_overrides_nsu_auth ON hybris_duplicate_overrides(nsu, authorization_code);
                """)
            conn.commit()
            conn.close()
            return True
        except psycopg2.Error as e:
            print(f"❌ Erro ao criar tabela hybris_duplicate_overrides: {e}")
            return False

    def log_duplicate_override(
        self,
        numero_pedido: str,
        nsu: str,
        authorization_code: str,
        source: str,
        pedido_original: str,
        overridden_by: str
    ) -> bool:
        """Registra que um usuário liberou a geração apesar de NSU/Autenticação duplicados"""
        try:
            conn = self.get_connection()
            if not conn:
                return False
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO hybris_duplicate_overrides
                        (numero_pedido, nsu, authorization_code, source, pedido_original, overridden_by)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (numero_pedido, nsu, authorization_code, source, pedido_original, overridden_by))
            conn.commit()
            conn.close()
            return True
        except psycopg2.Error as e:
            print(f"❌ Erro ao registrar liberação de duplicidade: {e}")
            return False
