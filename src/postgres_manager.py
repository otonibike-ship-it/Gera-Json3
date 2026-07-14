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

        self.db_config = {
            'host': host,
            'port': int(os.getenv('DB_PORT', '5432')),
            'database': os.getenv('DB_NAME', 'postgres'),
            'user': os.getenv('DB_USER', 'postgres'),
            'password': password
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
