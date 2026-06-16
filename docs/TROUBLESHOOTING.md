# Troubleshooting - Resolução de Problemas

**Última atualização**: 2025-12-09

---

## 🔍 Diagnóstico Rápido

Antes de qualquer coisa, rode o diagnóstico completo:

```bash
python tools/diagnostico_completo.py
```

Este script verifica:
- ✅ Conexão PostgreSQL
- ✅ Usuários carregados
- ✅ config.yaml presente
- ✅ Sincronização

---

## 🔴 Problema: "User not authorized"

### Sintomas
- Você digita usuário e senha corretos
- Recebe mensagem "User not authorized"
- Não consegue acessar a aplicação

### Solução

**Passo 1: Rodar diagnóstico**
```bash
python tools/diagnostico_completo.py
```

**Passo 2: Verificar output**

Se o diagnóstico mostrar:
```
PostgreSQL: 4 usuários
config.yaml: 1 usuário
Status: ❌ NÃO SINCRONIZADO
```

**Passo 3: Sincronizar manualmente**
```bash
python tools/debug_sync.py
```

**Passo 4: Reiniciar a aplicação**

Se estiver rodando localmente:
```bash
# Parar (Ctrl+C) e iniciar novamente
streamlit run src/app_streamlit.py
```

Se estiver no Coolify:
- Vá para o painel do Coolify
- Clique em "Restart" no container da aplicação

**Passo 5: Tentar login novamente**

Use navegador em **modo incógnito** (Ctrl+Shift+N no Chrome) para evitar cache.

---

## 🔴 Problema: "Credenciais inválidas"

### Sintomas
- Mensagem "Credenciais inválidas" ao fazer login
- Tem certeza que a senha está correta

### Soluções

**1. Verificar se usuário existe**
```bash
python tools/verificar_usuarios_postgres.py
```

Este script lista todos os usuários cadastrados.

**2. Tentar em navegador incógnito**

Às vezes o cache do navegador causa problemas:
- Chrome/Edge: Ctrl+Shift+N
- Firefox: Ctrl+Shift+P

**3. Verificar se senha tem caracteres especiais**

Se sua senha tem caracteres especiais (!, @, #, $), certifique-se de digitá-los corretamente.

**4. Contatar administrador**

Se nada funcionar, peça ao administrador para:
- Verificar se seu usuário está ativo
- Resetar sua senha se necessário

---

## 🟡 Problema: Login lento

### Sintomas
- Login demora mais de 5 segundos
- Página carrega devagar

### Causa Provável
Conexão com PostgreSQL está lenta (servidor longe geograficamente)

### Solução
Não há solução imediata - é limitação de infraestrutura. O sistema funciona normalmente, apenas é mais lento.

---

## 🟡 Problema: Session expired logo após login

### Sintomas
- Login funciona mas é deslogado em segundos
- Precisa fazer login novamente constantemente

### Solução

**Limpar cookies do navegador:**

1. Chrome/Edge:
   - Ctrl+Shift+Delete
   - Selecione "Cookies e outros dados de sites"
   - Clique em "Limpar dados"

2. Firefox:
   - Ctrl+Shift+Delete
   - Selecione "Cookies"
   - Clique em "Limpar agora"

3. Tente login novamente

---

## ✅ Checklist de Verificação

Antes de reportar problema ao administrador:

- [ ] Tentei em navegador incógnito?
- [ ] Verifiquei se usuário/senha estão corretos?
- [ ] Limpei cookies do navegador?
- [ ] Rodei `python tools/diagnostico_completo.py`?
- [ ] Tentei fazer logout e login novamente?

---

## 🔧 Scripts Úteis

```bash
# Diagnóstico completo (mais importante)
python tools/diagnostico_completo.py

# Verificar usuários no PostgreSQL
python tools/verificar_usuarios_postgres.py

# Sincronização manual
python tools/debug_sync.py
```

---

## 📞 Como Reportar Problema ao Administrador

Se nada acima resolver, reporte com as seguintes informações:

1. **Output do diagnóstico:**
   ```bash
   python tools/diagnostico_completo.py > diagnostico.txt
   ```
   Anexe o arquivo `diagnostico.txt`

2. **Descrição do problema:**
   - O que você tentou fazer?
   - O que aconteceu?
   - Mensagem de erro exata

3. **O que já tentou:**
   - Navegador incógnito?
   - Limpou cookies?
   - Rodou diagnóstico?

---

## 📚 Veja Também

- [GUIA.md](GUIA.md) - Como usar a aplicação
- [EXEMPLOS.md](EXEMPLOS.md) - Exemplos de uso

---

**Status**: ✅ Problemas mais comuns cobertos
